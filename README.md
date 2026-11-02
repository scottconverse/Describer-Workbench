# Describer Workbench

**One audio-description engine for a Windows workbench, Python, CLI, REST/OpenAPI and MCP.**

Version **0.5.0** combines the Windows workbench and developer interfaces in one shared engine. Download the portable Windows package or build the tagged source.

Open a video, draft timed descriptions with a local Ollama vision model or Google Gemini, edit every cue, listen alongside the video, and export subtitles or a narrated audio mix. Manual editing, subtitle import and Windows speech work without an AI API key.

[Windows 0.5.0](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.5.0) · [Website](https://describer-workbench.sconverse.chatgpt.site) · [User manual](docs/USER-MANUAL.md) · [Architecture](docs/ARCHITECTURE.md) · [Developer guide](docs/DEVELOPER-GUIDE.md) · [Issues](https://github.com/scottconverse/Describer-Workbench/issues)

> AI output is a draft. Review visual facts, character identities, timing and overlap with dialogue. Ollama receives sampled images **without audio**, so it cannot determine dialogue gaps or audible names. The shared engine measures speech/vocal protection independently with a pinned local YAMNet classifier. This reduces timing conflicts; it does not establish visual accuracy or legal compliance.

## Capabilities

| Task | Behavior |
| --- | --- |
| Open media | Local MP4, MKV, MOV, AVI and WebM; All files selector for other supported inputs. Download direct video or YouTube URLs through yt-dlp. |
| Draft descriptions | Gemini video uploads or local/remote Ollama vision requests. Whole video, Next 20 seconds or Next 60 seconds. Sequential chunks with character glossary continuity. |
| Choose models | Editable exact ID, Ollama discovery, vision/local/cloud labels, loaded status and a text connection test. No silent fallback. |
| Edit and save | Start/end/text cue editor, glossary, `.adproject` persistence, SRT/VTT import. |
| Explore scenes | Ask about scene, add answers as cues, keyboard exploration of an AI-generated spatial layout. |
| Hear descriptions | Windows speech during playback, audio ducking, player/speech volume, interruption or queue behavior; optional active screen-reader output. |
| Export | MP4 with pause extensions, narrated MP3/WAV, SRT, VTT, TXT and project JSON. Coverage sidecars explain in-gap, pause and unresolved events. Windows SAPI, 32-bit SAPI, OneCore or optional OpenAI speech. |
| Developer integration | Same serial, durable engine through Python, CLI, authenticated loopback REST/OpenAPI and MCP stdio/Streamable HTTP. Submit, batch, poll, cancel/resume, page/time-filter results, edit, ask/explore, preview voices and export. |
| Timing | Independently measured speech/vocal protection; event-bounded slots; acceleration capped at 1.15x. Descriptions that cannot fit become explicit pause narration, without deleting genuine repeated events. |
| Customize | Language-specific prompt presets, voice personalities, verbosity, interface language, sounds and diagnostic level. |

## Install and start

1. Download `DescriberWorkbench-0.5.0-windows-x64.zip` from the [release](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.5.0).
2. Extract the complete ZIP to a writable folder. Open `DescriberWorkbench/DescriberWorkbench.exe`; keep `_internal` beside it. Python, Qt, FFmpeg and FFprobe are bundled.
3. Select **Open video** and choose your video. Open it before importing subtitle cues. Standalone audio is not a documented input workflow.
4. Choose an analysis provider/model and a short range, or add cues manually. Follow the [first-project walkthrough](docs/USER-MANUAL.md#3-your-first-project).
5. Save with **Ctrl+S**, review playback and use **Export** for SRT, text or MP3.

The binary targets 64-bit Windows and is **unsigned**. Windows 11 was used for local acceptance. Windows speech depends on installed voices. Ollama, model weights and test media are separate. No macOS/Linux release or formal minimum RAM/GPU requirement is established; hardware needs depend on the local model.

Compare your download with the release's `SHA256SUMS.txt`:

```powershell
Get-FileHash .\DescriberWorkbench-0.5.0-windows-x64.zip -Algorithm SHA256
```

## Does it need an API key?

| Workflow | Key / account | Data sent |
| --- | --- | --- |
| Manual cues, subtitle import, playback, Windows speech/MP3 | No AI key | Local processing |
| Ollama model on this computer | No provider key for the default loopback server | Frames/prompts to local Ollama |
| Ollama cloud / remote server | Access configured in Ollama or the server's optional key | Sampled frames/prompts leave the computer after confirmation |
| Gemini analysis, Ask and Explore | Gemini key and accessible model | Video with audio unless silent upload is selected; confirmation required |
| OpenAI speech export/preview | OpenAI key and accessible speech model | Description text after confirmation |

The analysis picker has **Gemini and Ollama**. OpenAI is a speech/export engine, not an analysis provider. Direct Claude and generic OpenAI-compatible analysis adapters are not implemented. Additional Ollama hosted tags must report vision support and satisfy the request format; appearing in the picker does not prove compatibility. Workbench contains no OAuth flow. Choosing a model does not download it or sign in.

## Ollama quick start

Install and start [Ollama](https://ollama.com/), and separately install a vision model suitable for your hardware. In Workbench choose **Ollama → Refresh models**, then select an installed entry marked **vision**. You may type an exact tag; press Tab to commit it. **Test connection** checks capability and makes a small text request, not a visual accuracy test. Seek to a scene, choose **Next 20 seconds** or **Next 60 seconds**, then **Start draft** in **Draft with AI**.

Default server root: `http://127.0.0.1:11434`. Settings can change it. Remote servers require HTTPS; do not append `/api` or `/v1`. Configure cloud sign-in in Ollama itself.

### Exact-tag profiles

| Tag | Thinking | Output ceiling | Context | Sampling |
| --- | --- | --- | --- | --- |
| `gemma4:12b` | Off | 32,768 | 65,536 | Native defaults |
| `gemma4:26b` | Off | 32,768 | 65,536 | Native defaults |
| `qwen3.8:27b-q6_K-vision` | Off | 32,768 | 65,536 | Native defaults |

These are exact matches, not guaranteed model registry names. The Qwen vision tag existed on the test machine; a similarly named text-only tag is refused. Aliases/renamed tags do not inherit the profile. Limits are ceilings, not target response lengths. The `deepseek-v4.1-flash:1017...` family requests low effort while still requiring vision capability. Other tags retain the existing adapter behavior. Profiles apply per request and do not change global Ollama configuration.

Ollama receives up to eight timestamped frames per request, 640 pixels wide. At the default two-second interval, analysis uses chunks of at most 16 seconds; a 60-second range normally takes four requests. Ask samples at most eight frames across its scene window. Larger context/output cannot recover missing motion or audio.

## Editing and export

Open media → draft or import cues → correct the glossary → edit facts and timing → listen with the soundtrack → save → export.

Select a description to seek to its start and expand the inline editor. Times accept seconds, `MM:SS` or `HH:MM:SS`; Start and End update independently. Valid edits apply as you type; Ctrl+Z undoes. **Add at playhead** creates and selects a three-second cue. **Ctrl+S** saves the project. Analysis and subtitle import replace descriptions after confirmation; range analysis replaces the cue list. Save a separate `.adproject` copy to preserve comparisons.

The main source tree includes the redesigned native PySide6 interface. Public v0.5.0 downloads retain the earlier interface until the next authorized release.

The engine measures synthesized speech and fits it only within the visual event and independently protected soundtrack. Speed is capped at 1.15x; no-fit descriptions pause the source instead of being discarded or moved to an unrelated scene. Complete MP4 exports freeze the video during those descriptions; MP3/WAV exports insert matching audio pauses. Uncertain events remain unresolved and block a complete narrated export. Explicit `in-gap-only` exports are marked incomplete. Script exports retain all events and a coverage sidecar; a subtitle file alone cannot express pause playback. Audio mixes downmix to stereo.

Before analysis or narrated export of media with audio, use **File → Install local speech detector** once. This explicitly downloads and verifies the pinned Google YAMNet asset. Missing or corrupt assets fail safely; no model guesses dialogue slots.

## Architecture

![Architecture: Qt desktop editor routes projects through media tools, Ollama or Gemini, and speech/export services.](docs/diagrams/system.svg)

Python/PySide6 provides the editor; every consumer uses `DescriptionService` and one serial queue. The headless engine owns jobs, checkpoints, independent sound protection, observation, synthesis, placement and export. FFmpeg prepares media and mixes audio. Existing version-1 projects still load; new fields preserve event intervals, coverage and placement. Keys remain outside job/project files. See the [architecture guide](docs/ARCHITECTURE.md) for module responsibilities, request sequences and trust boundaries.

## Privacy, storage and updates

- Settings: `%LOCALAPPDATA%/DescriberWorkbench/settings.json`. Keys use Windows DPAPI for the current account; settings are not a portable key vault.
- Projects: `.adproject` JSON contains an absolute media path, duration, cues, glossary, event/placement metadata, coverage and analysis. It does not embed video or API keys. Keep media separately.
- Durable workspace: `%LOCALAPPDATA%/DescriberWorkbench/engine` (or `DESCRIBER_HOME/engine`) retains job snapshots, checkpoints and narration WAVs for explicit resume. Keep this directory with projects that refer to its audio. No automatic retention/deletion policy is applied. One process owns a workspace; attach other consumers over HTTP.
- Telemetry: no application analytics; Hugging Face/OTEL telemetry defaults and ONNX Runtime telemetry are disabled. HTTP explicitly disables FastAPI tracing, metrics, telemetry logs and auto-export setup. Explicit provider/download requests are separate, documented transmissions.
- Diagnostics: rotated logs beside settings. Configured keys are redacted; paths, text and provider errors can remain. Inspect before sharing.
- Gemini: upload deletion is attempted in `finally`; provider retention applies if cleanup fails. Cancellation cannot undo an upload or charge.
- Ollama: loopback requests go to the configured local server. Cloud/remote use prompts before sending frames and text; Ollama controls further routing.
- Updates: no public update feed is configured. Download releases manually. The optional trusted-feed updater verifies SHA256 and retains rollback folders; integrity verification is separate from signing.

See [privacy and recovery](docs/USER-MANUAL.md#12-privacy-storage-and-recovery) for details.

## Run and build from source

Tested with Windows and Python 3.13. Install FFmpeg/FFprobe on PATH or place their executables in `bin/`.

```powershell
git clone https://github.com/scottconverse/Describer-Workbench.git
cd Describer-Workbench
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,http,mcp,dev]"
.\.venv\Scripts\python.exe run.py
# Build the portable folder:
.\build.ps1
```

The build script installs the desktop, local-model and developer transport extras plus PyInstaller 6.22.3, copies missing media tools from PATH (including Scoop shim targets), and builds `dist/DescriberWorkbench/`. The folder includes `DescriberCLI.exe` for the same CLI, HTTP owner and MCP tools without a separate Python install. It uses `py -3` when creating a missing environment: explicitly create `.venv` with Python 3.13 for the tested interpreter. Your source build is a new artifact and does not inherit the published executable's hash or acceptance evidence.

## Verification

For 0.5.0, see the release acceptance record in `docs/V050-ACCEPTANCE.md` for exact commands, results and remaining limits. Historical 0.4.2 evidence below applies only to that release. The new protocol tests initialize real MCP clients over stdio and HTTP; media tests check actual FFmpeg output. No percentage visual-accuracy claim is made.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# Optional media acceptance: opens a window, synthesizes speech and writes receipts:
.\.venv\Scripts\python.exe -m tests.local_acceptance "C:\media\sample.mp4" "C:\receipts\workbench"
```

| Evidence | Established scope |
| --- | --- |
| 0.4.2 suite | All 28 tests passed, including exact-tag picker/request settings and regressions. |
| Actual rebuilt GUI | Bunny 1:02–2:02, clean starting glossaries, Gemma 26B and Qwen Q6: four completed requests each, 32K/64K/off settings, confirmed 64K runtime, no truncation/thinking output. |
| Saved results | 29 Gemma cues and 25 Qwen cues matched normalized responses. Cue counts are not accuracy scores. |
| Artifact | All 13 frozen app modules matched source; installed launch/playback accepted. Published ZIP and downloaded copies verified by SHA256. |
| Earlier media samples | Nine sampled video exports, 40 subtitle files and three audio layouts passed; not full-film coverage. |

The [v0.5.0 release](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.5.0) includes sanitized verification JSON and checksums. The table above is historical 0.4.2 evidence; the current [acceptance record](docs/V050-ACCEPTANCE.md) covers 0.5.0. Raw receipts stay local because they contain frames/machine paths. Live Gemini, OpenAI and cloud acceptance remain unverified without keys. NVDA/JAWS end-to-end use, native-speaker translation review, public YouTube extractor compatibility and full-film AD quality remain unverified. Windows GitHub CI runs the suite, lint, documentation rendering and Python package build. Its media tests use generated fixtures; the separate native acceptance record covers the actual vision/speech pipeline and portable executables. [AUDIT.md](AUDIT.md) records original parity work and historical results; read them in their version context.

## Documentation and development

- [User manual](docs/USER-MANUAL.md): nontechnical walkthrough, reference, troubleshooting and technical user section.
- [Architecture](docs/ARCHITECTURE.md): components, sequences and data boundaries.
- [Developer guide](docs/DEVELOPER-GUIDE.md): install extras, Python/CLI/REST/MCP contracts, authentication, jobs and export modes.
- [Public documentation audit](docs/PUBLIC-AUDIT.md): corrections, code tracing, download checks and verification limits.
- [Parity](PARITY.md), [audit](AUDIT.md) and [third-party notices](THIRD-PARTY-NOTICES.md).

For an issue include the app/Windows version, exact provider/model, reproduction steps, expected result and redacted logs. Never post keys, private video, complete settings or unsanitized projects. Describe the scope actually tested.

The landing page is in `website/`. The [GitHub Pages site](https://scottconverse.github.io/Describer-Workbench/) mirrors the landing page, manuals and diagrams through `.github/workflows/pages.yml` on documentation changes to `main`. The existing [website](https://describer-workbench.sconverse.chatgpt.site) remains available and is the canonical address in generated metadata. Both use the same renderer and relative HTML navigation; no analytics are added.

Render the manual/site with a documentation-only dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -r docs/requirements.txt
.\.venv\Scripts\python.exe tools/build_site.py --output "C:\work\workbench-site"
```

The output includes the landing page, HTML guides, architecture drawings and downloadable Markdown. Downloaded Markdown uses absolute web links so navigation survives saving it outside the repository. Hosting is separate from the desktop app; docs publication does not rebuild the executable. The immutable 0.4.2 ZIPs retain their historical documentation. The 0.5.0 portable package includes the current guides; this README and the website carry current release guidance.

## Provenance and licensing

Independently written Python source reconstructs a documented Omni Describer workflow through supplied documentation and static analysis. This is **not recovered original source** and implies no original-author endorsement. Original executables, recovered bytecode and branding are not distributed. Attributed translations retain their original terms in `third-party-licenses/Omni-Describer.txt`.

New Workbench code is licensed under **Apache-2.0**, with the no-warranty terms in [LICENSE](LICENSE). See [NOTICE](NOTICE) for attribution. Third-party components retain their own terms, including Qt/PySide, FFmpeg and original translation restrictions. Consult [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and retained texts before redistribution; the original app's terms do not license all Workbench code.
