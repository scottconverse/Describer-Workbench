# Start here — Describer Workbench 0.8.4

For Windows, macOS and Linux · documentation updated November 13, 2026.

Make one short description first. You do not need an AI account, programming, or a local AI model for this walkthrough.

## 1. Download for your computer

| Computer | Download | Install and start | Publisher signing |
| --- | --- | --- | --- |
| Windows x64 (Windows 11 tested) | [Portable ZIP](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-windows-x64.zip) | Extract everything; open `DescriberWorkbench/DescriberWorkbench.exe`. Keep `_internal` beside it. | Scott Converse, Azure Trusted Signing with Microsoft timestamps |
| Mac, Apple Silicon, macOS 15+ | [arm64 DMG](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-macos-arm64.dmg) | Open DMG; drag the app to Applications. | No Apple publisher certificate or notarization; ad-hoc integrity only |
| Mac, Intel, macOS 15+ | No Intel DMG (dropped in 0.7.0) | Install from the repository; see the [platform guide](UNIX-INSTALL.md). Not tested on Intel. | None (source install) |
| Ubuntu 24.04 / compatible Debian desktop, x86-64 | [DEB installer](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-linux-x64.deb) | `sudo apt install ./DescriberWorkbench-0.8.4-linux-x64.deb`; open Describer Workbench from the applications menu. | Unsigned |
| Other Linux x86-64 desktops | [Portable tar](https://github.com/scottconverse/Describer-Workbench/releases/download/v0.8.4/DescriberWorkbench-0.8.4-linux-x64.tar.gz) | Extract; run `DescriberWorkbench/DescriberWorkbench` after installing native dependencies. | Unsigned; other distributions not acceptance-tested |

Mac: choose **Apple Silicon** for an M-series Mac (Apple menu → About This Mac). There is no Intel Mac download. Use the normal Privacy & Security approval if macOS blocks opening the downloaded app; no Apple publisher certificate or notarization is available. Do not disable Gatekeeper. Linux: the DEB installs required media and speech dependencies; the tar requires you to install them yourself. See [platform installation](UNIX-INSTALL.md).

Each release provides `SHA256SUMS.txt` for checking download integrity. Windows is the only publisher-signed distribution. Ollama, large AI models, subscription tools and videos are installed separately. Repository setup for Windows is in the [manual](USER-MANUAL.md#14-runtime-and-source-setup); Mac/Linux have a [per-user installer](UNIX-INSTALL.md#install-from-the-repository).

## 2. Open a video and save a project

1. Start Describer Workbench. Choose **Open video** and select an actual MP4, MKV, MOV, AVI or WebM file. Extract downloaded archives first.
2. Press the **Play/Pause** icon. Confirm that the picture and original sound play.
3. Pause where you want to describe something. Choose **Add at playhead** in Descriptions.
4. Type one short sentence about what is visible. The new cue starts at the playhead and lasts three seconds, bounded by the video end. Edit Start/End if needed.
5. Choose **File → Save project**, using a name ending in `.adproject`. The project refers to the original video; keep both.

## 3. Listen and export

Enable **Speak descriptions** and play the passage. Choose an installed narration voice in **Settings → Export voice** or in **Export**: Windows voices on Windows, macOS voices on Mac, eSpeak NG on Linux. OpenAI speech is optional and sends text to a paid remote service after confirmation.

Use **Export → Subtitles · .srt** for a simple text output. For narrated MP3/WAV or described MP4, the engine measures narration and checks independent speech protection. If asked, explicitly install the small speech detector; no large vision model is needed. Missing detector or unresolved cues block complete narrated output. A sentence that cannot fit safely pauses the original soundtrack; MP4 also freezes the picture. Listen to the exported file before sharing it.

## 4. Try an AI draft when ready

**Since 0.7.0:** your existing descriptions stay by default. After drafting, review the proposals and explicitly approve any replacements. Cancel keeps your project unchanged; Ctrl+Z undoes the complete accepted draft.

Use **Save project as** to keep a separate comparison copy. Choose **Draft with AI**, select your connection and exact model ID, then try **Next 20 seconds**. Local Ollama needs a separately installed vision model. Claude, Codex and Antigravity use their installed CLI sign-in or the existing subscription gateway. API credits are separate. [Connection setup](AI-CONNECTIONS.md) explains each route and its limits.

**City and council meetings (0.8.0 and later):** Public meeting mode describes only what changed, reads slides and finds votes. To use it, tick **Public meeting mode** in **Draft with AI** (0.8.2 and later). See [Public meeting mode](USER-MANUAL.md#public-meeting-mode) in the manual.

Review is optional (since 0.8.4): you can export the draft as it is. If you review, check facts, names, omitted actions, printed text and timing. Completion and a green placement status do not prove accuracy. Sampled-frame routes cannot hear dialogue. The engine protects sound independently, but that detector can also make mistakes.

## 5. Keep your work and update safely

Save the project, source video and engine narration workspace together. Reopen the project to continue editing. When moving computers, locate the video again, re-enter credentials and repair narration if the referenced audio is missing. Installed voices and Windows-protected keys do not migrate.

Windows uses the signed updater or a separately extracted portable ZIP. Mac/Linux updates are manual: quit the app, download the matching architecture and replace/install it while retaining the previous copy. Settings and projects are separate from the application. [The full manual](USER-MANUAL.md) covers recovery, shortcuts, privacy and troubleshooting; [the technical guide](DEVELOPER-GUIDE.md) covers CLI, API and MCP.

Native package checks cover startup, storage, measured voice, exports and developer transports. Active screen-reader usability and human listening quality have not been certified. See the [platform evidence and limitations](UNIX-INSTALL.md#verification-status).
