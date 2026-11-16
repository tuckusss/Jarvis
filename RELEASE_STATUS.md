# JARVIS v0.7.0 — engineering release candidate

Base: v0.6.1, successful Windows GitHub Actions build #8.
Development branch: jarvis-v070-core. Draft pull request #5.
Automated fast Windows tests: 68 passed on Build #9. Full installer results
must be verified separately before declaring v0.7 ready.

Implemented:
- Short-lived per-command owner capabilities enforced in ToolExecutor, including
  independent worker isolation and revocation on lock or task completion.
- Automatically detected CK3 / Mount & Blade: Warband gaming focus with optional
  wake microphone and speech pause; two-thread limit when local CPU model starts
  while game is already running.
- Microphone device selection and user-initiated half-second RMS test.
- Explicit streamed speech sessions to avoid premature wake listening.
- Permissioned, read-only local JARVIS_STATUS.md from configured project folders;
  default PayCore Desktop folder only, not live remote business data.
- Manual, official stable GitHub release discovery without self-update.
- New tests for permission boundaries, gaming, audio input, project workspace and
  release selection.

Not implemented or not yet validated:
- Real speaker identification, anti-replay/AI voice clone resistance and genuine
  Windows lock-screen sign-in. Current owner gate is a passphrase, not biometrics.
- Separate background service and GPU inference.
- Windows acoustic/mic, UI, sleep-resume and gaming tests on the owner's laptop.
- Code signing and Smart App Control acceptance. The developer EXE is unsigned
  unless configured with an actual publisher certificate.
- Real PayCore/Freedom Homes connected reports, sales, automation and controls.

Do not publish draft release to end users or change Windows sign-in until the
distinct tests, signed distribution and recovery procedures are complete.
