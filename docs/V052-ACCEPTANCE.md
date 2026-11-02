# 0.5.2 release acceptance

0.5.2 addresses the bounded F01–F25 first-use/recovery findings: review provenance, voice-discovery ownership, Scene isolation, overwrite protection, damaged job isolation, explicit detector provisioning, verified readiness, exact-model and transactional Draft settings, responsive prerequisite checks, destination-specific consent, narration repair and desktop resume.

## Evidence

- Native Windows remediation suite: 86 passed and three subtests passed; one overly tight GUI timer assertion failed. Its corrected one-second bound retained the pending-provider/cancellation assertion and passed separately. This is not a claim of a single all-green local suite.
- An independent source audit identified six issues; regressions reproduced failures before fixes and 37 affected tests passed afterward.
- A packaged windowed API logging failure was reproduced and fixed. The occupied-port/retry check passes with stdout/stderr absent. No conflicting process is stopped.
- Five final acceptance-edge cases passed: declining coverage-file overwrite, failed/empty/removed native voices, and cancellation during detector download preserving prior bytes.
- Fresh-profile native Draft offered detector install/Cancel. Decline left the detector absent; acceptance downloaded the pinned SHA-256, validated ONNX and continued to the next prerequisite without inference.
- Native narration repair regenerated actual Windows speech while retaining cue text, evidence and event identity. Windows/32-bit voice lists returned installed voices; switching and dialog closure remained responsive.
- A real local prepare job was cancelled after a speech checkpoint. Incompatible settings were rejected without changing stages. After app restart, desktop recovery completed 30 synthetic cues; prior checkpoint/WAV hashes and modification times were unchanged, as was source-media hash. The recovered project saved successfully.
- Packaged typed-path overwrite confirmation preserved existing bytes on No and retained Export configuration. Current Help/version and packaged source/document provenance were checked.
- Packaged CLI, authenticated HTTP/OpenAPI and MCP checks passed with 17 MCP tools. Transport evidence was reused where code was unchanged; the final GUI additionally exercised real authenticated submit/cancel/resume.

The release-verification.json asset records exact release artifact provenance and publication checks. GitHub Actions supplies the required release-source CI result; retained local results above are not presented as remote CI.

## Limits

The original intermittent voice-picker abort was not reproduced with its exact historical crash signature. The identified ownership/completion-ordering defect is covered by controlled timing and native discovery, not a guarantee against all future Qt failures.

No new full-film accuracy campaign, live paid/cloud inference, screen-reader acceptance, clean-machine installation or public YouTube extraction is claimed. The 0.5.2 Windows package was corrected after initial publication: its GUI and CLI executables are now signed as Scott Converse using Azure Trusted Signing with Microsoft timestamps. Signing run 41541363690 signed the exact prebuilt executables; local signtool and Authenticode checks independently verified both. The release verification asset records the new hashes. AI descriptions still require editorial review. Earlier version releases remain unchanged; older checkpoint implementation identities may be rejected safely by this release.
