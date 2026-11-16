# JARVIS 0.7.0 — hands-on release acceptance checklist

Automated GitHub Windows CI is necessary but does not prove actual audio,
security, user-experience or game performance. Test on an authorised Windows
10/11 laptop only, without disabling Windows Smart App Control or antivirus.

## Installer and recovery
- [ ] Installer carries a valid trusted digital signature on all shipped
      application binaries, the setup and uninstaller.
- [ ] Install over v0.6.1 without losing JARVIS config, notes or reminders.
- [ ] Clean install and uninstall pass on both Windows 10/11.
- [ ] Launch after reboot and recover from sleep, headset unplugging and crash.
- [ ] Windows Hello or original Windows login always remains available.

## Voice and owner permissions
- [ ] Choose correct USB headset/microphone in Settings; test level locally.
- [ ] Offline wake word works while idle and pauses when a game is detected.
- [ ] Plain offline replies stream and interrupt cleanly without double speech.
- [ ] All commands, quick actions and tool executions fail closed while owner
      gate is enrolled and locked.
- [ ] Typed requests accept a five-minute passphrase session; voice requests
      require per-request verification until actual speaker biometrics exist.
- [ ] Passphrase wrong attempts, lockout, restart and expiry tested.
- [ ] Admin/process control on an already logged-on Windows user is outside
      JARVIS's security boundary. Do not treat the owner gate as OS protection.

## Gaming and projects
- [ ] CK3 detection engages gaming mode and releases it after game exit.
- [ ] Warband detection engages similarly, with no game memory access.
- [ ] Measure game frame time and JARVIS CPU/RAM before and during local AI.
- [ ] No automatic microphone, speech or background-task interruptions
      contrary to the owner's selected gaming settings.
- [ ] PayCore Desktop folder opens only when it exists.
- [ ] JARVIS_STATUS.md reads only after approval, correctly identifies
      manually maintained content and does not invent live business data.
- [ ] No automatic trades, payments, mail sends or data exports.

## Final blockers
- [ ] End-user feedback confirms speech naturalness and no choppiness.
- [ ] Real speaker verifier and adversarial replay/synthesis tests completed
      before marketing any registered-voice access control.
- [ ] No Windows unlock without independently reviewed native Credential
      Provider integration and strong account recovery.
