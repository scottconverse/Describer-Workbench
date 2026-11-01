# Audit of original Omni Describer and Describer Workbench

## Scope and method

Target is the supplied original ZIP, SHA-256 83456c4160d2020a9cfa7f49e006299b83c734b21a0ac6710862d7819c077a97. Its executable was not launched. REA retained artifact inventory (evidence/rea-artifact.json), static Python 3.11 bytecode inspection using xdis, the 39-module / 381-code-object inventory, and supplied help/change log establish the original behavior. This is an independent implementation, not the original source tree. No API keys were inspected or used and no media was uploaded.

The delivered 0.2 artifact was audited before edits: all 312 payload hashes, recorded source hashes and the source ZIP matched. Each of its eight embedded application code objects structurally matched compiled source, comparing bytecode, constants, names, signatures and flags while excluding source-filename metadata. Evidence: evidence/audit-0.2-identity.json. Old build claims were therefore linked to actual source, but that did not prove complete feature parity.

## Findings and disposition

| Original outcome | Inspected implementation / 0.3 disposition | Evidence and remaining limits |
|---|---|---|
| Local files, direct URLs and YouTube | Qt media player, FFmpeg segment preparation and validated yt-dlp URLs. Restored quality selection. | Nine real library videos decoded; real loopback HTTP download byte-matched. Public YouTube extraction not verified. |
| Timed playback, interruption and screen-reader speech | Fixed dropped cues: Qt enqueue preserves pending descriptions; optional original accessible-output2 backends with asynchronous Windows fallback. Seek/pause/close clear speech. Restored persisted player volume. | Queue/reader dispatch/fallback fixtures and actual native backend loading. No active NVDA/JAWS available; usability and reader-specific ducking unverified. |
| Description editor | Add/edit/delete, start-time duration preservation, row selection seeks. Ctrl+S now applies the active edit before project save; edits mark project dirty. | GUI regression and retained real edit/playback evidence; final portable acceptance separate. |
| SRT/TXT output and import | One description per TXT line; timed SRT; UTF-8/UTF-16/Windows-1252 SRT/VTT input, warnings for invalid empty/zero-duration rows. | All 40 library subtitle files preserve text and millisecond timing on SRT roundtrip. |
| Analysis settings | Restored chunking on/off and Short/Standard/Detailed guidance. Editable model, frame rate, temperature, silent video and safety-filter request remain. Provider defaults unchanged. | Single/chunked fixtures, SDK request fixtures and real silent transcoding. Provider acceptance/quality requires Gemini key. |
| Generated response cleanup | Original JSON schema supported; invalid rows skipped with a log, timestamps repaired, consecutive duplicate text removed including chunk boundaries. | Malformed/reversed/overlapping/duplicate fixtures; strict project validation retained. |
| Character glossary | Request/merge identities with or without chunking; edit manually and include in scene requests. | Single/multiple chunk fixtures and GUI glossary assignment. Real identity consistency requires Gemini key. |
| Prompts | Ten independently authored original genre equivalents, per-language CRUD, English fallback and original prompts.json import. | Catalogue/source inspection and read-only import regression. Wording is independently authored, not verbatim prompt equivalence. |
| Scene conversation | Conversation context, selectable clip length, valid answer insertion at captured time for four seconds with duplicate-button prevention. | Local insertion/validation fixture. Actual questions/answers require Gemini key. |
| Spatial explorer | Keyboard grid, layout/list/jump/nearest-object, validated coordinates and unique positions; uses selected speech output. | Parser/uniqueness fixtures. Live layout correctness requires Gemini key. |
| Windows TTS | Real SAPI 64-bit, SAPI 32-bit and OneCore enumeration, voice selection, rate, speech-volume control, preview and export. | Real WAV synthesis and quieter volume-50 output on all three. Third-party installed voices unavailable. |
| OpenAI personalities | Five independently authored presets, CRUD/import, base voice/speed/instructions, preview/export adapter. | Payload fixtures; actual OpenAI audio, account access and delivery require key. |
| MP3 mixing | Timing, speech fitting, stereo output, silent-source handling, bed ducking once, fades and batching. | Nine sampled library exports and three separate stereo/six-channel layouts with channel/duration assertions. Prior unchanged signal oracle: -15.02 dB and 21-cue narration gain regression. No full-film or quality claim. |
| Notifications | Generated start/finish/error tones; fixed asynchronous source-readiness race. | Native QSoundEffect Ready and playback-start observed; auditory quality not assessed. |
| Preferences and original imports | DPAPI storage, validation/recovery, explicit JSON/XOR/Fernet preference import without keys, prompt and voice import. | Synthetic encrypted original fixture and unchanged source-file assertions; prior actual DPAPI roundtrip. Hardware-bound importer not tested against private user settings. |
| Localization | Nine main-control packs plus supplied original catalogues applied to matching dialog/settings labels; Arabic RTL. Original attribution/license retained. | Nine-language dialog regression. English fallback remains for new/untranslated strings; no native-speaker review. Full translation equivalence is not claimed. |
| Diagnostics | Restored configurable logging level with rotating application log and API-key-string redaction. | GUI fixture verifies level filtering and redaction. Status messages remain visible independently. |
| Update check/apply/restart | Workbench-only configurable feed, opt-in startup check, SHA-256 staging, safe archive paths, retained previous directory, helper process identity check. Replaced timer race with completion-driven staging. | Bad hash/traversal and swap fixtures; real disposable portable restart evidence separate. No original updater/service contacted and no public Workbench feed exists. |
| Help/shortcuts | F1, Ctrl+O/U/Y/comma/S and menu entry points; integrated window rather than original separate player/editor windows. | Source tracing and local GUI acceptance. Original branding, web-service links and license activation dialog are not reproduced as product features; original license accompanies reused catalogues. |

## Receipt audit

The 0.2 receipts are retained as historical evidence. They do not demonstrate full original fidelity, full-film generation, live AI behavior or human AD quality. The old library harness compared subtitle counts and cached videos by path alone. It now pins all 52 input-file hashes and source hashes, does not reuse path-only cache results, compares every subtitle's text and rounded millisecond timing, and probes exported channel count/duration. New evidence is under acceptance-0.3; it does not overwrite historical 0.2 evidence.

The library run preceded final editor-save, prompt fallback, explorer speech routing, logging and cross-chunk cleanup changes. Its source hashes explicitly preserve that tested identity. These changes do not alter the tested codecs, subtitle import/export, synthesis, or mixer paths; affected behavior has separate final-source regressions. This is reuse of unaffected evidence, not a claim that the library ran against a different source hash. Native volume, notification, reader loading and downloader checks have their own receipt. Candidate source/payload identity and installed UI checks are recorded independently.

## Verification boundaries

Without a Gemini key, real uploads, processing latency/limits, current model access, retries, deletion, token usage, description accuracy/timing/dialogue gaps, glossary identities and scene responses remain unverified. Without an OpenAI key, voice rendering, speed/instructions, model/account access, billing and service delivery remain unverified. Fixtures validate request construction and local orchestration only. Even with keys, human AD quality needs review; captions are test inputs, not quality ground truth.

Other limits are independent of keys: no installed screen-reader acceptance, third-party voice testing, native-speaker review, public YouTube test or public update service. These are evidence limits, not hidden completion claims. No external release, signing or publication was performed.

## Delivered candidate and acceptance

Describer Workbench 0.3.0 is delivered at dist/DescriberWorkbench/DescriberWorkbench.exe, the existing desktop shortcut target. SHA-256: `79e11372cc2737bea76c519ab256e638a12c7343160575b775f3036cf1b47602`. All eleven frozen application modules match the final source structurally; the reader modules and NVDA DLL are bundled. Twenty-one final source regressions pass, including completion-driven update staging and diagnostic redaction.

The real disposable 0.2-to-0.3 swap retained the old executable hash, replaced it with the candidate hash, and relaunched a new process. Old process and helper terminated. The restarted packaged UI exposed the restored settings, loaded the desktop NASA project and advanced from zero to ten seconds with Screen reader output selected and Windows fallback available. No active reader was present and no auditory quality is asserted. Installed startup was separately observed after replacement. Receipts: acceptance-0.3/portable-update.json, relaunch-process.json, restarted-ui.json, portable-settings.json, portable-playback.json, installed-startup.json and delivery.json.

Immediate rollback is rollback/0.2.0. Earlier recovery and source archives are retained. Owned test windows/helpers/build jobs are closed. Cleanup removed 1,821,069,800 bytes of build caches, disposable update copies and redundant FFmpeg copies. Final payload hashes and code/receipt identity are in portable-SHA256SUMS-0.3.txt, source-identity-0.3.json and build-receipt-0.3.json. The source archive's external SHA-256 file avoids a circular archive/self-hash claim.
