# Eight-package stabilization

Approved scope: preserve every existing integration, model choice, format and
safety boundary. Implement, verify, document and push one package before starting
the next. Current released applications remain separate from source candidates.

1. Non-destructive range drafting and consistent project transactions.
2. Incremental editing and useful typing undo groups.
3. Keyboard focus, accessible cue information, contrast and native acceptance.
4. Save As, bounded unsaved-work recovery and reversible glossary deletion.
5. Validated cross-job speech-analysis reuse.
6. Simple drafting with preserved advanced controls and visible transmission.
7. Export duration/outcome previews based on the real plan.
8. Small controller/model extractions and affected GUI lint/type checks.

## Baseline protocol

[Recorded baseline and limits](STABILIZATION-BASELINE.json). The two-hour load
check after Package 1 measured 338 ms median/564 ms maximum at 721 cues, compared
with 410 ms/523 ms in the corrected original run. This is not Package 2's incremental
editing improvement; run-to-run variation and the remaining full refresh remain.

Before application changes, run `tools/stabilization_baseline.py` on actual short,
30-minute and two-hour media. Keep source identity, input hashes, each keystroke's
elapsed time, open/playback, real detector and segment processing times, process
memory and failures. The controlled cue population is one cue per ten seconds;
it is a load fixture, not AI output or factual-accuracy evidence. Full AI drafting
cost/quality is a separate workflow measurement. Compare the same inputs after
affected packages. Preserve original source media and user settings.

## Package 1 preservation rules

- Existing descriptions are retained by default, including authored, edited,
  reviewed, approved and legacy descriptions whose history cannot be inferred.
- Use stable cue identity distinct from the observed event identity. Preserve
  original event times/evidence and distinguish human review from placement.
- A range is half-open `[start,end)`. A cue crossing either boundary is
  retained in full, never clipped or silently deleted. Consider both authored
  placement and observed provenance when detecting conflicts.
- Present proposed additions and conflicting descriptions before changing the
  project. Replacing a conflicting existing description requires an explicit
  choice; retaining it remains the default. Never let provider output assign
  human approval.
- Applying a draft is one complete project transaction: cues, identity,
  provenance/review state, coverage, analysis/usage and glossary. Undo/redo must
  restore these together. Reject stale proposals if the project has changed.
- Cancellation/failure/rejected proposals do not mutate the project. Save/load
  round trips preserve the same identities and states. Atomic saves remain.
- Candidates read existing format-1 projects and save format 2. Older 0.6.1
  applications reject new files instead of silently dropping new identity and
  review metadata. Original files remain unchanged until explicitly saved.
- Preserve existing glossary by default; show proposed changes separately.
  Retained cue coverage stays attached to its cue; replacement coverage applies
  only to accepted replacements/additions. Reconcile combined narration before
  media export rather than treating partial-range timing as globally verified.

## Evidence status

Package 1 has passed local preservation, service, GUI, recovery and media checks.
The full Windows suite recorded 186 passing tests, 3 subtests and 4 skips, plus 7
failures caused by a test's old disclosure-text selector. All seven corrected
provider consent/routing cases passed in the affected run (132 passes, one
recovery-fixture failure). That fixture reused an old cue ID for purportedly new
AI output; fresh proposal identity and explicit approval fixed it, with 53 tests
and 3 subtests passing. Final event-window/identity checks passed 7 tests. Existing
passed evidence was retained; the full suite was not restarted. Documentation
links and affected Ruff checks pass. Windows emitted a native COM diagnostic at
the legacy start-screen visibility check; execution continued and the test
passed. No claim is made that this diagnostic has been resolved.

The native Windows real-media workflow decoded NASA video, explicitly replaced
one reviewed fixture cue, accepted another, preserved three other cues and the
original glossary, and verified full-project undo/redo and save/reopen. These are
fixture proposals through actual Qt controls, not a live AI or reader test.
Linux/Mac source checks passed at `179ab39` (run `42095956461`). The narrow
file-format compatibility correction at `94cf008` passed 49 affected local
checks and format-specific Linux/Mac checks (run `42096984452`); the original
GUI evidence was retained. The actual old reader rejected format 2, and forcing
format 1 demonstrated the loss of identity/review fields that the correction
prevents. Package 1 is accepted and pushed.

Package 2 updates a single cue, its coverage and existing visible widgets for
ordinary typing. It retains full transactions for timing/structural edits and
uses one project history for keyboard/context undo. Same-media native Windows
measurements recorded median 16.4/17.1/17.3 ms at 12/180/721 cues, compared with
53.6/146.2/410.3 ms before stabilization. The two-hour working memory measured
402 MB versus 716 MB; 20 continuous characters became one undo group. Occasional
paint spikes remain (two-hour maximum 344 ms); these are GUI load measurements,
not full AI processing or quality claims. Raw receipts remain local.

P2 verification ledger: initial 18 existing affected checks passed; the new
keyboard test exposed private text-widget undo bypassing project history and
was fixed. Two new fixtures needed normalization of legacy event times and a
noncanonical evidence field. Only those affected tests were repeated; no app
build or full CI restart. The pre-existing Windows COM diagnostic remained
nonterminal. Final local runs passed 48 tests and 3 subtests, then 7 editing/documentation
checks. Native Linux and macOS source/Qt tests passed at `9b9da1a` in run
`42098539007`. Package 2 is accepted and pushed.

Package 3 candidate restores native focus rendering in ordinary custom lists and
paints a distinct keyboard-focus rectangle on description rows. Accessible cue
names carry timing, placement, review state, text and uncertainty, including live
updates. White on #416180 replaces the low-contrast primary button and pause
badge combination. Platform voice labels retain correct settings categories;
shared help text uses host speech terminology.

Windows NVDA 2026.3 portable (official signed NV Access release) was actually
running with isolated settings and add-ons disabled. Its real speech log records
both cue names and times/review/uncertainty, description editor focus and the
application's live-text output through the active NVDA adapter. The native Qt
workflow navigated cues, edited text, used undo/redo and saved the actual project.
The saved file and normal application exit were verified. These are speech
pipeline and interaction observations; human listening/blind-user usability,
JAWS, VoiceOver and Orca remain unverified. Temporary reader was quit afterward. Local checks passed 22 tests (4 platform
skips) plus 3 documentation tests. Native Linux/macOS source/Qt checks passed
at `f1532a3` in run `42099782482`; Package 3 is accepted and pushed.
Initial test-window visibility was delayed and a duplicate fixture window was
closed normally; intermittent CUA foreground/geometry errors were recovered by
fresh observations, without changing the app. No full CI or build restart.

Package 4 candidate adds Save As, bounded local unsaved snapshots and reversible
glossary deletion. Cancelled/failed Save As leaves the original path/file intact.
Snapshots include all project data and pending editor values, use atomic writes,
validate source size/mtime at recovery and open unsaved copies. A real Windows
Qt/video workflow used the actual 30-second timer, abruptly exited the isolated
child (23), restarted, accepted the real recovery dialog, restored the full
project/review history and saved a separate copy. Original project/video were
unchanged. Local checks passed 42 affected tests, then 24 focused GUI, preservation
and documentation tests after narrowing deletion to keep other glossary lines
exactly. No full suite, binary build or earlier CI run was restarted. Native
Linux/macOS source checks passed at `67cdeba` in run `42102036691`. A controlled
721-cue snapshot/retention check measured 29–37 ms per snapshot, with three
retained versions totaling 1.43 MB; this is filesystem work, not AI or GUI latency.
Package 4 is accepted and pushed. The store limits and
30-second recovery window are documented in the user/developer guides.

Package 5 candidate reuses whole-source speech/vocal classification through the
same shared pipeline stage across jobs. The key hashes source bytes, duration,
pinned detector bytes, detector implementation (executable when frozen), FFmpeg,
ONNX runtime and NumPy versions. Captions are overlaid freshly on every call.
Payload digest/shape/finite-interval/score validation rejects corrupt reuse;
changed inputs create a new key. A per-key file lock observes cancellation while
waiting. Cancellation/failure publishes no result; unavailable cache storage
falls back to fresh validated analysis, not unprotected gaps. Source/model bytes
are checked again before publication. Detector checksum verification still runs
before any cache lookup.

Actual Windows YAMNet/FFmpeg comparisons on the same three media measured fresh
versus reused protection at 1.28/0.67 s (short), 6.37/0.42 s (30 minutes), and
24.08/0.65 s (two hours), with identical results and unchanged source hashes.
These are stage timings, not full AI throughput/quality. 46 affected checks passed;
a new caption fixture expected lists rather than the existing tuple output and
was corrected. The frozen-identity fixture's process-global sys patch stalled an
isolated test before the benchmark; it was stopped and replaced by a module-local
fixture, with the affected test passing. Prior engine evidence was retained; no
full CI/build restart. Native Linux/macOS source/locking checks passed at `d7c3cf4` in run
`42103572104`. Six final cache/documentation checks passed locally. Package 5 is
accepted and pushed.

Package 6 candidate makes connection, configured model summary, range and Start
with AI the ordinary path. Advanced retains every provider, exact model/catalog,
connection test, prompt/preset, verbosity and glossary control. Transmission and
preservation disclosures and Start/Cancel stay outside the scrolling area.
Provider/model selection remains explicit, no fallback/default change; cancel
restores settings and editorial text. 74 affected local tests and 3 subtests
passed, including provider consent/routing and model/recovery regressions.
Rendered native Qt simple/advanced layouts were inspected; final screen-height
and empty-model-list refinements are covered by affected checks. One atomic
patch missed an existing timer.stop clause, changed no files and was corrected
from actual source. No full suite/build/CI restart. Five final draft/documentation checks passed.
Native Linux/macOS source checks passed at `74c3364` in run `42104653513`.
Package 6 is accepted and pushed.

Package 7 candidate adds format-specific outcome text and an optional measured
narration preview using the shared prepare pipeline and pause selection. Voice,
format and destination survive measurement; settings remain unchanged until
Export. Stale measurements are explicit; changed project input cannot be
overwritten by measurement completion. Export still measures independently.
23 affected local tests passed, followed by 3 focused preview/actual-media tests
after correcting numeric normalization in the stamp across save/reopen. Actual
Windows native speech measured 6.143175 seconds of pause narration over a
4-second controlled video; WAV was 10.143175 seconds and MP4 passed the 0.15-second
tolerance and actual decoding. Source unchanged and reopened preview identical.
No human-listening or live cloud synthesis claim. Native Qt preview screenshot
was inspected. Acceptance-helper misuse of the video-only probe on WAV was
corrected to FFprobe; prior checkpoints reused. An atomic documentation patch
context miss changed no files. No full CI/build restart. Three final preview/stale-job checks and three documentation checks passed. A collection command used the nonexistent test_docs.py path; only the correctly named test_documentation.py was then run. Native Linux/macOS source checks passed at c24a3f1 in run42106391026. Package 7 is accepted and pushed.

Package 8 candidate extracts existing edit-history commands and keyboard routing
into `editor_history.py`, and replaces hidden-table selection with the typed
`CueSelection` identity model. Sorting, filtering, deletion, undo and load/save
use that model. The visible filter selection is retained. Loading a different
project resynchronizes the editor before it can be saved, preventing stale text
from carrying over. Advanced controls, providers, formats and safety remain.

31 affected checks and 3 subtests passed after the filter correction. One final
cross-cutting regression pass completed with 216 tests and 3 subtests passing,
4 platform skips and one existing FastAPI/httpx deprecation warning. A targeted
additional load test reproduced stale editor text; the synchronization fix then
passed 33 affected selection/edit/recovery/drafting/export checks. Unaffected
full-suite evidence was retained, with no whole-suite restart. Actual offscreen
Qt playback, 20-character editing, undo/redo and save/reopen passed on the same
short/30-minute/two-hour inputs, with unchanged source hashes and one typing undo
group. A final real NASA-media load check confirmed stale fields are replaced
without changing saved metadata. These offscreen latency/memory measurements
are not directly comparable to earlier native-window results. No AI, detector,
reader or human-listening claims are added by this check.

Affected desktop/tool Ruff F checks and strict mypy on the selection model pass;
the dynamic legacy GUI is not claimed fully typed. Three documentation checks
pass. Tests default to offscreen Qt. Desktop use was stopped at the user's
request and the computer-use runtime reset; the user confirmed release, then
authorized continuation headlessly. Initial extraction left three unused
imports, fixed locally; atomic patch context misses changed no files. These
agent/helper issues did not restart full CI or builds. Native source checks
at ce3cded passed all macOS tests/lint/types in run42108524514. Linux retained 49 passing tests and 3 subtests, but one added credential-storage test correctly refused plaintext because the new workflow lacked Secret Service. This is an agent CI setup error, not a product-test failure. The workflow now reuses the existing Unix dbus/keyring setup. A Linux-only keyring scope reruns just that test plus lint/types skipped after failure; all other passed evidence is retained. The original run remains recorded as failed. Final narrow check pending.

Native reader acceptance must identify exactly which
reader/platform combination was exercised; simulated events are not that proof.

Source candidates on the stabilization branch introduce a draft-review dialog.
The published 0.6.1 applications retain their documented replacement behavior
until a separately verified application release. A candidate does not update the
installed application or public binary merely by being committed.
