"""Google OAuth Desktop integration. Tokens are held in the OS credential manager."""
from __future__ import annotations
import base64
from datetime import datetime, timezone
from email.mime.text import MIMEText
import hashlib
import json
from pathlib import Path

READ_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]
WRITE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleConnector:
    def __init__(self, config):
        self.config = config

    def _scopes(self) -> list[str]:
        return READ_SCOPES + (WRITE_SCOPES if self.config.google_write_enabled else [])

    def _account(self):
        digest = hashlib.sha256("|".join(self._scopes()).encode()).hexdigest()[:16]
        return "google_oauth_" + digest

    def _credentials(self, interactive: bool = False):
        import keyring
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        name = self._account()
        saved = keyring.get_password("JARVIS-Desktop", name)
        creds = Credentials.from_authorized_user_info(json.loads(saved), self._scopes()) if saved else None
        if creds and not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if (not creds or not creds.valid) and interactive:
            path = Path(self.config.google_credentials_path).expanduser()
            if not path.is_file():
                raise RuntimeError("Choose a Google Desktop OAuth credentials.json file in Settings first")
            flow = InstalledAppFlow.from_client_secrets_file(str(path), self._scopes())
            creds = flow.run_local_server(port=0, open_browser=True)
        if not creds or not creds.valid:
            raise RuntimeError("Google not connected. Use Settings → Connect Google first")
        keyring.set_password("JARVIS-Desktop", name, creds.to_json())
        return creds

    def connect(self) -> None:
        self._credentials(interactive=True)

    def messages(self, count: int = 8) -> list[dict]:
        from googleapiclient.discovery import build
        svc = build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)
        ids = svc.users().messages().list(userId="me", maxResults=min(count, 15), labelIds=["INBOX"]).execute().get("messages", [])
        out = []
        for m in ids:
            msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            out.append({"from": headers.get("from", ""), "subject": headers.get("subject", ""),
                        "date": headers.get("date", ""), "snippet": msg.get("snippet", "")[:180]})
        return out

    def events(self, count: int = 10) -> list[dict]:
        from googleapiclient.discovery import build
        svc = build("calendar", "v3", credentials=self._credentials(), cache_discovery=False)
        now = datetime.now(timezone.utc).isoformat()
        events = svc.events().list(calendarId="primary", timeMin=now, maxResults=min(count, 20),
                                   singleEvents=True, orderBy="startTime").execute().get("items", [])
        return [{"start": x.get("start", {}).get("dateTime", x.get("start", {}).get("date")),
                 "summary": x.get("summary", "(untitled)"), "location": x.get("location", "")}
                for x in events]

    def send_mail(self, to: str, subject: str, body: str) -> dict:
        if not self.config.google_write_enabled:
            raise PermissionError("Enable Google write access in Settings first")
        from googleapiclient.discovery import build
        svc = build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)
        m = MIMEText(body, "plain", "utf-8")
        m["To"], m["Subject"] = to, subject
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode("ascii")
        res = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"status": "sent", "id": res.get("id", "")}

    def create_event(self, summary: str, start: str, end: str, description: str = "") -> dict:
        if not self.config.google_write_enabled:
            raise PermissionError("Enable Google write access in Settings first")
        from googleapiclient.discovery import build
        # Only aware datetimes, no ambiguous local clock times.
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if a.tzinfo is None or b.tzinfo is None or b <= a:
            raise ValueError("Start/end require timezone offsets and end must be later")
        svc = build("calendar", "v3", credentials=self._credentials(), cache_discovery=False)
        res = svc.events().insert(calendarId="primary", body={"summary": summary,
            "description": description, "start": {"dateTime": start}, "end": {"dateTime": end}}).execute()
        return {"status": "created", "url": res.get("htmlLink", "")}
