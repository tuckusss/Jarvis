# JARVIS v0.5.0 release status — 2026-11-14

- Source and offline-first prototype exist; Python compile and 24 automated core tests pass on Linux.
- The Windows release pipeline has been upgraded to build the actual setup, SILENTLY INSTALL it, verify bundled imports and offline local model inference, and UNINSTALL it before staging a candidate.
- Successful builds go to a PRIVATE DRAFT GitHub release, not to the default Actions artifact storage which may be too small for the model payload.
- No Windows CI run was executed from this environment, no final EXE exists here, and no real Windows mic/voice/GUI testing was possible.
- No trusted code signing certificate is present. Smart App Control compatibility is not verified.
- Publishing to anyone as a finished app requires a connected Windows build system (GitHub or other CI), successful build and install tests, hands-free audio/hardware testing, and trusted code signing.
- The installed user needs no manual Python, Ollama, model folder, or mandatory OpenAI API key when the full setup is produced.

Do not give source ZIPs to end users as if they were finished installers.
