# Describer Workbench 0.4.2

A Windows desktop reconstruction of the core Omni Describer workflow, built from the supplied distribution's documentation and static analysis. This is newly written Python source, not the original author's recovered source tree. It uses a separate application name and settings directory.

The Git repository tracks application source, tests, build instructions, assets, audit documentation and third-party license notices. Portable runtimes, rollback copies, local acceptance receipts, working state, credentials and the desktop media library stay outside version control. References to `evidence/` below refer to the retained local delivery; those machine-specific files are not part of the repository. The original executable and recovered bytecode are not included.

## Run the Windows build

Download the Windows portable ZIP from the [0.4.2 release](https://github.com/scottconverse/Describer-Workbench/releases/tag/v0.4.2), extract it, and open `DescriberWorkbench/DescriberWorkbench.exe`. Keep that EXE with its `_internal` folder. For a local source build, the executable is under `dist/DescriberWorkbench/`. The portable build includes Python, Qt and FFmpeg. Windows speech uses the installed Windows speech subsystem. This portable build is unsigned. Ollama and model weights are installed separately; they are not included in the download.

1. Open a local video. Choose Gemini or Ollama in the Analysis AI picker. Gemini uses your key in Settings; Ollama can use a local vision model without an API key. You can also import SRT / VTT or edit descriptions manually.
2. Select a description to seek to it. Edit start, end and text, then Apply edit or Ctrl+S. Add creates a new cue. Times accept seconds, MM:SS or HH:MM:SS. Moving start preserves the existing duration when focus leaves the field.
3. Play the video with Speak descriptions enabled. Windows speech reads descriptions and lowers the original audio during speech. Review the result; generated descriptions are editorial drafts.
4. Save your session with Ctrl+S as an `.adproject` file. It stores a video path, cues and character glossary, not a duplicate of the video. Relocate the video when prompted if its path changes.
5. Export SRT, plain text (one description per line) or mixed MP3. MP3 uses Windows speech by default; OpenAI speech is available with a key and an explicit export confirmation. Long utterances are sped up to fit their cue windows. Export downmixes original audio to stereo MP3, uses silence for videos without audio, and applies 50 ms fades around ducked windows. Original audio is ducked once before narration is mixed, including exports with more than 20 cues.

Use Ask about scene for a conversation about the current region. Explore scene requests a spatial object layout: arrow keys move, D announces layout, L lists objects, Shift+L jumps, and Enter describes the nearest object. Both use the selected analysis provider. With Recognize characters enabled, analysis requests a character glossary alongside descriptions, including for a single chunk. Later chunks receive the accumulated glossary. Names are requested only when spoken and unambiguously linked; the Ollama frame path has no spoken evidence. Character glossary in the File menu lets you review and correct identities before using them in later analysis and scene requests.

## Model picker and Ollama

The provider/model picker follows TownReporter's separation of saved provider choices, exact model IDs, discovery, readiness and local/cloud labels, adapted to this Python/Qt desktop app. No TownReporter installation or database is required. Reference implementation inspected: https://github.com/scottconverse/TownReporter/tree/8a47331a8f013e78ebeeccad60ad78ca4524f780 .

Choose Ollama, then Refresh models. The list labels each installed tag as local or cloud, reports vision support and identifies loaded models. Selection alone does not generate, download, sign in or switch to another provider. You can also type an exact model tag. The app checks the exact model's reported vision capability before Analyze, Ask, Explore or Test connection; a text-only installation is refused. Test connection sends a small text prompt and reports a reply; it does not prove visual accuracy. Refresh makes metadata requests only. Existing Gemini settings remain intact when switching providers.

The default server is `http://127.0.0.1:11434`. Settings can change its root URL, optional DPAPI-protected API key, frame interval and request timeout. Remote addresses require HTTPS. For hosted tags such as `deepseek-v4.1-flash:1017-cloud`, sign in using Ollama itself. Workbench contains no OAuth flow. Cloud/remote requests prompt before sending frames or using allowance. The exact DeepSeek 1017 tag requests `think: "low"`. Selecting `gemma4:12b`, `gemma4:26b` or the vision-enabled `qwen3.8:27b-q6_K-vision` automatically uses thinking off, a 32,768-token output ceiling and 65,536-token context for Analyze, Ask, Explore and Test connection. These tags retain their native sampling defaults, matching the controlled Bunny tests; the Gemini temperature setting is not sent to them. Other tags retain their existing request behavior. Use the Qwen vision entry: the similarly named text-only Q6 tag cannot analyze video. No DeepSeek or other cloud inference was performed for 0.4 acceptance.

Ollama analysis extracts up to eight 640-pixel-wide timestamped frames per request. Whole-video analysis processes sequential chunks bounded to eight frame intervals; the optional Next 20 seconds or Next 60 seconds range analyzes from the current playhead and replaces current descriptions after confirmation. Returned cues retain their absolute position in the source video. Longer Ask scene windows sample at most eight frames across that window. Gemini continues to use its existing video upload path.

**Ollama currently receives images and text, without audio.** It cannot verify speech, dialogue gaps or audible names. Sampled frames also miss motion between samples. Review visual accuracy, character continuity and every cue's timing; do not treat output as finished audio description. Cancellation prevents subsequent chunks and is checked between streamed events; an idle network read can take up to 120 seconds (or a shorter configured timeout) to return. No automatic provider fallback occurs.

Version 0.4.2 extends the existing `gemma4:12b` profile to `gemma4:26b` and `qwen3.8:27b-q6_K-vision`: thinking off, 32,768 output tokens, 65,536 context tokens and native sampling. All 28 automated checks passed. The actual rebuilt GUI analyzed desktop Bunny seconds 62–122 with both models from clean initial glossaries: eight requests completed without truncation, each runner confirmed 64K context, and no thinking output was received. Gemma saved 29 cues and Qwen saved 25; saved projects matched the actual responses. This verifies request settings and completion, not identical stochastic output or finished AD quality. The published verification summary pins the tested executable hash; local detailed receipts remain in `evidence/acceptance-0.4.2/`.

Version 0.4.1 introduced the larger budget and thinking-off profile for the exact `gemma4:12b` tag. Progress logs count received characters without displaying thinking text. Ollama prompts request visible evidence and no longer ask the image-only model to infer dialogue gaps or audible names. The installed Gemma12 model reports 262,144 tokens of maximum context; this does not establish an equivalent output limit.

Version 0.4.1 installed acceptance: desktop Bunny seconds 62–122 completed across four chunks in 40.069 seconds, producing 29 saved timed cues. Actual playback advanced with a visible frame. Receipts and project: `evidence/acceptance-0.4.1/`. This verifies one minute, not the entire film; glossary identifier text and identity/action errors still require editorial review.

Historical Version 0.4 local acceptance: real `gemma4:12b` Q4_K_M analyzed Bunny seconds 60–80, returning nine valid timed cues in about 85 seconds. An observed character-size/identity error and imprecise action descriptions remain in the saved draft for honest comparison. This is a sampled integration test, not full-film or human AD acceptance. Receipts and the saved `.adproject`/SRT are in `evidence/acceptance-0.4/`. Automated regression results are in `evidence/unit-tests-0.4.log`.

Prompt presets are stored per description language. Manage presets adds, edits and deletes them. Settings includes frame rate, chunk duration, description language, model names, temperature, audio ducking and interruption behavior. It also controls automatic character recognition, silent video uploads, notification sounds and the interface language. The main controls have English plus Arabic, Spanish, French, Italian, Portuguese, Russian, Turkish, Ukrainian and Vietnamese packs; the supplied original translation catalogues now also cover matching settings and dialog labels, with English fallback for unmatched or untranslated strings. Help and diagnostic messages remain English. Arabic uses a right-to-left layout. These new control translations have not had native-speaker review.

## Cloud/data behavior

No credentials ship with this app. It does not inspect the original app's settings. File → Import original data can explicitly import plain JSON or XOR-obfuscated `settings.dat2` preferences without API keys, or the original generated `audio_descriptions` / `character_glossary` JSON schema. Source files remain unchanged. Old hardware-bound Fernet `settings.dat` files require an export from the original app. Static inspection found no original saved-project format; Workbench project persistence is its own feature.

Keys entered in this app are protected with Windows DPAPI for the current Windows account. Settings live in `%LOCALAPPDATA%/DescriberWorkbench/settings.json`. Save that file only on the same Windows account; this is not a portable key vault.

Analyze, Ask and Explore prompt before uploading video to Google Gemini. Analysis transcodes clips to 640 pixels wide with the selected frame rate and includes audio. Uploaded files are deleted in a finally block when possible; provider retention policy applies if cleanup fails. Silent upload removes the audio track before transmission; this also removes dialogue evidence for timing and names. The optional BLOCK_NONE setting requests only the provider-supported adjustable thresholds; it cannot disable core safeguards and account/model restrictions still apply. Google operations use the entered model and key. Model availability and charges depend on the account.

OpenAI MP3 export prompts before sending description text to OpenAI. Video description playback uses the selected Qt Windows voice. File → Test selected export voice previews the selected synthesis engine. Export supports 64-bit SAPI, 32-bit SAPI through the native SysWOW64 host, Windows OneCore and OpenAI. Select Windows export voice enumerates the chosen engine. Changing engine clears the old export voice selection. Settings persist the separate playback voice.

Manage voice presets adds, edits, deletes or imports original `voices.json` personalities. Each preset has a base voice, speed and delivery instructions; choose the active preset in Settings. Delivery instructions are sent only for the compatible `gpt-4o-mini-tts` family. OpenAI previews require the same text-transmission confirmation as export. Keys are never embedded in saved projects. The log displays progress, token metadata and errors; review it before sharing it.

Cancel terminates owned FFmpeg processes and prevents subsequent chunks. It cannot undo a completed upload or API charge. An active cloud request can take up to its timeout to return. Closing during a job requests cancellation and keeps the app open until the job finishes.

## Updates

There is no published Workbench update service for this local reconstruction. The original app's feed and updater are never used. You can configure your own trusted HTTPS feed or select a local feed JSON, then use Check for updates; startup checks are opt-in. A feed has this shape:

```json
{"application":"DescriberWorkbench","version":"0.2.1","url":"https://example.org/portable.zip","sha256":"64 hexadecimal characters"}
```

The ZIP must contain `DescriberWorkbench/DescriberWorkbench.exe` and its `_internal/` directory. A verified download is staged separately. In the portable build, a second confirmation offers installation and restart. The helper waits for the exact running process to exit, replaces the installation through a sibling directory swap, keeps the previous folder for rollback, and writes a receipt under `%LOCALAPPDATA%/DescriberWorkbench/updates`. To roll back, close the app and restore that retained folder. Hash verification protects package integrity relative to the configured feed; it is not code signing. Only configure a feed you trust. No public release, signing or live production self-update is claimed.

## Source and build

Requires Windows, Python 3.13, and FFmpeg/FFprobe. Install the pinned dependencies from `requirements.txt`, then run `python run.py`. `build.ps1` creates a local environment and a PyInstaller folder build. It expects `bin/ffmpeg.exe` and `bin/ffprobe.exe`; if missing, it copies an installed FFmpeg from PATH (including Scoop shims). The application source is under `describer/`.

```
python -m unittest discover -s tests -v
python -m tests.local_acceptance "C:\path\to\video.mov" evidence\acceptance
```

The acceptance script opens an owned window, creates an 8-second local clip, tests editing/seeking/playback, DPAPI, Windows speech and MP3 export. It makes no cloud calls. Mock adapter checks validate chunk offsets, usage handling and upload cleanup without claiming live provider acceptance.

See `PARITY.md` for implemented behavior and remaining differences, `evidence/` for receipts, and `STATE.md` for candidate identity and delivery status.

## Dependency notices

Qt/PySide6 is used under its applicable open-source license; bundled component notices are retained in the build and `THIRD-PARTY-NOTICES.md`. FFmpeg's license is in `bin/FFmpeg-LICENSE.txt` and the portable build notices. FFmpeg project/source: https://ffmpeg.org/ ; installed Windows build provider: https://github.com/GyanD/codexffmpeg . The source ZIP excludes the original executable, recovered bytecode and branding. It includes attributed translation catalogues from the supplied original distribution, with its original license under third-party-licenses/Omni-Describer.txt.

API references consulted: https://ai.google.dev/gemini-api/docs/video-understanding and https://developers.openai.com/api/docs/guides/text-to-speech . No live provider success is claimed.

## Version 0.2 local acceptance

`tests/library_acceptance.py` exercised the desktop library: nine source videos decoded in Qt and transcoded; three-second narrated exports passed for each. All 40 subtitle files imported and roundtripped to SRT, including UTF-16, Windows-1252 Portuguese and single-arrow variants. Four empty Persian cues and one zero-length ASR cue are skipped with warnings. These are sampled media checks, not full-film analysis or human description-quality acceptance.

Separate Sintel M&E, Tears of Steel stereo and six-channel surround clips exported successfully, as did a deliberately silent NASA video. Both 64-bit and confirmed 32-bit SAPI hosts and OneCore produced real WAV audio. A signal fixture measured approximately -15.02 dB ducking; a 21-cue case preserved narration at 0.00 dB relative to the single-cue result. Update staging, bad-hash/traversal rejection, directory replacement and rollback-copy retention were tested with fixtures. Thirteen automated tests pass, including the queued GUI-thread completion regression. Detailed receipts: `evidence/acceptance-0.2/`.

Without API keys, Gemini's live descriptions, character identity, dialogue gaps, scene answers, spatial output, usage reporting, account/model access and cleanup cannot be verified. OpenAI voice rendering, instructions, speed, billing and account/model access also remain unverified. Tests validate their adapters with fixtures, without sending media or description text to either provider. Native-speaker review, NVDA/JAWS acceptance, third-party legacy voices and a real published update/restart cycle remain unverified.

## Version 0.3 audit and offline completion

See AUDIT.md for the requirement-by-requirement comparison and receipt limits. This version adds a real non-interrupting speech queue, optional active screen-reader output, player/speech volume controls, verbosity, optional chunking, download quality, diagnostic logging level, ten genre prompts and five voice personalities. Defaults from an existing installation are preserved; new preset defaults are added once during settings migration.

Scene answers can be added at the captured playback position as a four-second cue, clamped to video duration. Spatial objects are validated and assigned distinct grid positions. Generated rows are validated separately so one malformed timestamp cannot discard valid descriptions; overlaps, reversed end times and consecutive duplicates are handled. Project/import validation remains strict.

File → Import original data accepts generated JSON, plain JSON/settings.dat2 preferences, older hardware-bound settings.dat with the matching key.salt on the original Windows machine, and prompts.json. The voice manager imports voices.json. Original settings files are read only and API keys are excluded from import. Hardware-bound compatibility is tested with a synthetic encrypted fixture, not a user's saved credentials. Damaged Workbench settings load defaults with a warning and preserve the damaged file in a recovery copy before saving.

Settings now offers Screen reader as playback output; when an active supported reader cannot be found, asynchronous Windows speech is used. Actual NVDA/JAWS acceptance needs an installed reader. Screen-reader speech duration is managed by that reader; Workbench cannot measure it for playback ducking. Windows speech ducking and all offline MP3 engines are verified locally. Diagnostic logs are kept beside settings, rotated at 1 MiB with one backup; configured API-key strings are redacted.

The revised library receipt pins source and all 52 media/subtitle input hashes and compares exact subtitle text and millisecond timing. Nine sampled video exports, 40 subtitle files and three audio layouts passed; all three native speech hosts passed synthesis and volume checks. A real yt-dlp download against a local HTTP fixture passed. Public YouTube extractor behavior remains unverified. The final portable build, source correspondence and disposable update/restart acceptance are recorded separately in evidence/acceptance-0.3 and evidence/build-receipt-0.3.json.

Gemma can also exhaust its response budget: packaged tests at Bunny 62-82 seconds failed at both 2048 and 8192 tokens while regenerating with an existing draft glossary. Truncated replies are rejected without replacing the existing descriptions. A larger budget does not guarantee completion. Correct the glossary, use concise guidance or shorter analysis chunks, and review all draft output. The final installed test receipt distinguishes successful clean-project testing from these retained failures. Cloud requests omit forced structured-output parameters, which Ollama's hosted service does not support; returned JSON is still parsed and validated. Cloud behavior has fixture coverage, not live acceptance.

Final installed 0.4 acceptance passed on a four-second derivative of desktop Bunny seconds 60-64: two real Gemma cues, exact project save, visible video playback, 26-model discovery, and Gemini retained. Longer 20-second installed tests exhausted the response budget, including with an empty glossary; clearing the glossary was not proven to fix the problem. See AUDIT.md and evidence/acceptance-0.4/installed-ui.json. The app is left on the short sample so you can try the completed path without launching a full-film analysis.
