# JARVIS v1.0.0 — security and distribution candidate

Base: JARVIS v0.9 Build #25 passed all Windows automated checks.
Branch: jarvis-v100-secure-release. Keep draft and do not publish stable.

### Built
- Explicitly opted-in Windows CurrentUser DPAPI encryption for NEW ordinary
  chats, notes and reminders in a separate SQLite database.
- Owner-confirmed legacy database migration with all-or-nothing copy. Original
  unencrypted jarvis.db is retained; data deletion is NEVER automatic.
- Fail-closed startup if encryption was requested but cannot initialise.
- Windows build channel: DEVELOPMENT permits unsigned draft only. STABLE
  requires signing certificate + expected publisher identity; verify-release
  checks trusted Authenticode status and records SHA256 executable hashes.
- Packaged Windows smoke tests exercise DPAPI encrypted chat, explicit
  migration, neural speech, local inference, Qt Settings, silent setup and
  uninstallation.

### Still outstanding before the name v1.0 means released
- Trusted publisher signing credentials (not supplied to this repository).
- Physical Windows 10/11 laptop audio and owner permission acceptance.
- Independently validated biometric speaker identification and robust
  anti-spoofing (not part of current executable).
- True Windows voice unlock requires native, reviewed Credential Provider
  plus existing Windows login recovery. Never store/auto-type Windows PIN.
- Legacy plaintext file/backup/SSD remnants need explicit privacy handling.
- Long-term worker separation, safe signed updater and rollback are not
  represented as complete.
- Manual test of Smart App Control, code signing, install/upgrade/recovery.
