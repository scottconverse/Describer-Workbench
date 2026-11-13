# Describer Workbench

Describer Workbench writes audio description for video. An AI model drafts short, timed descriptions. You change the words and the timing, hear them over the soundtrack, and export a described video, narrated audio or subtitles. One engine serves the desktop app, Python, the CLI, an authenticated REST/OpenAPI server and MCP.

[Website](https://scottconverse.github.io/Describer-Workbench/) · [Download 0.8.4](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.8.4) · [Quick start](docs/QUICK-START.md) · [User manual](docs/USER-MANUAL.md) · [Developer guide](docs/DEVELOPER-GUIDE.md) · [Issues](https://github.com/scottconverse/Describer-Workbench/issues)

## What it does

| Task | Behavior |
| --- | --- |
| Open media | Local MP4, MKV, MOV, AVI and WebM. Direct video or YouTube URLs download through yt-dlp. |
| Draft descriptions | Gemini, Ollama, the subscription gateway, native Codex/Claude/Antigravity tools or compatible API profiles. Whole video, Next 20 seconds or Next 60 seconds. A character glossary carries over between chunks. |
| Choose models | The exact model ID is kept per route. No silent fallback to another model. |
| Edit and hear | Start, end and text editor, glossary, Scene questions, SRT/VTT import. Preview a cue with the soundtrack. |
| Timing | Descriptions go into the pauses in speech. A pinned local YAMNet detector protects speech. Speed is capped at 1.15x. A description that does not fit pauses the picture. |
| Export | MP4, narrated MP3/WAV, SRT, VTT, TXT and project JSON. Media exports include a coverage file. Voices: Windows SAPI/OneCore, macOS voices, Linux eSpeak NG or optional OpenAI speech. |
| Public meeting mode | For city and council meeting videos. Describes only frames that changed, reads slides, finds votes from a captions file and pauses only for meeting events. Turn it on with the **Public meeting mode** box in **Draft with AI**. See [the manual](docs/USER-MANUAL.md#public-meeting-mode). |
| Developer integration | One serial, durable job queue through Python, CLI, REST/OpenAPI and MCP stdio/Streamable HTTP. |

Manual cues, subtitle import, system voices and export work without an AI key.

## Quick start

| Computer | Download | Install and start | Signing |
| --- | --- | --- | --- |
| Windows x64 (Windows 11 tested) | [Portable ZIP 0.8.4](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-windows-x64.zip) | Extract everything; open `DescriberWorkbench/DescriberWorkbench.exe`. Keep `_internal` beside it. | Scott Converse, Azure Trusted Signing |
| Mac, Apple Silicon, macOS 15+ | [arm64 DMG 0.8.4](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-macos-arm64.dmg) | Open the DMG; drag the app to Applications. | Ad-hoc only; not notarized |
| Ubuntu 24.04 x64 | [DEB installer 0.8.4](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-linux-x64.deb) | `sudo apt install ./DescriberWorkbench-0.8.4-linux-x64.deb` | Unsigned |
| Other Linux x64 | [Portable tar 0.8.4](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-linux-x64.tar.gz) | Extract; run `DescriberWorkbench/DescriberWorkbench`. See the [platform guide](docs/UNIX-INSTALL.md). | Unsigned; not acceptance-tested |

There is no Intel Mac build. Compare each download with the release's `SHA256SUMS.txt`:

```powershell
Get-FileHash .\DescriberWorkbench-0.8.4-windows-x64.zip -Algorithm SHA256
```

Then follow the [first project without programming](docs/QUICK-START.md).

### Ollama

Install and start [Ollama](https://ollama.com/) and a vision model. In **Draft with AI**, choose **Ollama → Refresh models**, then pick an entry marked **vision**, or type its exact ID in the **Exact analysis model ID** field. Ollama receives sampled frames without audio. Tested exact-tag profiles: `gemma4:12b`, `gemma4:26b` and `qwen3.8:27b-q6_K-vision`. See [AI connections](docs/AI-CONNECTIONS.md).

### Editing

Select a description to seek to its start. Times accept seconds, `MM:SS` or `HH:MM:SS`. Changing Start shifts End to preserve cue duration; changing End adjusts only End. Edits apply as you type; Ctrl+Z undoes. **Ctrl+S** saves the project.

## Does it need an API key?

| Workflow | Key / account | Data sent |
| --- | --- | --- |
| Manual cues, subtitle import, playback, native speech/MP3 | No AI key | Stays on this computer |
| Ollama on this computer | None | Frames and prompts to local Ollama |
| Ollama cloud / remote server | Set in Ollama | Sampled frames leave the computer after you confirm |
| Gemini analysis, Ask and Explore | Gemini key | Video with audio, unless you choose a silent upload |
| Native Codex / Claude / Antigravity | Your existing sign-in | Sampled frames and prompts after you confirm |
| Subscription gateway | Existing client-key file | Sampled frames through the selected gateway account |
| OpenAI-compatible / Anthropic API | Profile or API key | Sampled frames to the selected endpoint |
| OpenAI speech | OpenAI key | Description text after you confirm |

Keys use Windows DPAPI, macOS Keychain or Linux Secret Service. Projects and job files never hold keys. The app sends no analytics. Details: [privacy and recovery](docs/USER-MANUAL.md#12-privacy-storage-and-recovery).

## Project status

Version 0.8.4 runs on Windows, Mac and Linux. Know these limits first:

- **Drafts can be wrong.** In earlier tests, drafts named the wrong person, left out a short sequence and misread text. Since 0.8.4, review is optional: cues marked **Needs review** are spoken in exports and keep their tag. To block MP4, MP3 and WAV export until a person checks them, turn on **Require review before media export** in Settings.
- **Meeting numbers are from a small test.** On 13 test videos with `gemma4:12b`, 67.6 % of cues were correct and 3.8 % were wrong or made up. Results change from run to run.
- **Signing and updates.** Only the Windows build has publisher signing. Check for updates works in the app on Windows only; Mac and Linux updates are manual.
- **Not tested yet.** No person has done a full listening review of the exports. No one has tested the app with VoiceOver, Orca, NVDA or JAWS.

Each release has `release-verification.json` and `SHA256SUMS.txt`. See the [0.8.4 release notes](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.8.4) and [all releases](https://github.com/scottconverse/Describer-Workbench/releases).

## Run from source

Python 3.11+ (tested with 3.13). Mac and Linux: install the prerequisites, then run `python3 tools/install_unix.py` (see the [platform guide](docs/UNIX-INSTALL.md)). Windows:

```powershell
git clone https://github.com/scottconverse/Describer-Workbench.git
cd Describer-Workbench
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,http,mcp,dev]"
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m pytest -q
# Build the portable folder:
.\build.ps1
```

Put FFmpeg and FFprobe on PATH or in `bin/`. The website source is in `website/`; build it with `tools/build_site.py --output <folder>`. GitHub Pages publishes it from `main`.

## Documentation

- [Quick start](docs/QUICK-START.md): download and a first project, no programming.
- [User manual](docs/USER-MANUAL.md): walkthrough, reference and troubleshooting.
- [Architecture](docs/ARCHITECTURE.md): components, sequences and data boundaries.
- [Platform installation](docs/UNIX-INSTALL.md): Mac and Linux installs, credentials and removal.
- [AI connections](docs/AI-CONNECTIONS.md): subscription, CLI and API setup.
- [Developer guide](docs/DEVELOPER-GUIDE.md): Python, CLI, REST and MCP contracts.
- Records: [0.7.0 acceptance](docs/V070-ACCEPTANCE.md), [stabilization plan](docs/STABILIZATION.md), [public audit](docs/PUBLIC-AUDIT.md), [parity](PARITY.md), [audit](AUDIT.md).

## Contributing

Open an [issue](https://github.com/scottconverse/Describer-Workbench/issues). Include the app and operating-system version, CPU architecture, exact provider and model, steps, expected result and redacted logs. Never post keys, private video, complete settings or unsanitized projects.

## Provenance and license

Independently written Python source reconstructs a documented Omni Describer workflow from supplied documentation and static analysis. This is **not recovered original source** and implies no original-author endorsement. Original executables, recovered bytecode and branding are not distributed. Attributed translations keep their original terms in `third-party-licenses/Omni-Describer.txt`.

New Workbench code is licensed under **Apache-2.0** ([LICENSE](LICENSE), [NOTICE](NOTICE)). Third-party components keep their own terms, including Qt/PySide, FFmpeg and the original translations. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) before redistribution.
