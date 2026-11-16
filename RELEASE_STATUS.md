# JARVIS v0.8.0 — development candidate (not a final release)

Source base: successful v0.7 Windows Build #16, branch jarvis-v070-core.
Current source branch: jarvis-v080-conversation-recovery.
Do not merge into main or publish as a trusted installer without CI + real
Windows desktop and audio checks.

Changes:
1. Cooperative cancellation and dedicated Cancel Request HUD/tray controls.
   The UI keeps its background worker busy until it exits; cancellation
   revokes action capabilities and prevents subsequent tool dispatch.
2. Streamed local and cloud responses recheck cancellation before any tool;
   hybrid mode never falls back to cloud for a cancelled offline task.
3. Offline speech capture uses local adaptive energy-based endpointing,
   0.5-second ambient calibration and short pre-roll, with cancellable
   microphone reads. No new voice model or upload added.
4. Optional Windows Error Reporting application restart registration. This
   is NOT a crash-resilient independent background service.
5. Non-blocking local AI process-state and restart-count display in HUD.
6. Regression tests cover streaming cancellation, approval races, ambient
   audio calibration, process status and OS restart registration.

Not implemented at v0.8:
- True full-duplex speaking-over-the-assistant with acoustic echo cancellation.
- Enrolled voice biometrics, replay/liveness defense or Windows unlock.
- A separate resilient background service, GPU acceleration and autonomous
  multi-app workflow execution.
- Encrypted searchable document memory, signed rollback updates or connected
  PayCore/Freedom Homes backend operations.

Security: The JARVIS owner passphrase gate is not an OS authentication
factor. Do not store Windows credentials or auto-type them after speech.
Windows Hello/PIN must remain available. A completed external action cannot
be reversed by pressing Cancel.
