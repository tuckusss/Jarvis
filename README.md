# JARVIS Desktop for Windows — Offline-first Hybrid Assistant (v0.5.0)

**Distribution target:** One Windows 10/11 x64 setup EXE, containing the complete desktop application, Python runtime, offline speech model, CPU inference engine, and offline language model. End users need **neither Python, Ollama, PowerShell, model folders, nor an OpenAI API key**. This repository/ZIP is a **build project**, not the finished EXE; no signed Windows installer has been compiled or hardware-tested in this Linux build environment.

## Install experience for end users (once built and signed)

1. Download `JARVIS-Setup-0.5.0-x64.exe`, double-click, and choose Install. The bundled installer may be **over 1 GB** because it includes Qwen model weights.
2. Choose whether JARVIS should launch with Windows (offered as an installer task; enabled by default and can be unchecked). A desktop shortcut is optional.
3. On first launch, permit or decline continuous **offline wake-word microphone listening**. Say **“Jarvis”**, pause, then speak your command. The mic can be muted via the tray icon or Settings.
4. JARVIS can answer general queries using the bundled Qwen2.5 1.5B Instruct Q4_K_M language model and its private, loopback-only llama.cpp CPU server. No paid API, Ollama process, or separate model downloads are required. Expect slower and less capable responses than large cloud models, particularly on older PCs.
5. Optional: in **Settings → AI provider**, select **Hybrid** (local first, OpenAI if local fails and user has added a key) or **OpenAI** (cloud). Add your own API key to Windows Credential Manager and test it. **There is no default key** in the installer. Cloud models and Google services require internet access, user credentials and provider billing where applicable.
6. Optional Gmail/Calendar access requires separately configured Google OAuth Desktop credentials and per-action confirmation for any send/write. The local app does not automatically acquire access to anyone's accounts.

On window close, JARVIS remains in the system tray, including wake listening if enabled. On sign-in it starts automatically if the installer startup option was selected. It does not keep listening if Windows is shut down, asleep, or the user is signed out. Only one JARVIS instance may run per Windows user.

## Features and security

- Animated Qt HUD, system telemetry, typed chat, system tray, optional launch-on-login.
- Offline Vosk wake-word detection and general spoken-command transcription, using a bundled model. Windows SAPI speech replies, free of OpenAI credits.
- Offline local Qwen/llama.cpp inference; local, hybrid and OpenAI provider modes (local default; **no automatic cloud use without explicit Hybrid or OpenAI selection**).
- Fixed tool allowlist, deterministic common Windows commands, HTTPS bookmarks, scoped file searches, SQLite notes/chat history, reminders, Gmail and Calendar (after user OAuth).
- Sensitive actions including sending messages, creating events, reading file contents and capturing screenshots require explicit approval. Cloud vision requires a configured cloud model and confirmation. No arbitrary command-line execution or unattended desktop takeover is offered.
- `llama-server.exe` is spawned as a child process only while JARVIS runs, on `127.0.0.1` with a random per-session bearer token. It doesn't listen on the LAN. Its model and speech models are installed with the app (not downloaded by end users).
- API credentials and OAuth tokens use Windows Credential Manager. Persistent conversations and configuration remain in `%LOCALAPPDATA%\JarvisLocal` across upgrades. Screenshots are captured only on request. The offline model has no implicit web browsing capability.

**Scope limits:** The bundled ~1.5B model is a compact offline assistant, not a frontier model. Tool-selection reliability varies; deterministic common commands work without model inference. It does not independently understand arbitrary screens offline, control third-party services without consent, or perform unrestricted GUI automation. Only Windows x64 is covered by the included builder. CPU/RAM, mic, local audio permissions, Windows Smart App Control and antivirus differ across PCs; validate on clean Windows machines before sharing broadly. Recommend at least **8 GB RAM**, with more for multitasking.

## Build the single EXE (maintainer only)

### Recommended: GitHub Actions Windows runner

1. Create a private GitHub repository, upload source contents (not any API credentials, OAuth secrets, certificates, or personal database files).
2. Use **Actions → Build, install-test and stage JARVIS Windows Setup → Run workflow**. It builds on Windows 2022 with Python 3.12 and Inno Setup; runs tests; downloads SHA256-pinned Vosk, llama.cpp Windows CPU binary and Qwen GGUF model; bundles them with PyInstaller and Inno Setup; installs the actual setup package to the runner, checks import/model payload and offline inference, and tests uninstallation. It then creates a **private DRAFT GitHub release** containing the single EXE (not an Actions artifact, which may exceed free storage quotas).
3. Download `JARVIS-Setup-0.5.0-x64.exe` from the private **draft release** created by the successful workflow. It is still a developer candidate, not a publicly signed or hardware-certified product.
4. Before public distribution, sign all shipped unsigned EXE/DLL/PYD and the setup/uninstaller with a **trusted code-signing certificate**, then test on Windows 10/11 with Smart App Control. A self-signed cert or unsigned build may be blocked. `JARVIS_SIGNING_PFX_BASE64` and `JARVIS_SIGNING_PASSWORD` are supported CI secrets (never commit them). Publishing is **not** complete until Windows testing and trusted signing are done.

### Build manually on a developer Windows machine

Install Python 3.12 and Inno Setup 6 **on the developer/build PC only**, then double-click `BUILD_INSTALLER.bat` or invoke `packaging/build_installer.ps1`. The completed installer is created in `dist\JARVIS-Setup-0.5.0-x64.exe` if all checks pass. Inno Setup defaults to per-user installation under `%LOCALAPPDATA%\Programs\JARVIS Desktop` and supports uninstallation through Windows Installed Apps.

### Offline asset provenance (SHA-256 pinned in packaging scripts)

- [Qwen/Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/qwen2.5-1.5b-instruct-q4_k_m.gguf), Q4_K_M GGUF, Apache 2.0, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, ~1.12 GB.
- [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/releases/tag/b12336) Windows CPU x64 ZIP, MIT, SHA-256 `e6734b9a11bc8b0b525922c49ce334fb6565d84df3786acb7d77b3e0a9acf4a3`.
- [Vosk small English model 0.15](https://alphacephei.com/vosk/models), SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498` (ZIP).

The build **aborts** if expected downloads are missing or corrupt. Licenses for the bundled Qwen and llama.cpp components are downloaded into `licenses` in the installed app; a production release should additionally verify all third-party dependency attribution and license obligations. Updating a binary or model requires updating its pinned hash after independent verification.

## Developer mode (source checkout only)

Developers may use `DEV_START_FROM_SOURCE.bat` with Python 3.12. This source ZIP intentionally omits the ~1.12 GB offline model and Windows CPU inference binaries; the source app's offline LLM won't start until the build-time payload is obtained and bundled. The Vosk model can be installed automatically if missing, but the **end-user EXE** must contain both models already. Offline deterministic commands and memory tests work without the binary files.

Run tests: `python -m unittest discover -s tests -v`.

## Launch smoke tests required before public release

1. Fresh Windows 10 x64, Windows 11 x64; test default installation, uninstallation and no separate Python/Ollama dependency.
2. Clean Windows 11 with Smart App Control on; verify valid publisher signature and allowlisting.
3. No internet and **no OpenAI API key**: say "Jarvis" → "open Notepad"; check a general offline Q&A; listen for SAPI reply; mute mic from tray.
4. Restart computer and verify user-selected launch-on-login; close dashboard and verify the background tray microphone.
5. Suspend/resume laptop, unplug headset, change sound devices, retry wake listener, and check no busy-loop or false wake on voice playback.
6. Test 8 GB RAM and a low-end CPU; time the startup and first local response; verify local AI process shuts down on Quit.
7. Test consent denials, Gmail read/write scopes, private-file protection, cancellation and no cloud egress in Local mode.

Official references: [Windows Smart App Control signing](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control), [PyInstaller](https://pyinstaller.org/en/latest/), [Inno Setup](https://jrsoftware.org/).

## Explicit release boundary (2026-11-14)

The only artifact generated in this Linux session is source/build configuration. The requested end-user single EXE **does not exist yet**; it requires a real Windows build. This release pipeline now **fails closed** unless it can compile, bundle, install, run offline inference, and uninstall on the Windows runner. A successful Windows CI run is not sufficient proof of microphone quality, Smart App Control acceptance, or general hardware reliability.

Do not distribute an unsigned draft candidate to the public. Smart App Control can block unsigned applications; publishing a generally trusted installer requires a real publisher signing identity and valid signatures. Code signing is separate from building the EXE.
