# 0.6.0 candidate acceptance

November4,2026. **Signed development candidate; not published or installed yet.** The public signed0.5.2 release and its acceptance records remain unchanged. Candidate source is `ba04cc390eb264093fcbdf185bf03e993d3e2499`. Required [Windows CI41872789830](https://github.com/scottconverse/Describer-Workbench/actions/runs/41872789830) succeeded. The Windows build, both frozen-source comparisons, packaged CLI/HTTP/OpenAPI/MCP checks and native GUI startup/normal close passed. Public downloads and installed acceptance remain pending.

## Bounded scope

The candidate addresses the22-item original-specification/REA remediation list. Source behavior, executed checks and delivery are distinct. The source has152 passing tests plus3 subtests; required local lint and remote CI pass. One upstream Starlette deprecation warning remains. Later version/documentation bookkeeping does not change the tested inference, speech or media behavior.

| Item | Implemented behavior and acceptance |
|---|---|
| D01 | Strict provider allowlist shared by consent and dispatch; unknown providers produce no transport calls. Regression checks pass. |
| D02 | Authored timing separated from observed event provenance; Start edits preserve duration, undo/replan/export retain intent. Regression checks pass. |
| D03 | Gemini finish/block/no-candidate classification; cut-off text retained separately as incomplete review material, not a result. Service/reopen/redaction regressions pass. Blocked text is not recovered. |
| D04 | Explicit Explore operation retains focus and project glossary through desktop/shared service. Persistence/usage regression passes. |
| D05 | Native Codex/Claude/Antigravity and existing gateway transports implemented. Native routes and gateway Codex/Gemini have actual image-backed requests and common-engine description/Scene evidence. **Gateway Claude remains open pending account reauthentication and successful inference.** See [connections](AI-CONNECTIONS.md). |
| D06 | Three120-second materials compared against source-time images; sampling defect corrected. Scott explicitly accepted reviewed drafts with documented factual/recall limits. Wrong bedroom identity, short object omission and uncertain text remain failed inference examples, not hidden passes. |
| D07 | Recognized redundant lead-ins shortened only when measured original speech cannot fit; shortened WAV remeasured. Actual Windows speech fit and original text/evidence/reopen checks pass; otherwise pause fallback remains. |
| D08 | Prompt manager reachable in File; existing per-language CRUD retained. UI regression passes. |
| D09 | Scott chose measured Windows narration for timed cues. Live text/Scene retain reader preference with Windows fallback; timed scheduling uses measured export-voice WAVs. Native Windows playback exercised; active NVDA/JAWS acceptance not claimed. |
| D10 | Recorded synthesis level, live/export gain and duck state corrected. Legacy unknown levels require repair. Actual Windows/FFmpeg40%-to100% RMS ratios approximately0.400 in both in-gap/pause outputs; mute silent and source unchanged. No human-listening claim. |
| D11 | Preview/discovery use unsaved draft voice choices; stale/cancel safeguards retained. Regression checks pass. |
| D12 | Explicit clip/source timestamp reconciliation; malformed/mixed/ambiguous chunks fail instead of silently losing rows. Regression checks pass. |
| D13 | Original voice engine/shared32-bit keys,100%-normal rate, fractional volume and language mapped with preview/voice check. Static REA algorithm plus encrypted synthetic fixture using actual Windows hardware identity pass; accepted native import refreshes controls. Original user secrets were not imported or read for testing. |
| D14 | Durable structured stage checklist/percentage reaches desktop; completed stages do not regress during cached protection checks. Completed native jobs and regression checks provide evidence; percentage is not accuracy. |
| D15 | Rich available metadata, exact manual IDs and per-entry catalog failure isolation. Regression checks pass; missing metadata stays unknown. |
| D16 | Available usage persists by operation/requested/reported identity. Description/glossary combined counts explicitly attributed; Scene separate; unavailable counts/cost unknown. Persistence/display checks and actual provider job records pass. |
| D17 | Final startup language application restored.204 literal strings inventoried,171 English fallbacks per non-English language except Turkish170. Dynamic/model/user strings excluded. Native-speaker/full translation acceptance not claimed. |
| D18 | Blank feed uses official stable GitHub release; digest, timestamped Scott Converse signatures on both executables and staged-file hashes required. Actual existing signed-package stage/disposable swap/backup/settings/tamper rejection pass. New production installed update/relaunch remains pending delivery. |
| D19 | Explore2/5/10/20 seconds and optional focus restored; end-to-end shared-service check passes. |
| D20 | Native Windows screenshots/control checks cover Scene actions/focus, actual model/counts, four-bar mark, dialogue hatch, diamond playhead, visible range, toast and runtime developer paths. Settings Cancel preserves bytes. No active-reader usability certification. |
| D21 | Native Qt event loop decoded/sought/played measured in-gap and pause narration for bounded MP4/MKV/MOV/AVI/WebM fixtures. No arbitrary-codec or every-file guarantee. |
| D22 | Finite [connection inventory](AI-CONNECTIONS.md): native/gateway subscriptions, compatible profiles and explicit Anthropic API implemented; duplicate DeepSeek CLI relay and retired Grok excluded. Live compatible-profile requests pass against existing gateway; separate LM Studio/llama.cpp and keyed Anthropic/OpenAI services remain unverified. No automatic fallback, default-provider change or new token store. |

## Quality and verification limits

Descriptions are reviewed drafts. Human correction of visual facts, omitted events, readable text and timing is required before final export. Uncertainty blocks complete narrated exports; a confident false fact or omitted event may have no marker. Placement coverage and cue counts do not measure factual truth or recall. The retained comparison covers360 seconds at one-second visual samples plus selected full-resolution frames; it is not complete-film or continuous-motion acceptance.

Gateway Gemini reported a different canonical model ID from the requested high alias. Native Codex/Antigravity did not report actual model identity. These limits are exposed rather than substituting another route or claiming every model entitlement. Existing Gemini/OpenAI keyed speech/analysis, third-party legacy voices, public YouTube extraction, full native-speaker translation and active-reader sessions retain their previous live-testing limits.

## Delivery still pending

The exact prebuilt GUI and CLI were signed through the established Azure workflow41873830687. Independent local `signtool verify /pa /v` and Authenticode checks passed for both: Valid, Scott Converse, Microsoft timestamps. Intake/returned hash mappings matched and both post-sign embedded-source comparisons passed. Unsigned backups remain retained.

| Signed candidate file | SHA256 |
|---|---|
| `DescriberWorkbench.exe` | `18ff122c0b88d0c55d150bfa5996bd89c8fbf5e5a692cf6a3820ff62db67a011` |
| `DescriberCLI.exe` | `f882bc67d95a71dba67fb4081415dfbc0ab93682083c0803bf9b1790c121ca19` |

Before this becomes a delivered release: resolve or explicitly disposition the gateway Claude account, finalize release documentation/package contents, publish verified assets after the normal protected merge, update installed app/launcher, and verify downloaded/installed files and all documentation surfaces. A signed candidate or launched process is not delivery evidence. Documentation-only follow-up commits do not change the signed-build identity above.
