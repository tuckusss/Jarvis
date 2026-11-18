# JARVIS v0.9.0 — private project memory development candidate

Source base: v0.8 Windows CI build #22 succeeded.
Branch: jarvis-v090-private-memory.
Developer release and current Windows CI: verify the latest GitHub Actions run.

Scope implemented:
- Opt-in DPAPI CurrentUser encrypted project note vault, separate SQLite DB.
- Encrypted save/search/delete/backup tools behind owner approval, with
  bounded search, exact project scope and fail-closed encryption.
- Local-only deterministic voice/text commands for encrypted notes; no cloud
  model forwarding and no legacy plaintext chat-history persistence.
- Read-only project brief built from encrypted notes, reminders and an
  explicitly user-maintained JARVIS_STATUS.md, with source labels.
- Windows installer smoke check performs a real DPAPI roundtrip and verifies
  that encrypted data was not accidentally stored in plaintext.
- Unit tests for project scoping, deletion, approval, privacy, backup,
  cloud isolation and encrypted storage.

Boundaries:
- Legacy history/notes/reminders/audit are NOT encrypted or migrated.
- The current Windows user/administrator or malware in the same session
  may still access data or decrypt it. This is not Windows sign-in security.
- No biometric registered speaker or actual Windows unlock.
- No live PayCore or Freedom Homes data sync, agent swarms, arbitrary PC
  automation, independent Windows background service or signed updater.
- Hardware testing and trusted code signing required before public release.
