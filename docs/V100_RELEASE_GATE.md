# JARVIS v1.0 — production release gate

Current status: development candidate, not trusted public software.

## Automated Windows checks
- [ ] Every unit test passes, including real Windows DPAPI roundtrip
- [ ] Optional encrypted history is separate from plaintext legacy data
- [ ] Missing DPAPI keys never cause fallback to plaintext
- [ ] Migration needs owner consent, copies once and rolls back on error
- [ ] Old files and backups remain clearly disclosed; no false encryption claims
- [ ] Packaged EXE and installed EXE run secure-history smoke checks
- [ ] Packaged Settings UI, offline neural TTS, local AI, install and uninstall work
- [ ] Development installer clearly reports NotSigned rather than trusted
- [ ] Stable channel rejects missing PFX/approved managed signing identity
- [ ] Stable channel verifies Authenticode publisher and SHA256 hashes

## Hands-on Windows device validation
- [ ] Microphone capture, accents and background-noise recognition tested
- [ ] No artificial voice cloning or replay resistance is claimed without testing
- [ ] Stop/cancel during model startup and actions behaves as designed
- [ ] Lock, sleep, reboot, headset reconnect and owner gate are tested
- [ ] Encrypted database reopens after an ordinary password change
- [ ] DPAPI recovery process covers profile loss and administrator reset
- [ ] Original Windows Hello/PIN/password stays enabled and works
- [ ] Signing is verified using SignTool /pa and target Windows certificate trust
- [ ] Smart App Control works without disabling OS security protections
- [ ] Upgrade from v0.9 and rollback tested using a disposable Windows VM

## Not included by this developer candidate
- Enrolled-speaker voice biometrics with anti-spoof thresholds
- Native Windows Credential Provider or voice-based lock-screen unlock
- A signed autonomous updater, complete background-service separation,
  live PayCore/Freedom Homes backend connectors or arbitrary agent control
- Cryptographic erasure of legacy SQLite pages, WAL files, backups or SSD remnants

Microsoft reference documentation:
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- https://learn.microsoft.com/en-us/windows/win32/seccrypto/using-signtool-to-verify-a-file-signature
- https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control
