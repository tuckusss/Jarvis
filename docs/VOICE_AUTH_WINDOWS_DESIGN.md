# JARVIS owner-only voice access and Windows sign-in architecture

**Status: DESIGN ONLY — NOT IMPLEMENTED.** This document is not a functioning
Windows unlock mechanism. It must not be represented as one.

## Objective and security boundary

Two separate controls must be designed and validated:

1. **JARVIS application authorization:** Only enrolled, verified users can
   issue JARVIS commands (particularly PC-control, files, and connected-app
   operations). This can run inside the existing Python application.
2. **Real Windows workstation unlock:** An actual locked Windows 10/11
   workstation may only be unlocked by the Windows authentication subsystem.
   JARVIS running in a regular user session cannot unlock the secure Windows
   sign-in desktop. A native Windows Credential Provider and properly supported
   authentication mechanism would be a separate, signed security component.

Windows Hello does not currently list voice as a built-in sign-in method;
its standard methods are face, fingerprint, and PIN.

Microsoft reference: https://learn.microsoft.com/en-us/windows/win32/secauthn/credential-providers-in-windows

## Recommended secure experience

- Owner first signs into Windows using Windows Hello or another accepted
  system sign-in method.
- Owner explicitly enrolls their voice inside JARVIS. Collect several
  minutes of varied phrases in a quiet and a mildly noisy environment,
  with consent and a clear delete/reset procedure.
- Enrollment requires Windows Hello re-verification and stores only
  necessary, encrypted speaker embeddings locally, never cloud recordings
  or a Windows password/PIN.
- The wake word "Jarvis" is a convenience signal, **not authentication**.
- When JARVIS hears a command, it checks the voice against the enrolled
  owner. Unverified commands are ignored or receive a generic denial.
- The owner may require a fresh, randomized spoken challenge for sensitive
  requests. A spoken challenge is replay-resistant only to the extent its
  liveness and anti-synthesis measures are effective.
- High-impact operations (sending email, reading private files, changing
  settings, Windows controls, revealing data, executing external actions)
  must STILL require explicit user authorization. Speaker verification
  does not replace these permissions or Windows Hello.
- If speaker-verification models fail, samples are noisy, microphone is
  disconnected or the threshold cannot be met, the system FAILS CLOSED.
- Only a verified Windows login session may enroll or reset a voice
  profile. Never permit unknown speakers to enroll through wake word.
- JARVIS must not claim it locked Windows account access. Files and
  other apps still follow Windows permissions, not JARVIS decisions.

## Windows sign-in / unlock track — separate native project

Windows unlock requires more than registering a voice in Python:
- A code-signed, **native custom Windows Credential Provider** integrated
  with Windows Logon UI, with a proper authentication package or
  server-backed Windows-supported credential exchange.
- A pre-logon microphone capture path proven to work on Windows 10/11.
  User-session microphone permissions/availability cannot be presumed
  to work in LogonUI.
- Voice detection, speaker identification, anti-spoofing and randomized
  liveness challenge before authentication submission.
- Strong recovery access via an unchanged built-in Windows system
  credential provider such as Hello PIN, password or another available
  Windows-supported method.
- Proper security review, account lockout throttling, audit logs,
  error handling, deployment/revocation, installer signing, upgrade
  migration and offline-operation requirements.
- NEVER store, recover, paste, auto-type, or auto-submit the user's
  Windows password or PIN from a JARVIS-accessible file, registry key
  or reversible encrypted blob. Do not attempt to use a user-mode
  process to bypass the secure desktop.
- The credential provider merely collects/serializes sign-in credentials.
  Authentication and permission enforcement remain with Windows LSA.
- Keep standard credential providers enabled. Test in a snapshot-able
  disposable virtual machine before deployment to the owner's PC.

Microsoft reference:
https://learn.microsoft.com/en-us/windows/win32/secauthn/credential-providers-in-windows

## Threat model

- A phone playing a recording of the owner's speech.
- An AI-cloned voice reading a challenge or arbitrary commands.
- An imitator speaking the wake word and known phrases.
- Background TV/loudspeaker triggering the wake listener.
- Previously authenticated voice replayed from another application.
- Local untrusted processes attempting to call the command dispatcher.
- Malware/administrator already in control of the Windows session.
- Device asleep, disconnected microphone, service crashes, Windows updates.
- Biometric template theft and cross-device replay.

Reference: UK National Cyber Security Centre:
https://www.ncsc.gov.uk/collection/biometrics/speaker-recognition

**Voice recognition by itself cannot ensure that nobody else can access the computer.**
The OS sign-in boundary and device encryption remain essential.

## Implementation phases

### Phase A — JARVIS authorization (doable in current app)

- User consent and local voice enrollment wizard.
- Offline speaker embedding inference model (trained for speaker verification,
  distinct from Vosk speech-to-text/wake model).
- Enrollment-template storage with Windows DPAPI, owner SID binding, explicit
  deletion/export rules, and no raw audio retention by default.
- Per-command verification before dispatch to local or cloud models.
- Pre-execution verification on every action, not only on the wake event.
- Voice-auth session TTL, repeated mismatches lockout, generic denial,
  sensitive-operation confirmations and auditable deny/allow results.
- Randomized phrase check for exceptional high-risk actions.
- Speaker-match thresholds measured on target laptop and diverse speakers,
  including recordings and synthesized audio.
- Separate opt-in for microphone background listening. No cloud transmission
  of raw enrolled voice data.
- Fail-closed behavior if the local speaker model is missing.

**Definition of done:** An unenrolled voice cannot call any JARVIS tool or
view saved personal results. The enrolled owner succeeds with a measured
false-reject rate in normal use. Replay and synthetic-voice resistance
must be specifically tested rather than assumed.

### Phase B — Windows lock/unlock

- Security design review of proper native Credential Provider plus
  supported authentication authority.
- Prototype in an isolated VM; verify pre-logon audio and recovery.
- Hardware-backed factor or additional system credential recommended.
- Full compatibility and recovery testing on Windows 10/11 and after updates.
- Trusted signatures and independent security testing before normal deployment.

**Definition of done:** A genuine locked Windows session is unlocked through
Windows LSA only following supported authentication; wrong speaker/replay/
invalid proof fails, Windows system sign-in recovery remains functional,
and a crash cannot permanently lock the owner out.

## Current JARVIS build status

v0.5 Windows build #2 passed installer, local AI and uninstall tests.
v0.6 Windows build #3 failed the packaged import check in CI and has NOT
produced an approved replacement installer. Fix this CI failure before
mixing any new voice-biometric functionality into a release.

## Explicitly prohibited shortcuts

- Storing the Windows password and auto-typing it after voice recognition.
- Running shell commands or UI automation to circumvent the lock screen.
- Disabling Windows PIN/password/Hello fallback.
- Calling speech transcription (recognizing words) speaker authentication.
- Claiming that any voice biometric is impossible to spoof.
