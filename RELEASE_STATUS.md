# JARVIS v0.6.0 — voice improvement development candidate

Prior build #2 of JARVIS v0.5 compiled and passed unattended Windows installation, local AI response, and uninstallation tests. Real user testing then identified choppy synthetic voice quality and slow response latency.

v0.6 changes on the voice-latency branch:
- Bundled, SHA256-pinned offline Kokoro neural TTS with British George voice by default (MIT engine, Apache-2.0 model).
- Selectable voice and speed in Settings, with Windows speech fallback.
- Shorter conversational LLM completions, lighter prompts when tools are unnecessary, background local model prewarm.
- Quicker microphone end-of-speech detection and lower priority local LLM process to reserve audio CPU headroom.
- New Windows CI check to synthesize British offline speech from the packaged model without audio output hardware.

This candidate is NOT verified or published until Windows CI passes on main. Unattended CI does not prove subjective voice quality. A listening test on the user's Windows laptop is essential. The new installer may still be unsigned and blocked by Smart App Control; obtain a trusted code-signing certificate before distributing.
