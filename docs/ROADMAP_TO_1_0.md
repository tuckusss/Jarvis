# Roadmap to JARVIS v1.0 — ship one release at a time

## v0.8 — CURRENT
- Cancel requests without allowing later tools to execute
- Improve local speech endpoint capture and real-world voice performance
- Add transparent core-health reporting and bounded Windows crash restart
- Pass Windows packaging + full integration smoke checks
- Get real laptop audio and user feedback before the next release

## v0.9 — CURRENT: PRIVATE MEMORY, NOT FULL MEMORY MIGRATION
- Opt-in Windows DPAPI project notes, delete and same-profile encrypted backup
- Separate worker from dashboard with explicit OS authorization boundaries
- Trusted application planning and permissioned read-only desktop/screen tools
- More robust audio pipeline (evaluate neural VAD / echo cancellation)
- Better CPU/GPU detection and hardware-qualified model choice
- Read-only authorised PayCore and Freedom Homes integrations

## v1.0 — FUTURE, NOT IMPLEMENTED
- Signed application, installer and updater with safe rollback
- Independent security review of voice biometrics, anti-spoofing and account recovery
- Multi-device performance, sleep/restart, error injection and security test matrix
- Stable supervised workflows with approve/deny and detailed audit
- **Windows unlock** requires a separately reviewed native Windows Credential
  Provider and strong fallback factor; never bypass or auto-type a password.
- Public distribution only after actual publisher trust validation

Research foundations:
- Microsoft application restart/recovery:
  https://learn.microsoft.com/en-us/windows/win32/recovery/registering-for-application-restart
- Microsoft per-user DPAPI:
  https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- llama.cpp inference health and model resources:
  https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Silero VAD (future evaluation only):
  https://github.com/snakers4/silero-vad
