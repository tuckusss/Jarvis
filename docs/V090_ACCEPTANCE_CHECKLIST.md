# JARVIS v0.9 — private memory acceptance

## Build and migration
- [ ] All Windows tests pass, including real DPAPI encryption and decryption
- [ ] Packaged + installed EXE can save, search and delete encrypted test notes
- [ ] Upgrade preserves v0.8 settings, old messages, notes and reminders
- [ ] No legacy message/notes data is silently migrated or deleted

## Privacy and authorisation
- [ ] Private vault initially disabled until explicitly selected in Settings
- [ ] Encrypted note body is never present in vault SQLite plaintext
- [ ] Project name and time metadata are disclosed in SQLite
- [ ] No same-user malware/security guarantee is claimed
- [ ] Unrecognised project and wrong note ID are rejected
- [ ] Denied prompts save/read/delete nothing
- [ ] Cancelling a request before tool execution denies the action
- [ ] "Remember for PayCore:" and "Search PayCore notes about" never send
      private text to cloud or save it to the legacy chat table
- [ ] Project brief says NOT LIVE, uses only explicitly permitted local inputs
- [ ] Backup remains DPAPI ciphertext and is not portable to other Windows users
- [ ] User can disable private note access without erasing existing ciphertext

## Real laptop tests
- [ ] Test current Windows user login, reboot, lock/unlock and sleep/resume
- [ ] Test failure when DPAPI is unavailable: no plaintext fallback
- [ ] Test install/uninstall preserves existing private vault database
- [ ] Test voice command with headset and offline neural response
- [ ] Confirm Smart App Control and trusted binary signature separately

## For v1.0, not v0.9
- [ ] Encrypted legacy chat migration with backups and rollback
- [ ] Speaker-biometric verification and spoof/replay testing
- [ ] Sign application, installer and updater; rollback and security review
- [ ] Validated native Windows sign-in Credential Provider, if pursued
