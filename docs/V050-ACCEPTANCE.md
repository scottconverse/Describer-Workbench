# v0.5.0 local candidate acceptance

Status: **implemented and locally verified; not pushed or published**. Branch `feat/shared-engine-v050`, based on `92afa7c24c6a0840b05a2d02d41c83a5f4bd988b`. November1,2026. Apache-2.0 applies to new Workbench code; original translations and dependency terms are retained separately.

## Agreed outcomes

| Outcome | Implementation and observed evidence |
| --- | --- |
| One engine | Desktop, Python, CLI, HTTP and MCP use `DescriptionService`, one workspace owner and a serial durable queue. Headless wheel imports work without Qt. |
| Independent dialogue protection | Verified local YAMNet measures speech/vocals; optional captions add protection. Missing/corrupt assets stop processing; vision does not supply safe-gap guesses. Three native clips used the existing pinned model. |
| Event times retained | Visual event intervals survive normalization. Placement intersects those intervals with protected gaps and other narration. Tests preserve overlapping original events. |
| Intelligibility and no-fit coverage | Speech is measured and acceleration is capped at1.15x. No-fit observations become actual pause narration. Complete MP4 freezes picture and source audio for the inserted voice; complete audio inserts matching pauses. Unresolved events block complete narrated media. |
| Real recurrence retained | Only identical same-event/time/text observations are deduplicated. Same text at another event time remains. Regression tests passed. |
| Developer access | Python/CLI, authenticated REST/OpenAPI,17 MCP tools over stdio/Streamable HTTP: jobs, batch, status, cancel/resume, paged/time-filtered reads, coverage, revision edits, scenes, voice preview and exports. Real protocol checks passed. |
| Existing projects preserved | Version-1 roundtrip/read-only original tests passed. Real GUI acceptance loaded the native project, paused/resumed correctly and stopped old narration on source change; project hash was unchanged. All three source-video hashes were unchanged. |
| Packaging | Headless wheel and sdist build. Fresh core install has resources and no Qt dependency. Portable `DescriberWorkbench.exe` and `DescriberCLI.exe` build. Actual packaged GUI main-window startup, packaged CLI, HTTP/OpenAPI and MCP stdio checks passed. All25 frozen application modules match source. |
| Privacy | No application analytics. ONNX telemetry disabled; process telemetry-off defaults set; FastAPI tracing/metrics/log exporters/automatic setup explicitly disabled. Provider/cloud use remains explicit and separately authorized. |
| Documentation | README, user manual, developer guide, architecture/drawings, landing source and rendered local site updated. Previous stable0.4.2 downloads remain explicitly historical. |

## Automated checks

`python -m pytest -q`: **43 passed,3 subtests passed**, one non-failing Starlette/httpx deprecation warning. No skipped tests in that run. `ruff check` with `--select F` passed for the new engine/adapters/CLI/tests/verification tools. `git diff --check` passed. Documentation tests render guides and check local links/fragments/download navigation.

The batch media-failure regression first failed on a real corrupt MP4, then passed after preserving per-item errors. Resume with an explicit settings override likewise failed before its merge fix. Native media tests use actual FFmpeg encoding/decoding; they do not substitute an existing file for a successful export.

## Three native Blender samples

Each source is a120-second excerpt, not an entire film. Local `gemma4:12b`, its existing off/32K-output/64K-context profile, the existing verified YAMNet asset and native Windows speech were used. No model/provider default was changed.

| Clip | Observations retained | In-gap | Pause | Unresolved | Actual complete MP4 length |
| --- | ---: | ---: | ---: | ---: | ---: |
| Big Buck Bunny |60|24|36|0|206.284s|
| Tears of Steel |59|13|46|0|238.600s|
| Sintel |60|17|43|0|213.550s|

All outputs decoded. No in-gap narration crossed a classifier-protected interval or its visual event interval; speed stayed within the ceiling. One intentional cancel/resume reused the first observation checkpoint with the same hash and modification time. Native observation/placement runs preceded later submission-error, fingerprint, packaging and GUI callback fixes; those changes were checked with affected tests and the final source suite, without repeating unaffected inference.

These counts account for returned observations. They are **not accuracy scores** or proof that every essential visual event was detected. In particular, the model still produces drafts that can contain subjective descriptions or factual mistakes. No99% accuracy or WCAG compliance claim is established by this build. A complete export means every accepted observation is voiced, not that model perception is complete.

## Artifacts, evidence and limits

The local verification directory contains `native/run.json`, three exported videos, original/result projects, checkpoints, `gui/receipt.json`, `portable/receipt.json`, `frozen-gui.json`, `frozen-source.json`, test/build logs and package checksums. Raw machine-specific evidence is deliberately kept out of the source repository. The private state record supplies its absolute path.

The GUI executable SHA256 is `db057f4aaf688e640bd196e301a68eec61a90fa81ac0458cedbefad3f23c77df`. Portable executables are unsigned. No existing installation was replaced; no GitHub release, package upload, hosted-site deployment or CivicCast RC/live-data edit was performed. GitHub CI was not configured or run for this unpublished branch, so local green checks are not represented as hosted CI.

Live keyed Gemini/OpenAI/cloud acceptance, Linux/macOS native speech, NVDA/JAWS user acceptance and full-film semantic accuracy remain unverified. The server is a trusted loopback developer service, not a public multi-tenant deployment. Hosted model aliases may change without locally verifiable weight identity. Source, projects and the durable workspace should be backed up together because planned cues refer to narration files there.

Earlier GUI checks stalled inside Qt event processing. Final acceptance uses the real Qt event loop, bounded failure timeout and deferred resume after the status callback. Earlier test windows were stopped by verified owned PID. Capture failures and earlier failed checks remain recorded; they are not counted as passes.
