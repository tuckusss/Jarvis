# JARVIS 0.8.0 desktop acceptance tests (not CI substitutes)

## Conversation interruption
- [ ] Cancel AI generation before first response; no late speech or visible answer
- [ ] Cancel between streamed sentences; speech stops and pending chunks drain
- [ ] Cancel while action approval dialog is open; no action executes afterward
- [ ] Cancel while microphone is listening; capture stops and no command runs
- [ ] Confirm actions committed BEFORE cancellation are reported as non-undoable
- [ ] Check timeout behavior on an intentionally slow cloud request and disable
      cloud mode if not authorised to transmit data

## Speech in real environments
- [ ] Compare quiet built-in laptop mic with USB headset and Bluetooth headset
- [ ] Test 0.5s noise-floor calibration, moderate gaming noise, quiet speaking
- [ ] Check truncated phrases, Vosk recognition accuracy and false wake-ups
- [ ] Verify microphone/headset reconnect after sleep and app restart
- [ ] Confirm nothing records while wake listening is disabled
- [ ] Measure first meaningful speech latency and total response time

## Reliability and consent
- [ ] Evaluate WER restart after an actual crash on a disposable test account
- [ ] Ensure normal Quit, uninstall or manual Windows shutdown does not loop
- [ ] Confirm model subprocess exits when JARVIS quits
- [ ] Confirm local AI health indicator does not start AI just to query health
- [ ] Install over v0.7 preserving user settings, owner lock, notes and reminders
- [ ] Confirm game mode continues to pause wake listening on CK3/Warband
- [ ] Validate signatures and Smart App Control without disabling OS protections
- [ ] Never claim true Windows voice unlock or biometric identity verification
