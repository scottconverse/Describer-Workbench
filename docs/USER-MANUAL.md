# Describer Workbench user manual

For desktop version **0.4.2** · Documentation updated November 1, 2026

[Download](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.4.2) · [Project](https://github.com/scottconverse/Describer-Workbench) · [Architecture guide](ARCHITECTURE.md)

## Part I — Everyday use, no programming required

## 1. What you can make

Describer Workbench helps you write short spoken descriptions of a video's visual information. Each description is a **cue**: a start time, an end time and text. You can write cues yourself, import subtitles as a starting point, or ask an AI model to draft them. You then correct and listen to the result.

The outputs are an editable project, an SRT subtitle file, plain text or a narrated MP3 containing the original soundtrack mixed with descriptions. Workbench does not create a new video file or an embedded selectable audio-description track.

AI descriptions need editorial review. In particular, the Ollama path sees still images sampled from the video and receives no audio. It cannot know when someone is speaking or confirm a spoken name. You decide what is accurate, useful and safe to say over the soundtrack.

## 2. Install and choose a working mode

Download the Windows portable ZIP from the release page. Extract everything, then open `DescriberWorkbench/DescriberWorkbench.exe`. Keep the `_internal` directory with the executable. The current portable build is unsigned. It includes the application runtime and media tools; it does not include Ollama, AI model weights or videos.

Use one of these paths:

| Mode | Setup | Best starting task |
| --- | --- | --- |
| Manual/offline | No AI key. Use installed Windows voices. | Open video, add one cue, listen and export. |
| Local AI | Install/start Ollama and install a vision model separately. | Choose Ollama, refresh models, test a short range. |
| Gemini | Enter your Google Gemini API key/model in Settings. | Confirm upload and analyze a short clip. |
| Ollama cloud/remote | Configure sign-in/access in Ollama or the remote server. | Select a vision-capable tag and confirm transmission. |

OpenAI is optional for speech synthesis. It is not an analysis provider in this version. No key is needed for manual editing, subtitle import, local playback or native Windows speech. A local AI model still needs enough RAM/VRAM for that model; the app does not estimate hardware requirements.

## 3. Your first project

1. Choose **Open video** (Ctrl+O). Select a local video such as an MP4 of Big Buck Bunny. Use the video file itself, not an SRT subtitle, soundtrack or folder. The default selector lists MP4, MKV, MOV, AVI and WebM. **All files** exposes other files, but decoding is still required.
2. Press **Play / Pause** to confirm playback and sound. The position slider and **−10 s / +10 s** buttons move through the video.
3. For a manual first cue, type `0` in Start and press Tab to leave that field. Then enter `3` in End and a short description of the opening image. Choose **Add**, then select the new cue's row. This inserts a cue; **Apply edit** changes a selected existing cue.
4. Save with Ctrl+S and choose a name ending in `.adproject`. The project points to your video; it does not copy it. Keep the video available.
5. Select the cue in the table. It seeks to the cue's start. Enable **Speak descriptions**, then play. Adjust player volume with the main slider and speech volume in Settings.
6. Correct the words or timings and choose **Apply edit**. Save again. Use **Export → Subtitles (*.srt)** for a simple first output, or choose MP3 for spoken narration mixed with the soundtrack.

For an AI first draft, save your project, seek to the intended beginning and follow section 5. Start with **Next 20 seconds** or **Next 60 seconds** before requesting a whole film.

## 4. Find your way around

The top row opens media, starts analysis, opens Settings and cancels a job. The **Analysis AI** row selects provider, exact model and analysis range. Under the video are playback controls, the current description, the cue table and editor. The bottom area has editorial presets and a status log.

The **File** menu includes projects, subtitle import, glossary, voice tools, original-data import and update checks. **Help** (F1) opens the built-in help. Some operations are unavailable while a background job is active; wait for completion or cancel it.

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open video |
| Ctrl+U | Download/open URL |
| Ctrl+Y | Open YouTube through the same download workflow |
| Ctrl+Shift+O | Open project |
| Ctrl+S | Apply selected cue editor and save project |
| Ctrl+I | Import SRT/VTT after opening video |
| Ctrl+, | Settings |
| Ctrl+E | Export |
| F1 | Built-in help |

There is no documented global Space shortcut for playback. Use the Play / Pause control. Ordinary Tab navigation follows Qt focus order.

## 5. Draft with AI

### Local Ollama

Start your separately installed Ollama server. In Workbench choose **Ollama** and **Refresh models**. Entries show their exact tag, local/cloud status, reported vision capability and whether they are loaded. A text-only model cannot analyze video, even if it answers ordinary chat prompts.

Choose an installed vision entry. To type a custom tag, enter its exact ID and leave the field with Tab. **Test connection** first checks capability and then sends a short text prompt; a successful reply does not prove visual understanding. Refresh itself makes metadata requests, not inference requests or downloads.

If the server is elsewhere, set its root address and optional key in Settings. Local default: `http://127.0.0.1:11434`. Remote addresses require HTTPS. For cloud tags, sign in using Ollama itself. Workbench has no OAuth flow. Remote/cloud inference asks permission before sending sampled frames/prompts and may use paid allowance. Local server selection alone does not guarantee private inference if Ollama routes the chosen tag to its cloud.

### Gemini

Enter **Gemini API key** and **Gemini model** in Settings. Choose Gemini in the main picker and use a model your account can access. Analyze, Ask and Explore ask before uploading video. Clips include audio by default; **Remove audio before uploading video** removes it and also removes the model's evidence for dialogue and audible names. Provider account access, quotas and charges apply.

### Range, prompts and replacement

Choose **Whole video**, **Next 20 seconds** or **Next 60 seconds**. Next ranges start at the current playhead and stop at the end of the video if necessary. Pick a prompt preset or edit the editorial guidance, then choose **Analyze video**.

**Analysis replaces the project's cue list after confirmation, including when only a short range is selected.** It does not append or merge a range into existing cues. Returned times remain absolute video times. Save before comparing models, copy the `.adproject` file in Windows File Explorer, and use **Open project** on the copy. This version has no Save As command; Ctrl+S continues saving the currently opened project.

The log reports prepared ranges, response progress and available token metadata. Long jobs run sequentially. At the default Ollama frame interval, a 60-second range normally means four requests. Do not assume a single short response represents the whole requested range; inspect the final cue coverage.

### Model settings that reproduce tested requests

| Exact tag | Thinking | Maximum output | Context |
| --- | --- | --- | --- |
| `gemma4:12b` | Off | 32,768 tokens | 65,536 tokens |
| `gemma4:26b` | Off | 32,768 tokens | 65,536 tokens |
| `qwen3.8:27b-q6_K-vision` | Off | 32,768 tokens | 65,536 tokens |

These use the model's native sampling settings. They are request profiles, not globally installed Ollama configuration or guaranteed public registry names. Renamed models and aliases do not inherit them. The Qwen vision tag was available in the test installation; the text-only Q6 tag is unsuitable. DeepSeek 1017 tags request low effort but still must pass the vision check. Other tags use existing adapter defaults; the UI has no universal effort/context/output control.

### Glossary and consistency

With **Recognize characters during analysis** enabled, the model is asked to return stable visual identities. Generated glossary entries are carried into later chunks. **File → Character glossary** lets you correct them. It is stored in the project and can affect future analysis, Ask and Explore.

For a clean model comparison, use identical media/range/prompts and clear the glossary before each run. Keep each result in a separate project. Do not let incorrect identities become established facts. Ollama is told to leave names unknown because it has no audio; a visual label is not an established personal name.

## 6. Edit and review descriptions

Select a cue in the table. Edit **Start**, **End** and description text below it, then choose **Apply edit**. The table itself is read-only. **Add** inserts the values as a new cue, but does not move the selection to it. **Select the newly added row before Ctrl+S**: saving applies the editor to the selected row, so leaving the old row selected can overwrite that old cue with the new values. **Delete** removes the selected cue after confirmation.

Times accept numeric seconds (`62.5`), minutes/seconds (`1:02.5`) or hours/minutes/seconds (`00:01:02.5`). The cue must have nonempty text and an end after the start, within the video duration. **Set Start and leave the field before setting End**: leaving Start shifts End by the start-time change, with a minimum 0.1-second duration. Check both values before applying. Ctrl+S applies the current selected cue editor before saving. Apply edits explicitly before export or another operation.

Use this review sequence:

1. Watch the source scene and verify visible actions, objects, identities and chronology.
2. Remove guesses, redundant dialogue and descriptions of sounds already audible.
3. Listen for a suitable opening in the soundtrack. Ollama cannot do this for you.
4. Fit the words comfortably in the cue window; shortening text is often better than fast speech.
5. Check adjacent cues, continuity and overall coverage. A valid timestamp is not proof of useful timing.

Automatic generated-cue normalization skips malformed rows, repairs overlaps, removes consecutive repetitions and bounds timings. This is structural cleanup, not editorial accuracy checking. Manual/imported cues still need review for overlap and readability.

## 7. Ask and explore a scene

**Ask about scene** asks for a question and a context window from 1 to 120 seconds around the current position. The player pauses and the selected provider analyzes the region. Answers appear in a conversation dialog. **Add to descriptions** inserts the answer as a four-second cue at the captured position, bounded by the video end. Edit its timing and text before using it. Conversation history is session memory, not a saved project field.

**Explore scene** requests an AI-generated object layout around the current position. It is a simplified 0–10 grid, not measured coordinates or an interactive reconstruction of the video. Models can omit or misplace objects.

| Explorer key | Action |
| --- | --- |
| Arrow keys | Move one grid unit |
| D | Announce layout summary |
| L | List object names |
| Shift+L | Choose/jump to an object |
| Enter | Describe the nearest returned object |

Both tools use the selected analysis provider and applicable transmission confirmations. Ollama uses sampled frames without audio. Close the dialog to return to the editor.

## 8. Listen, choose voices and export

**Speak descriptions** enables speech when the playhead enters a cue. Playback uses the selected Qt Windows voice, or optional active screen-reader output. Player volume and speech volume are separate. **Allow new descriptions to interrupt speech** chooses interruption rather than queued speech. Seeking stops the current speech.

The **Audio export speech engine** is separate from playback voice:

| Engine | What it uses |
| --- | --- |
| Windows | 64-bit SAPI voices installed in Windows |
| Windows 32-bit | 32-bit SAPI via the SysWOW64 PowerShell host |
| Windows OneCore | Installed Windows OneCore voices |
| OpenAI | Configured API key, model, base voice/preset and paid remote synthesis |

Select an engine in Settings, then use **File → Select Windows export voice** for the native engine's voice list. Changing engine clears the old export voice selection. **Test selected export voice** synthesizes a preview. OpenAI preview and export confirm before sending text.

**Manage voice presets** adds, edits, deletes or imports original `voices.json` personalities. Choose the active preset in Settings. Presets set a base voice, speed and delivery instructions; instructions are sent only for the compatible `gpt-4o-mini-tts` family. They do not turn a Windows voice into an OpenAI voice.

Export choices:

- **SRT:** timed UTF-8 descriptions. This is not a speech transcript unless your cues are transcripts.
- **Plain text:** one description per line; timing is omitted.
- **MP3:** original soundtrack mixed with synthesized cues, stereo output. Silent video gets a silent bed. Long utterances are sped up to fit; source surround channels are downmixed. Background ducking is applied once with 50 ms fades around narration windows. Listen to the finished mix for clipping, intelligibility and dialogue conflicts.

MP3 does not embed itself back into a video. Save the `.adproject` as well so you can revise it later.

## 9. Import and download

Open video first, then **Import SRT / VTT** (Ctrl+I). Import replaces current cues after confirmation. UTF-8, UTF-16 with a byte-order marker and Windows-1252 fallback are supported. Empty/zero-length subtitle entries are skipped with warnings. The parser handles the tested timestamped variants; it is not a general preservation tool for WebVTT styling, regions or metadata.

**Open URL** / **Open YouTube** asks for a URL and destination folder, downloads through yt-dlp and opens the resulting video. Quality is configurable. Use content you are entitled to download. Public extractor behavior changes and was not verified against live YouTube in the release acceptance; a local HTTP download fixture was tested.

**File → Import original data** explicitly imports original description/glossary JSON or preferences. It supports plain JSON, obfuscated `settings.dat2`, and older machine-bound `settings.dat` with its matching `key.salt` on the original Windows machine. The machine-bound path has synthetic-fixture coverage, not acceptance with a user's credentials. Prompt data can be imported through this workflow; voice personalities use the voice manager. Original files are read only and API keys are excluded from preference import. A Workbench project is a separate format.

## 10. Settings reference

| Setting group | Meaning |
| --- | --- |
| Provider fields | Gemini key/model; Ollama root URL, optional key; OpenAI key, speech model and base voice. Analysis provider/exact Ollama tag are in the main picker. |
| Description language / verbosity | Requested output language and Short/Standard/Detailed guidance. Model compliance is not guaranteed. |
| Chunk duration / enable chunking | Gemini segment length (15–1800 seconds). Ollama additionally caps chunks at eight frame intervals even if chunking is disabled. |
| Gemini frames per second | FFmpeg segment preparation, 1–30 fps. Despite the UI label, it also affects the prepared video from which Ollama samples frames; Ollama's sampling interval is separate. |
| Ollama frame interval | 1–10 seconds, maximum eight frames per request. Wider intervals reduce temporal coverage. |
| Ollama timeout | 30–1800 seconds; default 600. An idle network read can take up to 120 seconds or the shorter configured timeout to return. |
| Gemini temperature | Generation sampling parameter. Tested Gemma/Qwen profiles omit it and preserve native sampling. |
| Recognize characters | Requests and carries a visual glossary. |
| Remove audio | Strips audio from prepared video. Gemini then loses dialogue evidence; Ollama already receives no audio. |
| Background ducking | −40 to 0 dB, default −15 dB. More negative reduces the original bed more. |
| Speech rate / volume | Native export voice rate −10 to 10; speech volume 0–100 for Qt/native Windows speech. The app does not apply this volume setting to OpenAI exports or a screen reader's own output. |
| Playback voice / output | Qt Windows voice or active screen reader; separate from export engine/voice. |
| Interruption | Allow new cue speech to interrupt, or queue it. |
| Interface language | English, Arabic, Spanish, French, Italian, Portuguese, Russian, Turkish, Ukrainian or Vietnamese. Arabic uses RTL. Unmatched strings/help/logs fall back to English; no native-speaker acceptance is claimed. |
| Presets | Main prompt manager stores guidance per description language. Voice manager stores speech personalities. |
| Download quality | Best, 360p, 480p, 720p or 1080p, subject to available formats. |
| Notifications / diagnostics | Enable sounds and choose DEBUG through CRITICAL logging. |
| Gemini BLOCK_NONE | Requests supported adjustable thresholds only; provider core safeguards/account restrictions remain. |
| Update feed / startup check | Optional trusted HTTPS or local JSON feed. Startup checks are opt-in; no public feed is supplied. |

## 11. Accessibility and keyboard use

Controls have Qt accessibility labels; timed cues are exposed in a table and main file actions have shortcuts. Scene Explorer has its own keys. **Screen reader** playback asks an active supported reader to speak, with asynchronous Windows speech fallback if unavailable. Workbench cannot measure screen-reader speech duration for ducking.

NVDA/JAWS end-to-end acceptance was not performed. The presence of controller modules or accessible labels does not establish usability for every assistive setup. Test your reader, voice and workflow before relying on them for a production session.

## 12. Privacy, storage and recovery

Projects are user-selected `.adproject` JSON files with `version`, `video`, `duration`, `cues` and `glossary`. Video is an absolute path, not embedded media. Moving a project to another computer requires moving the media separately; **Open project** prompts you to locate a missing video and revalidates cue durations. Projects contain description text and paths; inspect before sharing. Save is written to a sibling temporary file then replaced.

Settings live at `%LOCALAPPDATA%/DescriberWorkbench/settings.json`. API keys are DPAPI-protected for the current Windows user. Moving this file to a different account does not move working keys. If a key cannot be unlocked, re-enter it. Damaged/incompatible settings load defaults with a warning and are preserved in a `.recovery-*` copy before saving. Other settings are not encrypted.

Logs live beside settings, rotate at 1 MiB with one backup and redact configured key strings. They may still include paths, descriptions and error text. Temporary clips/frames/audio are created for jobs and normally removed when their temporary directories close. Downloaded videos and exported files remain where you chose to save them.

**Cancel operation** stops owned FFmpeg work and prevents subsequent chunks. It is cooperative around network streaming; an idle read may delay completion. It cannot retract already transmitted media or cancel a provider charge. Closing during a job requests cancellation and keeps the app open until the job ends. Save before long operations.

For manual updates, close Workbench and extract the new portable build separately; retain your old folder and projects until the new version works. Settings remain under LocalAppData. The optional trusted-feed updater stages a hash-verified ZIP, then requests installation/restart. It swaps sibling directories after the exact running process exits and retains the previous folder; receipts go under LocalAppData's `updates` directory. To roll back, close the app and restore the retained folder. Do not configure an untrusted update feed: a matching hash is not a publisher signature. The release does not configure an automatic GitHub update feed.

## 13. Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Cannot see Bunny | Use Open video and find the actual MP4/MKV. All files expands the filter. SRT and separate audio tracks are not video projects. Extract ZIP archives first. |
| Video opens but cannot play | Check the log and source with FFprobe/another player. Codec/container support is not guaranteed by the extension. Try an ordinary H.264 MP4 copy. |
| No Ollama models | Start Ollama; check the root URL, refresh and verify installed models in Ollama. Workbench does not download weights. |
| Model says no vision | Choose the installed vision-enabled tag. A text-only model cannot become visual through a larger context. |
| Connection test works, analysis fails | Text connectivity is narrower than image/JSON compatibility. Check capability, model limits, exact tag, shorter range and log. |
| Output cut off / no descriptions | Truncated output is rejected and existing cues are preserved. Check exact-tag profile, concise guidance, clean/correct glossary and a shorter range. Other model tags use smaller adapter defaults. |
| Character/action wrong | Rewatch, correct the glossary/text and timing. Never interpret a completed request as accuracy acceptance. |
| Narration talks over dialogue | Manually move/shorten cues. Ollama receives no audio and does not detect dialogue gaps. |
| Nothing happens when analyzing | Open video first, finish/cancel any current job, confirm replacement/transmission prompts and inspect the log. |
| No voice / native export fails | Select an installed voice from the correct engine/bitness. Test export voice; playback and export use separate settings. |
| MP3 speech too fast | Shorten the cue text or widen its window while respecting the soundtrack; export fits overlong speech by speeding it up. |
| Cloud authentication/quota error | Check provider access, key, model ID and billing/limits. Workbench does not silently switch providers. Never paste keys into an issue. |
| Project video missing | Relocate the original video when prompted. The project contains no copy. |
| Cancel seems slow | Wait for the pending network read/timeout. Closing waits for the worker; completed uploads cannot be undone. |

## Part II — Technical users and developers

## 14. Runtime and source setup

The supported delivered artifact is a 64-bit Windows PyInstaller folder bundle. Source was tested with Python 3.13, PySide6 6.12.0, google-genai 2.34.0, yt-dlp 2026.10.26, accessible-output2 0.17 and cryptography 50.0.2. FFmpeg/FFprobe are separate source prerequisites; the portable bundle includes them. Native speech requires the corresponding Windows hosts/voices.

```powershell
git clone https://github.com/scottconverse/Describer-Workbench.git
cd Describer-Workbench
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Place `ffmpeg.exe` and `ffprobe.exe` on PATH or in `bin/`. Run `build.ps1` for the portable build. It installs PyInstaller 6.22.3, copies missing media tools and writes `dist/DescriberWorkbench/`. Creating `.venv` explicitly avoids the build script choosing another `py -3` interpreter. Build outputs are ignored by Git. Do not rebuild into an active installation; preserve the running folder and accept a candidate separately.

## 15. Architecture and data flow

![System architecture and external service boundary.](diagrams/system.svg)

`app.py` owns Qt UI, state, confirmations, worker lifecycle and project operations. `model_picker.py` manages discovery and selection. `services.py` coordinates segmentation, provider dispatch, generation, settings and export. `models.py` implements Ollama HTTP/discovery/streaming and frame extraction. `project.py` validates JSON/cues, imports subtitles and persists projects. Dedicated modules handle Windows speech, playback queues, compatibility, translations, diagnostics and updates.

![Analysis sequence: snapshot, segment, select provider, validate and replace on success.](diagrams/analysis.svg)

The GUI copies settings/project before a generation job. FFmpeg prepares successive clips. Ollama extracts at most eight images per request; Gemini uploads the segment. Replies are parsed and normalized, relative times are offset into the video, and the new cue list/glossary is committed to the GUI when the job completes. A failed/truncated/cancelled generation does not apply its partial result to the displayed project.

See [ARCHITECTURE.md](ARCHITECTURE.md) for source-linked responsibilities and Mermaid sequences. The site diagrams are static SVG with textual explanations for nonvisual reading.

## 16. Adapter contracts and limits

Ollama metadata endpoints are `/api/tags`, `/api/ps` and `/api/show`; generation streams newline-delimited JSON from `/api/chat`. The adapter blocks redirects, uses a validated root URL and requires HTTPS off loopback. Every analysis/scene request verifies reported `vision` capability. Cloud/remote classification uses metadata, known cloud suffixes and server location; it is a disclosure heuristic, not network attestation of the model implementation.

Local structured requests set `format:json`. Hosted requests omit it because that API path does not support the same structured-output parameter. Prompts still ask for JSON and replies are parsed. A missing final event, empty answer, `done_reason:length`, malformed JSON, timeout or excess response size is an error; there is no silent fallback. Response accumulation is capped at 4 MiB, including streamed thinking. Cancellation is checked between events; HTTP reads have a maximum 120-second idle timeout bounded by the configured timeout.

Matched Gemma/Qwen tags override request options to `num_predict:32768`, `num_ctx:65536`, omit temperature and use `think:false`. DeepSeek 1017 uses `think:"low"`. Other tags start with `num_predict:8192` and the configured sampling value; they do not inherit a forced 64K context. These are implementation limits, not general claims about a model's maximum supported output.

Gemini uses google-genai file upload, processing polling and generation with the selected model/key, JSON response request and optional supported safety thresholds. Retryable 429/5xx errors receive bounded backoff. File deletion is attempted on exit. Provider restrictions/retention remain external. OpenAI speech uses `/v1/audio/speech` with description text; it is independent of the analysis picker.

## 17. Project format and integrations

Example `.adproject` (illustrative; update the media path):

```json
{
  "version": 1,
  "video": "C:/media/example.mp4",
  "duration": 60.0,
  "cues": [
    {"start": 2.0, "end": 5.0, "text": "A cyclist crosses the bridge."}
  ],
  "glossary": "cyclist: Blue helmet and yellow jacket."
}
```

Project schema version is independent of application version. Loading requires version 1, finite nonnegative timings, valid text and cue bounds. Import validation is strict; model-output normalization is more tolerant and logs skipped rows. Settings schema is separate and migrates bundled presets. Do not use source-controlled settings files to distribute credentials.

Optional update-feed shape (example only; no service is supplied):

```json
{
  "application": "DescriberWorkbench",
  "version": "0.4.3",
  "url": "https://example.org/DescriberWorkbench.zip",
  "sha256": "REPLACE_WITH_THE_ACTUAL_64_HEXADECIMAL_CHARACTER_DIGEST"
}
```

The example digest is deliberately invalid and must be replaced. Remote feed/package URLs require HTTPS. The updater validates application/version/hash, rejects unsafe archive paths/symlinks and requires the portable EXE plus `_internal` structure. A downloaded package is staged before a separate installation confirmation. No original-app updater/feed is reused.

## 18. Tests, evidence and extending the app

Run the standard suite on Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.local_acceptance "C:\media\sample.mp4" "C:\receipts\workbench"
```

The optional second command opens an owned window, makes a short clip, tests editing/seeking/playback, DPAPI, native speech and MP3. It writes local artifacts and is not a cloud test. Additional acceptance scripts in `tests/` exercise library formats, audio mixing and update staging/rollback; read their inputs before running. `verify_payload.py` compares frozen source code fingerprints to the executable and checks reader dependencies. It does not prove human usability or visual accuracy.

The accepted 0.4.2 suite passed 28 tests. Actual GUI Bunny seconds 62–122 with Gemma 26B and Qwen Q6 completed four requests per model with a clean initial glossary. The eight requests carried the requested off/32K/64K settings, runner contexts were 64K and no thinking output or truncation occurred. Projects matched responses; cue counts (29/25) are not quality scores. The release verification asset pins the executable and source identity. Raw local receipts are excluded from Git/public downloads because they include images and paths.

Still unverified: live Gemini/OpenAI/keyed-cloud operation, full-film analysis/AD quality, NVDA/JAWS user acceptance, native-speaker translations, third-party legacy voices, live public YouTube extraction and a real production update cycle. Fixtures validate adapter/format behavior without proving live provider acceptance. Docs/site-only publication leaves the accepted binary/tag unchanged.

When extending a provider, trace selection → saved exact tag → capability/preflight → confirmation → request → normalized response → GUI/project. Preserve cancellation and existing cue data on failure. Add focused affected tests and document real transmission/compatibility limits. Do not claim another provider is supported solely because it is named by a discovery endpoint.

## 19. Support and license notes

Report issues at the [GitHub issue tracker](https://github.com/scottconverse/Describer-Workbench/issues). Include app/Windows version, exact tag/provider, range, reproducible steps and redacted logs. Share a public sample only if you have the rights. Omit keys and private paths/media.

This is newly written reconstruction source, not recovered original source or an original-author-endorsed release. No blanket license has been assigned to new Workbench code. Third-party dependencies/translations retain their terms; public source visibility does not grant a new open-source license. See [third-party notices](../THIRD-PARTY-NOTICES.md).
