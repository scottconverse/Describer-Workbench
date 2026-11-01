# Public documentation audit — November 1, 2026

Audited the public repository, README, user manual, architecture guide, landing page and release downloads against the 0.4.2 application. This audit corrects documentation and its renderer; it does not rebuild or change the desktop application. The starting documentation commit was `b54a1fe0ab42f642d02f59f69ce7486b08d21a04`.

## Findings corrected

| Finding | Correction |
| --- | --- |
| Downloaded Markdown linked to repository-only guide and notice filenames, producing three website 404s. | Rewrite guide, diagram and notice links to absolute published URLs when generating downloads. Repository Markdown keeps its repository links. |
| The PySide source browser URL returned 404. | Link to the working upstream `/cgit/pyside/pyside-setup.git/` browser. |
| Timing instructions could produce unintended end times. | Explain that leaving Start shifts End, and enter the intended End afterward. |
| Add preserves the previous selection; saving applies the editor to that selected cue. | Explicitly instruct selecting the newly added row before saving. This documents existing behavior; the application quirk remains. |
| Instructions did not clearly explain how to preserve a comparison copy without Save As. | Save, copy the project in File Explorer, then open the copy. |
| Settings descriptions overstated the scope of speech volume and implied preparation FPS affected only Gemini. | Specify native/Qt speech volume scope and preparation FPS use for both analysis providers. |
| Guide canonical URLs and sitemap entries pointed through `.html` redirects. | Use the hosting service's extensionless canonical paths. Local HTML navigation remains usable. |

## Claims traced against the application

Each row distinguishes code inspection from execution. No live paid/cloud inference was run for this audit.

| Documented outcome | Implementation inspected | Evidence / limit |
| --- | --- | --- |
| Open video, URL downloads and reject audio-only media | `app.py`, `services.py` probe/download paths | Source traced; UI controls observed in isolated Qt test. Public YouTube extractor compatibility remains unverified. |
| Gemini and Ollama analysis, model discovery and connection tests | `models.py`, `services.py`, `app.py` | Provider choices observed; capability/request code traced. Direct Claude/OpenAI-compatible analysis is correctly described as absent. |
| Exact-tag off/32K/64K profiles; DeepSeek 1017 low effort | `models.py`, profile regression tests | Source traced; existing release receipts establish Gemma 26B/Qwen Q6 settings on the Bunny segment. No new inference claimed. |
| Chunked ranges, eight-frame Ollama cap, progress/cancellation and cloud confirmation | `services.py`, `models.py`, worker/UI paths | Source traced; range controls observed. Sampling limits and inability to recover omitted audio/motion remain explicit. |
| Add/edit/delete, timing, save/open and replacement on analysis/import | `app.py`, `project.py` | Isolated GUI test reproduced Start/End shift and Add selection behavior, verified safe documented selection sequence and absence of Save As. |
| Ask/Explore, glossary, presets and verbosity | `app.py`, `services.py`, prompt generation | Source traced; controls observed. Output quality depends on model and sampled frames. |
| Windows playback speech, queue/interruption, ducking and screen-reader fallback | `playback_speech.py`, `app.py` | Source traced; previous playback acceptance reused. NVDA/JAWS end-to-end use remains unverified. |
| SRT/text import/export, compatibility imports and project schema | `project.py`, `compatibility.py`, UI paths | Source traced against documented formats and paths; prior subtitle acceptance reused. Projects do not embed media or saved API keys. |
| Windows/32-bit/OneCore/OpenAI voice selection and stereo MP3 mixing | `services.py`, voice helpers, UI | Engine choices observed; timing/ducking/downmix code traced. Prior media-export acceptance reused; OpenAI speech requires live key acceptance. |
| Settings, DPAPI, recovery and logging | `services.py`, `diagnostics.py`, `app.py` | Source traced; isolated test left production preferences untouched. Configured key redaction is not a guarantee that logs contain no sensitive text. |
| Updates and source/portable installation | updater/build code, release packaging | Source traced; unsigned Windows binary accurately disclosed. No new signed build or CI run claimed. |
| Diagram module/data-flow boundaries | `docs/ARCHITECTURE.md`, three SVGs and corresponding app modules | Source comparison; diagrams describe implemented desktop/worker/provider boundaries. |
| Public navigation, HTML fragments, Markdown and downloads | root docs, generated pages and live publication | Before-fix crawl checked 70 distinct HTTP targets and repository-relative links. Only the four broken targets above failed. Regression checks cover generated files/fragments and absolute Markdown navigation; live post-publication check is recorded locally. |
| Download authenticity | all four anonymous GitHub release downloads | Sizes and SHA256 match GitHub digests and SHA256SUMS; both ZIP CRC checks passed. All source ZIP files match the tag after Windows line-ending normalization. |

## Artifact and evidence boundaries

The immutable release is [v0.4.2](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.4.2), source commit `5bf93b952369c1342e54faa9f2c857a695430075`. Downloaded executable SHA256: `f5a7fcd34998b96fa85089c77b07346df20abe1f43cee9c37e4a0f3e11ed2b13`. Its original packaged documentation is historical; current corrections are in main and the [published manual](https://describer-workbench.sconverse.chatgpt.site/manual).

The earlier 28-test release suite, frozen-module checks and Bunny segment receipts are historical acceptance, not newly executed tests. This audit executes two documentation regression tests and an isolated source GUI smoke test. Raw HTTP, download-integrity and GUI receipts are retained locally under `evidence/public-audit/`; they are excluded from Git because machine paths and third-party response data need not be published. No independent reviewer is claimed.

Unverified: live Gemini/OpenAI/cloud behavior without keys/access; screen-reader end-to-end behavior; native-speaker translation quality; public YouTube compatibility; full-film description accuracy and coverage. Cue counts and successful requests are not accuracy scores. No blanket open-source license has been assigned to new Workbench code; public visibility does not change licensing.
