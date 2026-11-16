"""Hybrid HUD: full dashboard on demand, discreet tray resident when closed."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import threading
import time
from datetime import datetime

from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer, QRunnable, QThreadPool, QSize, QUrl
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QIcon, QPixmap, QLinearGradient, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QInputDialog,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon,
    QTextEdit, QVBoxLayout, QWidget,
)

from .agent import Agent
from .config import Config, api_key, save_api_key, data_dir
from .google_connector import GoogleConnector
from .memory import Memory
from .owner_auth import OwnerGate
from .gaming import GamingState, installed_game_running
from .audio_devices import input_devices, microphone_probe
from .updates import check_official_release
from .request_control import RequestCancelled, check_cancelled
from .recovery import register_windows_restart
from .tools import ToolExecutor
from .voice import Speaker, WakeListener, record_phrase, transcribe, transcribe_local
from .neural_voice import VOICE_CHOICES, neural_available
from .wake_model import resolve_model, install_model
from .local_ai import has_local_bundle

BG = "#050a14"
PANEL = "#0d1727"
PANEL2 = "#101f31"
CYAN = "#00d9fa"
SOFT = "#86c5db"
MUTED = "#6e8aa0"

QSS = f"""
QWidget {{ color: #d9f4ff; font-family: 'Segoe UI'; font-size: 12px; }}
QMainWindow, QDialog {{ background: {BG}; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid #1a3a50; border-radius: 14px; }}
QFrame#panelSmall {{ background: {PANEL2}; border: 1px solid #184158; border-radius: 10px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#heading {{ font-size: 22px; font-weight: 800; color: white; letter-spacing: 3px; }}
QLabel#section {{ color: {SOFT}; font-size: 11px; letter-spacing: 2px; font-weight: 700; }}
QPushButton {{ background: #122d40; color: #b7eefe; border: 1px solid #20617d; border-radius: 9px;
  padding: 9px 12px; font-weight: 600; }}
QPushButton:hover {{ background: #184761; border: 1px solid {CYAN}; }}
QPushButton:pressed {{ background: #0b2536; }}
QPushButton#primary {{ background: #00b9d7; color: #001824; border: 0; font-weight: 800; }}
QPushButton#primary:hover {{ background: {CYAN}; }}
QPushButton:disabled {{ color: #557282; background: #12212c; border: 1px solid #203746; }}
QLineEdit, QTextEdit {{ background: #081724; border: 1px solid #25546c; border-radius: 8px;
 padding: 10px; color: #e9fcff; selection-background-color: #146884; }}
QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {CYAN}; }}
QScrollArea {{ border: 0; }}
QCheckBox {{ spacing: 9px; }}
"""


class Orb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.active = False
        self.setMinimumSize(260, 260)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(35)

    def tick(self):
        self.angle = (self.angle + (2.2 if self.active else 0.65)) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * .39
        p.fillRect(self.rect(), QColor(BG))
        # subtle scan lines
        for i in range(16, h, 26):
            p.setPen(QPen(QColor(8, 54, 71, 40), 1))
            p.drawLine(0, i, w, i)
        for pct in [1.13, 1.01, .86, .69, .5]:
            p.setPen(QPen(QColor(0, 146, 198, 80 if pct > 0.8 else 125), 1.4))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx-r*pct), int(cy-r*pct), int(r*2*pct), int(r*2*pct))
        # rotating arcs
        for k, (pct, length, width) in enumerate([(1.07, 96, 3.5), (.91, 65, 2.5), (.75, 52, 4), (.58, 130, 1.4)]):
            rect = (int(cx-r*pct), int(cy-r*pct), int(r*2*pct), int(r*2*pct))
            angle = self.angle * (1 if k % 2 == 0 else -1) + k * 73
            p.setPen(QPen(QColor(CYAN if k == 0 else "#3f9bbc"), width, Qt.SolidLine, Qt.RoundCap))
            from PySide6.QtCore import QRect
            p.drawArc(QRect(*rect), int(angle*16), int(length*16))
        # core soft radial gradient
        from PySide6.QtGui import QRadialGradient
        g = QRadialGradient(cx, cy, r * .55)
        g.setColorAt(0, QColor(1, 153, 193, 115 if self.active else 65))
        g.setColorAt(0.67, QColor(0, 78, 111, 40))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g)
        p.setPen(Qt.NoPen)
        p.drawEllipse(int(cx-r*.65), int(cy-r*.65), int(r*1.3), int(r*1.3))
        # center label
        f = QFont("Segoe UI", max(17, int(r*.24)), QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        p.setFont(f)
        p.setPen(QColor("#e5fdff"))
        p.drawText(int(cx-r*.8), int(cy-r*.15), int(r*1.6), int(r*.35), Qt.AlignCenter, "J.A.R.V.I.S.")
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor("#5fa9c3"))
        p.drawText(int(cx-r*.7), int(cy+r*.13), int(r*1.4), 19, Qt.AlignCenter,
                   "PROCESSING" if self.active else "SYSTEM ONLINE")
        p.end()


def panel() -> QFrame:
    f = QFrame()
    f.setObjectName("panel")
    return f


def section(title: str) -> QLabel:
    l = QLabel(title)
    l.setObjectName("section")
    return l


def muted(title: str) -> QLabel:
    l = QLabel(title)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class Bridge(QObject):
    approval_requested = Signal(str, str, object)
    wake_detected = Signal()
    wake_error = Signal(str)
    speech_finished = Signal()
    speech_sentence = Signal(str)
    speech_error = Signal(str)


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS / CONFIGURATION")
        self.setMinimumWidth(560)
        self.resize(610, 700)
        self.cfg = cfg
        self.setStyleSheet(QSS)
        lay = QVBoxLayout(self)
        title = QLabel("SYSTEM CONFIGURATION")
        title.setObjectName("heading")
        lay.addWidget(title)
        form = QFormLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Paste your private OpenAI API key (blank keeps saved key)")
        self.key.setToolTip("Stored in your Windows user credential vault. Do not put keys in shared screenshots.")
        self.provider = QComboBox()
        self.provider.addItem("LOCAL / FREE — no API credits", "local")
        self.provider.addItem("HYBRID — local, then OpenAI if configured", "hybrid")
        self.provider.addItem("OPENAI — cloud only", "openai")
        self.provider.setCurrentIndex(max(0, self.provider.findData(cfg.provider)))
        self.model = QLineEdit(cfg.model)
        self.model.setToolTip("Responses API model available in your OpenAI project")
        self.voice = QCheckBox("Enable spoken replies")
        self.voice.setChecked(cfg.voice_enabled)
        self.voice_engine = QComboBox()
        self.voice_engine.addItem("Natural neural voice — OFFLINE", "neural")
        self.voice_engine.addItem("Windows built-in voice — OFFLINE", "sapi")
        self.voice_engine.setCurrentIndex(max(0, self.voice_engine.findData(cfg.voice_engine)))
        self.voice_choice = QComboBox()
        for voice_id, name in VOICE_CHOICES.items():
            self.voice_choice.addItem(name, voice_id)
        self.voice_choice.setCurrentIndex(max(0, self.voice_choice.findData(cfg.voice_name)))
        self.voice_speed = QComboBox()
        self.voice_speed.addItem("Relaxed (0.9×)", 0.9)
        self.voice_speed.addItem("Natural (1.0×)", 1.0)
        self.voice_speed.addItem("Quick (1.1×)", 1.1)
        self.voice_speed.addItem("Brisk (1.2×)", 1.2)
        self.voice_speed.setCurrentIndex(max(0, self.voice_speed.findData(cfg.voice_speed)))
        self.history = QCheckBox("Save local chat history")
        self.history.setChecked(cfg.save_history)
        self.wake = QCheckBox("Enable offline 'Jarvis' wake word (no model folder needed)")
        self.wake.setChecked(cfg.wake_enabled)
        self.microphones = QComboBox()
        self.microphones.addItem("Windows default microphone", None)
        for device_id, label in input_devices():
            self.microphones.addItem(f"{label} (#{device_id})", device_id)
        selected_mic = self.microphones.findData(cfg.microphone_device)
        self.microphones.setCurrentIndex(max(0, selected_mic))
        self.microphone_test = QPushButton("TEST SELECTED MICROPHONE")
        self.microphone_test.clicked.connect(self._test_microphone)
        self.recovery_enabled = QCheckBox("Allow Windows to offer recovery after a crash")
        self.recovery_enabled.setChecked(cfg.crash_restart_enabled)
        self.gaming_enabled = QCheckBox("Automatically detect Crusader Kings III / Warband")
        self.gaming_enabled.setChecked(cfg.gaming_mode_enabled)
        self.gaming_pause_wake = QCheckBox("Pause wake listening while gaming")
        self.gaming_pause_wake.setChecked(cfg.gaming_pause_wake)
        self.gaming_mute_speech = QCheckBox("Mute spoken replies during gameplay")
        self.gaming_mute_speech.setChecked(cfg.gaming_mute_speech)
        self.custom = QLineEdit(cfg.custom_folder)
        self.custom.setPlaceholderText("Optional extra folder to search; blank = none")
        self.google = QLineEdit(cfg.google_credentials_path)
        self.google.setPlaceholderText("Path to OAuth Desktop credentials.json")
        self.write = QCheckBox("Allow Gmail send + Calendar write (always confirm each action)")
        self.write.setChecked(cfg.google_write_enabled)
        self.sites = QTextEdit()
        self.sites.setFixedHeight(92)
        self.sites.setPlainText(json.dumps(cfg.sites, indent=2))
        self.projects = QTextEdit()
        self.projects.setFixedHeight(78)
        self.projects.setPlainText(json.dumps(cfg.project_folders, indent=2))
        form.addRow("AI provider", self.provider)
        form.addRow("OpenAI API key (optional)", self.key)
        form.addRow("Cloud model (if used)", self.model)
        form.addRow("Speech output", self.voice)
        form.addRow("Speech engine", self.voice_engine)
        form.addRow("Voice", self.voice_choice)
        form.addRow("Speaking speed", self.voice_speed)
        form.addRow("Local memory", self.history)
        form.addRow("Wake listener", self.wake)
        form.addRow("Input microphone", self.microphones)
        form.addRow("Microphone diagnostics", self.microphone_test)
        form.addRow("Crash recovery", self.recovery_enabled)
        form.addRow("Gaming focus", self.gaming_enabled)
        form.addRow("Gaming microphone", self.gaming_pause_wake)
        form.addRow("Gaming speech", self.gaming_mute_speech)
        model_path = resolve_model(cfg.wake_model_path)
        self.model_status = QLabel("Vosk wake model: bundled / ready" if model_path else "Vosk wake model: automatically installed when enabled")
        self.model_status.setWordWrap(True)
        form.addRow("Wake model", self.model_status)
        self.ai_model_status = QLabel("Offline LLM: bundled / ready" if has_local_bundle() else
                                      "Offline LLM: not bundled in source checkout; build full installer")
        self.ai_model_status.setWordWrap(True)
        form.addRow("Local brain", self.ai_model_status)
        form.addRow("Extra file folder", self.custom)
        form.addRow("Google OAuth JSON", self.google)
        form.addRow("Google write access", self.write)
        form.addRow("HTTPS bookmarks (JSON)", self.sites)
        form.addRow("Local project folders (JSON)", self.projects)
        # Many security, audio and gaming controls must remain usable on
        # standard 768p laptop displays. Keep Save/Cancel below a scroll area.
        scroller = QScrollArea(self)
        scroller.setWidgetResizable(True)
        scroller.setMinimumHeight(360)
        scroller.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setLayout(form)
        scroller.setWidget(content)
        lay.addWidget(scroller, 1)
        api_actions = QHBoxLayout()
        open_keys = QPushButton("CREATE / FIND API KEY")
        open_keys.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://platform.openai.com/api-keys")))
        api_actions.addWidget(open_keys)
        self.test_key_button = QPushButton("TEST OPENAI CONNECTION")
        self.test_key_button.clicked.connect(self._test_api_key)
        api_actions.addWidget(self.test_key_button)
        lay.addLayout(api_actions)
        self.check_updates_button = QPushButton("CHECK OFFICIAL JARVIS RELEASES")
        self.check_updates_button.clicked.connect(self._check_updates)
        lay.addWidget(self.check_updates_button)
        choose = QPushButton("Browse Google credentials…")
        choose.clicked.connect(self._pick_google)
        lay.addWidget(choose)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _check_updates(self):
        self.check_updates_button.setEnabled(False)
        self.check_updates_button.setText("CHECKING OFFICIAL RELEASES…")
        self._update_task = Task(lambda: check_official_release("0.7.0"))
        self._update_task.signals.done.connect(self._update_result)
        self._update_task.signals.failed.connect(self._update_error)
        QThreadPool.globalInstance().start(self._update_task)

    def _update_result(self, result):
        self.check_updates_button.setEnabled(True)
        self.check_updates_button.setText("CHECK OFFICIAL JARVIS RELEASES")
        if result.get("update") and result.get("url"):
            yes = QMessageBox.question(
                self, "Official JARVIS release",
                "A newer stable release " + result["version"] +
                " is available. Open the official GitHub release page?\n\n"
                "JARVIS will not download or install an unverified program.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if yes == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(result["url"]))
        else:
            QMessageBox.information(
                self, "JARVIS updates",
                "No newer stable public release is available. Development "
                "drafts are excluded from this check."
            )

    def _update_error(self, _error):
        self.check_updates_button.setEnabled(True)
        self.check_updates_button.setText("CHECK OFFICIAL JARVIS RELEASES")
        QMessageBox.warning(
            self, "Update check unavailable",
            "Could not contact the official GitHub release endpoint. "
            "No application changes were made."
        )

    def _test_microphone(self):
        """Half-second local volume check, only when the user clicks Test."""
        self.microphone_test.setEnabled(False)
        self.microphone_test.setText("TESTING MICROPHONE…")
        target = self.microphones.currentData()
        self._mic_task = Task(lambda: microphone_probe(target))
        self._mic_task.signals.done.connect(self._microphone_test_ok)
        self._mic_task.signals.failed.connect(self._microphone_test_failed)
        QThreadPool.globalInstance().start(self._mic_task)

    def _microphone_test_ok(self, result):
        self.microphone_test.setEnabled(True)
        self.microphone_test.setText("TEST SELECTED MICROPHONE")
        QMessageBox.information(
            self, "Microphone test",
            f"Microphone opened successfully. Average audio level: {result['rms']:.0f}. "
            "Audio was neither recorded to disk nor uploaded."
        )

    def _microphone_test_failed(self, _error):
        self.microphone_test.setEnabled(True)
        self.microphone_test.setText("TEST SELECTED MICROPHONE")
        QMessageBox.warning(
            self, "Microphone unavailable",
            "Could not read this microphone. Check Windows microphone privacy settings "
            "and whether another application has exclusive access."
        )

    def _test_api_key(self):
        """User-initiated, asynchronous credential validation without logging secrets."""
        key = self.key.text().strip() or api_key()
        if not key:
            QMessageBox.information(self, "API key missing", "Paste an OpenAI API key into the field first.")
            return
        self.test_key_button.setEnabled(False)
        self.test_key_button.setText("TESTING CONNECTION...")

        def check():
            from openai import OpenAI
            with OpenAI(api_key=key, timeout=12.0, max_retries=0) as client:
                client.models.list()
            return True

        self._api_task = Task(check)
        self._api_task.signals.done.connect(self._key_test_success)
        self._api_task.signals.failed.connect(self._key_test_failure)
        QThreadPool.globalInstance().start(self._api_task)

    def _key_test_success(self, _result):
        self.test_key_button.setEnabled(True)
        self.test_key_button.setText("TEST OPENAI CONNECTION")
        QMessageBox.information(self, "Connected", "OpenAI accepted your API key. Save your settings to store it securely. Billing and model permissions are checked when AI commands run.")

    def _key_test_failure(self, _err):
        self.test_key_button.setEnabled(True)
        self.test_key_button.setText("TEST OPENAI CONNECTION")
        # Never expose raw exception text; some proxies echo HTTP headers.
        QMessageBox.warning(self, "Connection failed", "Could not authenticate with OpenAI. Check your key, internet connection and API account, then retry.")

    def _pick_google(self):
        path, _ = QFileDialog.getOpenFileName(self, "OAuth Desktop credentials", str(Path.home()), "JSON (*.json)")
        if path:
            self.google.setText(path)

    def apply(self):
        try:
            sites = json.loads(self.sites.toPlainText())
            project_folders = json.loads(self.projects.toPlainText())
            if not isinstance(project_folders, dict) or any(
                    not isinstance(k, str) or not k.strip() or
                    not isinstance(v, str) or not v.strip()
                    for k, v in project_folders.items()):
                raise ValueError("Project folders must be a JSON map of names to paths")
            if not isinstance(sites, dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in sites.items()):
                raise ValueError("Bookmarks must be an object of names to URLs")
            from urllib.parse import urlparse
            for url in sites.values():
                u = urlparse(url)
                if u.scheme != "https" or not u.hostname or u.username or u.password:
                    raise ValueError("Every bookmark must be an HTTPS website URL")
            if self.key.text().strip():
                save_api_key(self.key.text())
            self.cfg.sites = sites
            self.cfg.project_folders = project_folders
            self.cfg.provider = self.provider.currentData()
            self.cfg.model = self.model.text().strip() or "gpt-5.5"
            self.cfg.voice_enabled = self.voice.isChecked()
            self.cfg.voice_engine = self.voice_engine.currentData()
            self.cfg.voice_name = self.voice_choice.currentData()
            self.cfg.voice_speed = float(self.voice_speed.currentData())
            self.cfg.save_history = self.history.isChecked()
            self.cfg.wake_enabled = self.wake.isChecked()
            self.cfg.microphone_device = self.microphones.currentData()
            self.cfg.gaming_mode_enabled = self.gaming_enabled.isChecked()
            self.cfg.crash_restart_enabled = self.recovery_enabled.isChecked()
            self.cfg.gaming_pause_wake = self.gaming_pause_wake.isChecked()
            self.cfg.gaming_mute_speech = self.gaming_mute_speech.isChecked()
            # Vosk model path is discovered automatically from bundled files or app data.
            self.cfg.wake_model_path = ""
            self.cfg.custom_folder = self.custom.text().strip()
            self.cfg.google_credentials_path = self.google.text().strip()
            self.cfg.google_write_enabled = self.write.isChecked()
            self.cfg.save()
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))


class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS // DESKTOP INTELLIGENCE")
        self.resize(1200, 800)
        self.setMinimumSize(920, 650)
        self.setStyleSheet(QSS)
        self.pool = QThreadPool.globalInstance()
        self.bridge = Bridge()
        self.bridge.approval_requested.connect(self._ask_approval)
        self.bridge.wake_detected.connect(self._on_wake)
        self.bridge.wake_error.connect(self._wake_error)
        self.bridge.speech_finished.connect(self._on_speech_finished)
        self.bridge.speech_sentence.connect(self._on_stream_sentence)
        self.bridge.speech_error.connect(self._notice)
        self.config = Config.load()
        self.owner_gate = OwnerGate()
        self.game_state = GamingState(False)
        self.memory = Memory()
        self.google = GoogleConnector(self.config)
        self.speaker = Speaker(
            on_finished=lambda: self.bridge.speech_finished.emit(),
            on_error=lambda error: self.bridge.speech_error.emit(error),
            engine=self.config.voice_engine, voice=self.config.voice_name,
            speed=self.config.voice_speed,
        )
        self._speaking = False
        self._streamed_speech = False
        self._speech_muted = False
        self.wake_listener = None
        self._installing_wake_model = False
        self._busy = False
        self._quitting = False
        self._request_cancel = None
        self._request_capability = None
        self._request_started = 0.0
        self._first_audio_latency = 0.0
        self.agent = None
        executor = ToolExecutor(self.config, self.memory, self.google, self._approve,
                                lambda: self.agent.describe_screen(),
                                owner_gate=self.owner_gate)
        self.executor = executor
        self.agent = Agent(self.config, self.memory, executor)
        self.agent.local_runtime.gaming_mode_enabled = self.config.gaming_mode_enabled
        self._build_ui()
        self._make_tray()
        self._sync_owner_visibility()
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self._refresh_gaming)
        self.game_timer.start(5000)
        self._refresh_gaming()
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._refresh_stats)
        self.stats_timer.start(3500)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._poll_reminders)
        self.reminder_timer.start(15000)
        self._poll_reminders()
        self._refresh_stats()
        self._start_wake()
        if self.config.provider in ("local", "hybrid") and not self.game_state.active:
            QTimer.singleShot(2500, self._warm_local_brain)
        self._append("SYSTEM", "JARVIS initialised. Offline AI is the default; no OpenAI API key is required. Enable the hands-free wake listener in Settings. Closing the window keeps the tray assistant running.")
        if not (data_dir() / "onboarding_complete.flag").exists():
            QTimer.singleShot(500, self._first_launch)

    def _build_ui(self):
        body = QWidget()
        self.setCentralWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(22, 17, 22, 16)
        root.setSpacing(15)
        header = QHBoxLayout()
        badge = QLabel("J.A.R.V.I.S.  /  PERSONAL INTELLIGENCE")
        badge.setObjectName("heading")
        header.addWidget(badge)
        header.addStretch()
        self.clock = muted("")
        header.addWidget(self.clock)
        settings = QPushButton("⚙  SETTINGS")
        settings.clicked.connect(self.settings)
        header.addWidget(settings)
        owner = QPushButton("OWNER ACCESS")
        owner.clicked.connect(self.manage_owner_access)
        header.addWidget(owner)
        root.addLayout(header)
        line = QFrame(); line.setFixedHeight(2); line.setStyleSheet("background: #11445c; border: 0;")
        root.addWidget(line)
        upper = QHBoxLayout()
        upper.setSpacing(15)
        root.addLayout(upper, 5)
        left = panel(); left.setFixedWidth(225)
        left_lay = QVBoxLayout(left); left_lay.setContentsMargins(17, 20, 17, 17); left_lay.setSpacing(12)
        left_lay.addWidget(section("QUICK ACCESS"))
        for title, prompt in [
            ("SYSTEM DIAGNOSTICS", "Check my PC CPU, RAM and battery status"),
            ("TODAY'S CALENDAR", "Show my upcoming calendar events"),
            ("EMAIL BRIEFING", "Summarise my newest emails"),
            ("MY MEMORIES", "What notes have you remembered about my projects?"),
            ("REMINDERS", "What local reminders do I have scheduled?"),
            ("OPEN NOTEPAD", "Open Notepad on this PC"),
            ("PAYCORE FOLDER", "Open PayCore project folder"),
            ("PAYCORE STATUS", "Read PayCore local project status"),
        ]:
            b = QPushButton(title); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, x=prompt: self.submit(x))
            left_lay.addWidget(b)
        left_lay.addStretch()
        left_lay.addWidget(section("PRIVACY & CONTROL"))
        left_lay.addWidget(muted("Offline AI and voice work without credits. Cloud API is optional. Sensitive operations request approval."))
        clear = QPushButton("CLEAR CHAT HISTORY")
        clear.clicked.connect(self.clear_history)
        left_lay.addWidget(clear)
        upper.addWidget(left)
        center = panel()
        center_l = QVBoxLayout(center); center_l.setContentsMargins(14, 10, 14, 14)
        center_l.addWidget(section("CENTRAL INTELLIGENCE"), alignment=Qt.AlignHCenter)
        self.orb = Orb(); self.orb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center_l.addWidget(self.orb, 1)
        self.state = QLabel("ONLINE  /  AWAITING COMMAND")
        self.state.setStyleSheet(f"color: {CYAN}; font: bold 12px Consolas; letter-spacing: 2px;")
        self.state.setAlignment(Qt.AlignCenter)
        center_l.addWidget(self.state)
        controls = QHBoxLayout()
        self.listen = QPushButton("◉   LISTEN")
        self.listen.setObjectName("primary")
        self.listen.clicked.connect(self._listen)
        controls.addWidget(self.listen)
        self.stop_voice_button = QPushButton("STOP SPEAKING")
        self.stop_voice_button.clicked.connect(self.stop_speaking)
        controls.addWidget(self.stop_voice_button)
        self.cancel_task_button = QPushButton("CANCEL REQUEST")
        self.cancel_task_button.clicked.connect(self.cancel_request)
        self.cancel_task_button.setEnabled(False)
        controls.addWidget(self.cancel_task_button)
        self.voice_button = QPushButton("VOICE  ON" if self.config.voice_enabled else "VOICE  OFF")
        self.voice_button.clicked.connect(self.toggle_voice)
        controls.addWidget(self.voice_button)
        center_l.addLayout(controls)
        upper.addWidget(center, 1)
        right = panel(); right.setFixedWidth(225)
        right_l = QVBoxLayout(right); right_l.setContentsMargins(17, 20, 17, 17); right_l.setSpacing(12)
        right_l.addWidget(section("SYSTEM TELEMETRY"))
        self.cpu = QLabel("CPU   -- %")
        self.ram = QLabel("RAM   -- %")
        self.batt = QLabel("BATTERY   --")
        self.response_speed = QLabel("RESPONSE   --")
        for widget in [self.cpu, self.ram, self.batt, self.response_speed]:
            widget.setStyleSheet("font: bold 16px Consolas; color:#b6f5ff; padding: 7px 0;")
            right_l.addWidget(widget)
        right_l.addSpacing(10)
        right_l.addWidget(section("SERVICES"))
        self.api_status = muted("AI: LOCAL / FREE")
        self.google_status = muted("GOOGLE: OPTIONAL")
        self.mic_status = muted("MICROPHONE: OFF")
        self.game_status = muted("GAMING: NORMAL")
        self.local_health = muted("LOCAL AI: NOT STARTED")
        for widget in (self.api_status, self.google_status, self.mic_status, self.game_status, self.local_health):
            right_l.addWidget(widget)
        right_l.addStretch()
        connect = QPushButton("CONNECT GOOGLE")
        connect.clicked.connect(self.connect_google)
        right_l.addWidget(connect)
        hint = muted("Minimise / close to tray. No automatic emails, payments, or file changes.")
        right_l.addWidget(hint)
        upper.addWidget(right)
        lower = panel(); lower_l = QVBoxLayout(lower)
        lower_l.setContentsMargins(17, 12, 17, 15)
        lower_l.addWidget(section("CONVERSATION STREAM"))
        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setMinimumHeight(150)
        self.conversation.document().setMaximumBlockCount(450)
        lower_l.addWidget(self.conversation)
        input_row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ask JARVIS anything…  (Enter to send)")
        self.entry.returnPressed.connect(lambda: self.submit(self.entry.text()))
        input_row.addWidget(self.entry, 1)
        self.send_button = QPushButton("SEND  ↗")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(lambda: self.submit(self.entry.text()))
        input_row.addWidget(self.send_button)
        lower_l.addLayout(input_row)
        root.addWidget(lower, 3)

    def _append(self, who: str, text: str):
        from html import escape
        label = {"USER": "#00d9fa", "JARVIS": "#e8f9ff", "SYSTEM": "#789bad"}.get(who, "#a5bdcc")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.conversation.append(
            f'<span style="color:{label}; font-weight:700;">[{timestamp}] {escape(who)}</span>'
            f'<div style="color:#cbdfe7; margin:3px 0 11px 0; white-space:pre-wrap;">{escape(text).replace(chr(10),"<br>")}</div>')

    def _set_busy(self, busy, message="ONLINE  /  AWAITING COMMAND"):
        self._busy = busy
        self.orb.active = busy
        self.listen.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.cancel_task_button.setEnabled(busy)
        self.state.setText(message)
        if not busy and self.config.wake_enabled and not self._speaking:
            self._start_wake()

    def _warm_local_brain(self):
        if (not self._quitting and not self.game_state.active
                and self.config.provider in ("local", "hybrid")):
            self._run_task(lambda: self.agent.local_runtime.client(), lambda result: None,
                           lambda error: self._append("SYSTEM", "Local AI prewarm unavailable: " + error[:130]))

    def _run_task(self, func, done, error=None):
        task = Task(func)
        task.signals.done.connect(done)
        task.signals.failed.connect(error or self._notice)
        self.pool.start(task)
        # The signals are QObject-owned and connected until the task finishes.

    def submit(self, text: str, from_voice: bool = False):
        text = text.strip()
        if self._busy or not text:
            return
        if not self._authorise_owner("issue a JARVIS command", voice_command=from_voice):
            self._set_busy(False)
            return
        capability = self.owner_gate.issue_command_token(voice_command=from_voice)
        if capability is None:
            self._notice("Command denied: owner capability missing.")
            self._set_busy(False)
            return
        if self.wake_listener:
            self.wake_listener.stop()
        self.entry.clear()
        self._append("USER", text)
        self._request_started = time.monotonic()
        self._first_audio_latency = 0.0
        self._streamed_speech = False
        self._speech_muted = False
        self._request_cancel = threading.Event()
        self._request_capability = capability
        self._set_busy(True, "REASONING / PROCESSING REQUEST")
        self._run_task(
            lambda: self._execute_owner_request(text, capability, self._request_cancel),
            self._answer, self._fail_answer,
        )

    def _execute_owner_request(self, text: str, capability: str | None, cancel_event):
        # Thread-local capability is valid only inside this task, not globally
        # and not for requests started by other applications or speakers.
        try:
            with self.executor.authorised_request(capability, cancel_event=cancel_event):
                return self.agent.ask_stream(
                    text, lambda chunk: self.bridge.speech_sentence.emit(chunk),
                    cancel_event=cancel_event,
                )
        finally:
            self.owner_gate.revoke_command_token(capability)

    def _say(self, text: str):
        if (not self.config.voice_enabled or not text.strip() or
                (self.game_state.active and self.config.gaming_mute_speech)):
            return
        if self.wake_listener:
            self.wake_listener.stop()
            self.wake_listener = None
        self._speaking = True
        self.speaker.speak(text)

    @Slot(str)
    def _on_stream_sentence(self, sentence: str):
        if self._request_cancel is not None and self._request_cancel.is_set():
            return
        if (not self.config.voice_enabled or self._speech_muted or not sentence.strip()
                or (self.game_state.active and self.config.gaming_mute_speech)):
            return
        if not self._first_audio_latency and self._request_started:
            self._first_audio_latency = time.monotonic() - self._request_started
            self.response_speed.setText(
                f"FIRST SPEECH   {self._first_audio_latency:.1f} s"
            )
        if not self._streamed_speech:
            self._streamed_speech = True
            if self.wake_listener:
                self.wake_listener.stop()
                self.wake_listener = None
            self._speaking = True
            self.speaker.begin_stream(sentence)
        else:
            self.speaker.enqueue(sentence)

    def cancel_request(self):
        """Cancel model generation and pending actions, not only speech output."""
        if not self._busy or self._request_cancel is None:
            return
        self._request_cancel.set()
        self.owner_gate.revoke_command_token(self._request_capability)
        self.stop_speaking()
        self.state.setText("CANCELLING  /  WAITING FOR WORKER")
        self.cancel_task_button.setEnabled(False)

    def _finish_cancelled(self):
        self.speaker.interrupt()
        self._speaking = False
        self._request_cancel = None
        self._request_capability = None
        self._append("SYSTEM", "Request cancelled. Actions already completed cannot be undone.")
        self._set_busy(False)

    def stop_speaking(self):
        """Stop speaking immediately without cancelling an in-flight safe reply."""
        self._speech_muted = True
        self.speaker.interrupt()
        self._speaking = False
        if not self._busy and self.config.wake_enabled:
            self._start_wake()

    def _answer(self, answer):
        if self._request_cancel is not None and self._request_cancel.is_set():
            self._finish_cancelled()
            return
        self._request_cancel = None
        self._request_capability = None
        if self._request_started:
            elapsed = time.monotonic() - self._request_started
            self.response_speed.setText(f"ANSWER   {elapsed:.1f} s")
        self._append("JARVIS", str(answer))
        if self._streamed_speech and not self._speech_muted:
            self.speaker.end_stream()
        elif self.config.voice_enabled and not self._speech_muted:
            self._say(str(answer))
        self._set_busy(False)

    def _fail_answer(self, err):
        if (self._request_cancel is not None and self._request_cancel.is_set()) or "RequestCancelled" in str(err):
            self._finish_cancelled()
            return
        self._request_cancel = None
        self._request_capability = None
        if self._request_started:
            elapsed = time.monotonic() - self._request_started
            self.response_speed.setText(f"FAILED   {elapsed:.1f} s")
        self._append("SYSTEM", "Operation failed: " + err)
        if self._streamed_speech and not self._speech_muted:
            self.speaker.end_stream()
        self._set_busy(False)

    def _listen(self):
        if self._busy:
            return
        if self._speaking:
            self.stop_speaking()
        if self.wake_listener:
            self.wake_listener.stop()
        capture_cancel = threading.Event()
        self._request_cancel = capture_cancel
        self._request_capability = None
        self._set_busy(True, "MICROPHONE ACTIVE / SPEAK NOW")
        self.mic_status.setText("MICROPHONE: RECORDING")
        def capture_and_transcribe():
            wav = record_phrase(device=self.config.microphone_device,
                                cancel_event=capture_cancel)
            check_cancelled(capture_cancel)
            if self.config.provider == "openai":
                return transcribe(wav, self.agent._client(), self.config.transcription_model)
            wake_model = resolve_model(self.config.wake_model_path)
            if wake_model is None:
                wake_model = install_model()
            try:
                return transcribe_local(wav, str(wake_model))
            except Exception:
                if self.config.provider == "hybrid" and api_key():
                    return transcribe(wav, self.agent._client(), self.config.transcription_model)
                raise
        self._run_task(capture_and_transcribe, self._transcribed, self._listen_error)

    def _transcribed(self, text):
        self.mic_status.setText("MICROPHONE: OFF")
        if self._request_cancel is not None and self._request_cancel.is_set():
            self._finish_cancelled()
            return
        self._request_cancel = None
        # Do not restart the wake microphone between a transcript and its dispatch.
        if text.strip():
            self._busy = False
            self.submit(text, from_voice=True)
        else:
            self._append("SYSTEM", "No speech detected")
            self._set_busy(False)

    def _listen_error(self, err):
        self.mic_status.setText("MICROPHONE: OFF")
        if self._request_cancel is not None and self._request_cancel.is_set():
            self._finish_cancelled()
            return
        self._request_cancel = None
        self._append("SYSTEM", "Voice error: " + err)
        self._set_busy(False)

    def _approve(self, name: str, detail: str) -> bool:
        request = {"event": threading.Event(), "result": False}
        self.bridge.approval_requested.emit(name, detail, request)
        if not request["event"].wait(timeout=120):
            return False
        return bool(request["result"])

    @Slot(str, str, object)
    def _ask_approval(self, name, detail, request):
        try:
            self.showNormal(); self.raise_(); self.activateWindow()
            dialog = QMessageBox(self)
            dialog.setWindowTitle("JARVIS / ACTION APPROVAL")
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(f"JARVIS requests permission: {name}")
            dialog.setInformativeText(detail[:4000])
            dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dialog.setDefaultButton(QMessageBox.No)
            request["result"] = dialog.exec() == QMessageBox.Yes
        finally:
            request["event"].set()

    def _first_launch(self):
        answer = QMessageBox.question(
            self, "Welcome to JARVIS — offline first",
            "JARVIS can run locally without OpenAI credits.\n\n"
            "Enable an always-listening, OFFLINE microphone wake word ('Jarvis')? "
            "Microphone audio will be processed locally. You can switch this off in Settings.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        self.config.wake_enabled = answer == QMessageBox.Yes
        self.config.save()
        self._sync_mic_action()
        (data_dir() / "onboarding_complete.flag").write_text("1", encoding="utf-8")
        if self.config.wake_enabled:
            self._start_wake()
        self._append("SYSTEM", "Offline-first setup complete. Cloud API is optional; configure it in Settings if needed.")

    @Slot()
    def _on_speech_finished(self):
        self._speaking = False
        if not self._busy and self.config.wake_enabled:
            self._start_wake()

    def _sync_owner_visibility(self):
        """Prevent casual disclosure of chat while JARVIS owner gate is locked."""
        if hasattr(self, "conversation"):
            self.conversation.setVisible(self.owner_gate.authorised())

    def _authorise_owner(self, action: str, *, voice_command: bool = False) -> bool:
        if self.owner_gate.authorised(voice_command=voice_command):
            return True
        message = (
            "Voice identification is not yet installed. Enter your owner "
            "passphrase to " + action + "."
            if voice_command else "Enter your JARVIS owner passphrase to " + action + "."
        )
        phrase, ok = QInputDialog.getText(
            self, "JARVIS / OWNER VERIFICATION", message, QLineEdit.Password
        )
        if not ok or not self.owner_gate.unlock(phrase, voice_command=voice_command):
            self._notice("Owner authorisation denied. No private action executed.")
            self._sync_owner_visibility()
            return False
        self._sync_owner_visibility()
        return True

    def manage_owner_access(self):
        """Opt-in owner passphrase gate; NOT voice biometrics or Windows sign-in."""
        if not self.owner_gate.enrolled:
            consent = QMessageBox.question(
                self, "JARVIS / OWNER LOCK",
                "Create a JARVIS-only owner passphrase?\n\n"
                "This blocks unapproved JARVIS commands, but does not unlock or "
                "replace Windows sign-in. Voice commands will request the "
                "passphrase until separate speaker verification is developed.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if consent != QMessageBox.Yes:
                return
            phrase, ok = QInputDialog.getText(
                self, "Create owner passphrase",
                "Enter a unique passphrase of at least 12 characters:",
                QLineEdit.Password,
            )
            if not ok:
                return
            second, ok = QInputDialog.getText(
                self, "Confirm owner passphrase",
                "Re-enter the owner passphrase:", QLineEdit.Password,
            )
            if not ok or phrase != second:
                self._notice("Owner passphrase confirmation did not match.")
                return
            try:
                self.owner_gate.enrol(phrase)
                self._sync_owner_visibility()
                self._notice("Owner gate enabled. JARVIS commands now require confirmation.")
            except (ValueError, PermissionError, OSError) as exc:
                self._notice("Owner gate setup failed: " + str(exc))
            return
        phrase, ok = QInputDialog.getText(
            self, "JARVIS / OWNER LOCK",
            "Enter the current owner passphrase:", QLineEdit.Password,
        )
        if not ok or not self.owner_gate.unlock(phrase):
            self._notice("Owner verification denied.")
            return
        result = QMessageBox.question(
            self, "JARVIS / OWNER LOCK",
            "Owner verified.\n\nDisable the JARVIS-only passphrase gate? "
            "Choose No to leave it enabled and unlocked for five minutes.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            self.owner_gate.disable()
            self._sync_owner_visibility()
            self._notice("JARVIS owner gate disabled.")
        else:
            self._sync_owner_visibility()
            self._notice("JARVIS owner gate unlocked for five minutes.")

    def lock_owner_access(self):
        self.owner_gate.lock()
        self._sync_owner_visibility()
        self.stop_speaking()
        self._notice("JARVIS owner access locked.")

    def settings(self):
        if not self._authorise_owner("change JARVIS settings"):
            return
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            self.agent.client = None  # update API key and model
            self.toggle_voice(update_only=True)
            self.speaker.configure(engine=self.config.voice_engine,
                                   voice=self.config.voice_name, speed=self.config.voice_speed)
            self.agent.local_runtime.gaming_mode_enabled = self.config.gaming_mode_enabled
            self._refresh_gaming()
            self._start_wake()
            self._sync_mic_action()
            self._refresh_stats()
            self._append("SYSTEM", "Configuration saved. API keys and Google tokens are held in Windows Credential Manager when available.")

    def toggle_voice(self, update_only=False):
        if not update_only:
            if not self._authorise_owner("change spoken output"):
                return
            self.config.voice_enabled = not self.config.voice_enabled
            self.config.save()
        self.voice_button.setText("VOICE  ON" if self.config.voice_enabled else "VOICE  OFF")

    def clear_history(self):
        if not self._authorise_owner("clear your conversation history"):
            return
        if QMessageBox.question(self, "Clear local history", "Delete all local conversation history? Notes are retained.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.memory.clear_history()
            self.conversation.clear()
            self._append("SYSTEM", "Local conversation history cleared")

    def connect_google(self):
        if self._busy:
            return
        if not self._authorise_owner("connect a Google account"):
            return
        if not self.config.google_credentials_path:
            self._notice("Add your Google OAuth Desktop credentials file in Settings first")
            return
        self._set_busy(True, "GOOGLE OAUTH / AUTHORISE IN BROWSER")
        self._run_task(self.google.connect, lambda _: (self._append("SYSTEM", "Google connected"), self._set_busy(False)), self._fail_answer)

    def _start_wake(self):
        if self.wake_listener:
            self.wake_listener.stop()
            self.wake_listener = None
        if self._busy or self._speaking or not self.config.wake_enabled:
            return
        if self.game_state.active and self.config.gaming_pause_wake:
            self.mic_status.setText("MICROPHONE: PAUSED FOR GAME")
            return
        model = resolve_model(self.config.wake_model_path)
        if not model:
            if not self._installing_wake_model:
                self._installing_wake_model = True
                self.mic_status.setText("MICROPHONE: WAKE MODEL INSTALLING")
                self._append("SYSTEM", "Downloading and verifying the offline wake model automatically (about 40 MB). Push-to-talk remains available.")
                self._run_task(install_model, self._wake_model_installed, self._wake_model_failed)
            return
        self.wake_listener = WakeListener(
            str(model),
            lambda: self.bridge.wake_detected.emit(),
            lambda message: self.bridge.wake_error.emit(message),
            device=self.config.microphone_device,
        )
        self.wake_listener.start()
        self.mic_status.setText("MICROPHONE: LOCAL WAKE MODE")

    def _wake_model_installed(self, path):
        self._installing_wake_model = False
        self._append("SYSTEM", "Verified offline wake model installed successfully.")
        self._start_wake()

    def _wake_model_failed(self, err):
        self._installing_wake_model = False
        self.mic_status.setText("MICROPHONE: OFF — WAKE MODEL ERROR")
        self._notice("Wake model installation failed: " + str(err)[:180] + ". You can still use the LISTEN button; check your internet connection before retrying.")

    @Slot()
    def _on_wake(self):
        if not self._busy:
            self.showNormal(); self.raise_(); self.activateWindow()
            self._append("SYSTEM", "Wake phrase detected. Listening for your next command.")
            self._listen()

    @Slot(str)
    def _wake_error(self, text):
        self.mic_status.setText("MICROPHONE: UNAVAILABLE / RETRYING")
        self._append("SYSTEM", str(text)[:250] + "; retrying in 60 seconds")
        if self.config.wake_enabled and not self._quitting:
            QTimer.singleShot(60000, self._start_wake)

    def _notice(self, text):
        self._append("SYSTEM", text)
        if self.tray and self.tray.isVisible():
            self.tray.showMessage("JARVIS", text[:160], QSystemTrayIcon.Information, 4000)

    def _poll_reminders(self):
        if self.owner_gate.enrolled and not self.owner_gate.authorised():
            # Preserve pending reminders until private access is unlocked.
            return
        try:
            for item in self.memory.due_reminders():
                message = item["message"]
                self._append("SYSTEM", "REMINDER: " + message)
                if self.tray:
                    self.tray.showMessage("JARVIS REMINDER", message[:200], QSystemTrayIcon.Information, 10000)
                if self.config.voice_enabled and self.owner_gate.authorised():
                    self._say("Reminder. " + message)
        except Exception as exc:
            self._append("SYSTEM", "Reminder check failed: " + str(exc))

    def _refresh_gaming(self):
        new = (installed_game_running() if self.config.gaming_mode_enabled
               else GamingState(False))
        changed = new.active != self.game_state.active
        self.game_state = new
        if not hasattr(self, "game_status"):
            return
        self.game_status.setText(
            "GAMING: " + (new.title.upper() if new.active else "NORMAL")
        )
        if changed and new.active:
            if self.config.gaming_pause_wake and self.wake_listener:
                self.wake_listener.stop()
                self.wake_listener = None
                self.mic_status.setText("MICROPHONE: PAUSED FOR GAME")
            if self.config.gaming_mute_speech and self._speaking:
                self.stop_speaking()
            self._append("SYSTEM", "Gaming focus active: " + new.title)
        elif changed:
            self._append("SYSTEM", "Gaming focus ended; normal assistant restored.")
            if not self._busy:
                self._start_wake()

    def _refresh_stats(self):
        self._sync_owner_visibility()
        health = self.agent.local_runtime.status_snapshot()
        self.local_health.setText("LOCAL AI: " + health["state"].upper() +
                                  " · LOADS " + str(health["launches"]))
        try:
            import psutil
            self.cpu.setText(f"CPU   {psutil.cpu_percent():.0f} %")
            self.ram.setText(f"RAM   {psutil.virtual_memory().percent:.0f} %")
            battery = psutil.sensors_battery()
            self.batt.setText(f"BATTERY   {battery.percent:.0f} %" if battery else "BATTERY   AC / N/A")
        except Exception:
            pass
        self.clock.setText(datetime.now().strftime("%d %b %Y  •  %H:%M"))
        mode = getattr(self.config, "provider", "local")
        labels = {"local": "LOCAL / FREE", "hybrid": "HYBRID", "openai": "OPENAI / CLOUD"}
        self.api_status.setText("AI: " + labels.get(mode, "LOCAL") +
                                ("  •  CLOUD KEY SAVED" if api_key() else "  •  NO CLOUD KEY"))
        self.google_status.setText("GOOGLE: OAUTH READY" if self.config.google_credentials_path else "GOOGLE: NOT CONFIGURED")

    def _make_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        pix = QPixmap(64, 64); pix.fill(Qt.transparent)
        p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(CYAN), 5)); p.drawEllipse(7, 7, 50, 50)
        p.setFont(QFont("Segoe UI", 25, QFont.Bold)); p.drawText(pix.rect(), Qt.AlignCenter, "J")
        p.end()
        self.tray = QSystemTrayIcon(QIcon(pix), self)
        self.tray.setToolTip("JARVIS - Hybrid AI assistant")
        menu = QMenu()
        menu.addAction("Open JARVIS", self._show)
        menu.addAction("Listen", self._show_and_listen)
        menu.addAction("Stop speaking", self.stop_speaking)
        menu.addAction("Cancel current request", self.cancel_request)
        menu.addAction("Lock JARVIS owner access", self.lock_owner_access)
        self.mic_menu_action = menu.addAction("Mute wake microphone", self._toggle_wake_microphone)
        self._sync_mic_action()
        menu.addSeparator()
        menu.addAction("Quit JARVIS", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self._show() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _sync_mic_action(self):
        if hasattr(self, "mic_menu_action"):
            self.mic_menu_action.setText(
                "Mute wake microphone" if self.config.wake_enabled else "Enable wake microphone"
            )

    def _toggle_wake_microphone(self):
        if not self._authorise_owner("change microphone listening"):
            return
        self.config.wake_enabled = not self.config.wake_enabled
        self.config.save()
        self._sync_mic_action()
        if self.config.wake_enabled:
            self._start_wake()
            self._notice("Offline wake microphone enabled. Say Jarvis to activate.")
        else:
            if self.wake_listener:
                self.wake_listener.stop()
                self.wake_listener = None
            self.mic_status.setText("MICROPHONE: OFF")
            self._notice("Offline wake microphone disabled.")

    def _show(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def _show_and_listen(self):
        self._show()
        self._listen()

    def closeEvent(self, event):
        if not self._quitting and self.tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("JARVIS", "Running quietly in the system tray. Right-click for controls.",
                                  QSystemTrayIcon.Information, 3000)
        else:
            event.accept()

    def quit(self):
        if self.wake_listener:
            self.wake_listener.stop()
        self.speaker.stop()
        self.agent.close()
        self._quitting = True
        if self.tray:
            self.tray.hide()
        self.close()
        QApplication.quit()


def run():
    from PySide6.QtCore import QLockFile
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS Desktop")
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(data_dir() / "app-instance.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "JARVIS already running",
                                "JARVIS is already running in your system tray. "
                                "Open it from the JARVIS tray icon.")
        return
    window = JarvisWindow()
    restart = register_windows_restart(window.config.crash_restart_enabled)
    if window.config.crash_restart_enabled and not restart.registered and sys.platform == "win32":
        window._append("SYSTEM", "Windows crash recovery could not be registered.")
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        lock.unlock()
