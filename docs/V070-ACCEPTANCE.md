# Describer Workbench 0.7.0 acceptance

The release contains all eight [stabilization packages](STABILIZATION.md), with the recorded [baseline and measurement limits](STABILIZATION-BASELINE.json). Existing providers, model choices, accessibility routes, export formats and safety protections remain.

Projects read format 1 and save format 2. Older 0.6.1 readers reject format 2; preserve originals when comparing releases. Range drafting retains existing cues by default, requires explicit conflict replacement, preserves boundary-crossing cues and applies one complete undoable transaction. Editing and recovery retain cue identity, provenance, review history, coverage and glossary.

Source acceptance: 216 tests and 3 subtests passed with 4 platform skips; after the final load synchronization correction, 33 affected checks passed. Three documentation checks, affected desktop/tool lint and strict selection-model types passed. Actual short/30-minute/two-hour media playback/edit/undo/save/reopen preserved source hashes and metadata. The long inputs are excerpts of the same council meeting. Native Windows NVDA speech events were observed earlier in this stabilization cycle; no human-listening, VoiceOver or Orca claim is made. Offscreen results are not directly comparable to native-window latency.

Current binary provenance, platform build/installation checks, Windows Azure signature/timestamp verification, public asset hashes and installed-update recovery are recorded in the release's `release-verification.json`. Consult that receipt for executed release outcomes; source checks alone do not prove binary delivery. The historical 0.6.1 and Unix add-on receipts apply only to their original candidates.

Windows requires Valid Scott Converse Authenticode signatures and Microsoft timestamps on both application executables. Mac has ad-hoc integrity only, no Apple publisher certificate or notarization. Linux packages are unsigned. Only Windows uses the staged signed updater; Mac/Linux replacement remains manual.

AI descriptions remain reviewed drafts. Known factual/recall limits and separately keyed provider entitlement limits remain documented in [AI connections](AI-CONNECTIONS.md). No new full-film semantic-quality, live-provider, human-listening or legal-compliance guarantee is implied.
