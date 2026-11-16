# JARVIS v0.6.1 engineering branch — release validation

Last successful developer Windows installer: v0.5, GitHub Actions build #2.
v0.6 CI build #3 failed during packaged import-check.
Follow-up CI build #4 captured the precise error:
FileNotFoundError language_tags/data/json/index.json, a transitive phonemizer/Kokoro dependency.

v0.6.1 changes:
- Bundle language_tags, segments, csvw and clldutils data needed by Kokoro.
- Diagnostic traceback capture for packaged Windows checks.
- Stream complete sentences from local AI to Kokoro TTS; add Stop Speaking and answer latency telemetry.
- Optional owner passphrase authentication for JARVIS actions. Voice-command owner confirmation is required every time when enabled. This is NOT biometric identification or Windows unlock.
- Local searchable chat excerpts behind approval and a guarded workstation LOCK operation.
- New unit tests for streaming and owner authorization. Native Windows audio/hardware and anti-spoofing tests are still required.

The main branch must not be described as ready until GitHub Actions finishes build, package check, install, offline inference, voice synthesis and uninstall tests. Draft installer is unsigned unless a valid publisher signing credential is configured.

## Voice compatibility discovered in CI
The packaged neural voice synthesized only after the missing phonemizer data was included; then kokoro-onnx 0.5.0 raised ONNX tensor(int32) versus tensor(float) while reading the pinned model-files-v1.1 ONNX model. Bump pinned kokoro-onnx to 0.6.1, which supports the model's speed input type. Validate real audio generation through CI before release.
