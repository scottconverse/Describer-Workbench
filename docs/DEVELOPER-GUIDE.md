# Developer guide — local candidate 0.5.2

Public release remains v0.5.1; the candidate changes below are not a published upgrade.

Describer Workbench has one headless engine. The Qt desktop, Python API, CLI,
REST API and MCP tools call the same `DescriptionService`. No WSL, Docker,
desktop window or paid service is required for local processing.

## Install

Install the source checkout with the interfaces you need:

```powershell
python -m pip install ".[local,http,mcp]"
# Desktop additionally needs:
python -m pip install ".[desktop,http,mcp]"
```

Core installs do not depend on Qt. Local speech detection needs the `local`
extra, FFmpeg/FFprobe and a pinned YAMNet asset. Install an Ollama vision model
separately. Windows voices provide offline narration on Windows. Other platforms
can supply a speech adapter; native Windows voices do not become cross-platform
merely by installing the headless package. Optional OpenAI speech remains a
remote, explicitly authorized alternative.

Provision the classifier explicitly; opening a file never downloads models:

```powershell
describer assets provision
```

New code is Apache-2.0. See LICENSE, NOTICE and third-party notices. Attributed
original translations and dependencies retain their own licenses.

## Python API

```python
from describer.engine import DescriptionService

with_settings = {
    "analysis_provider": "Ollama",
    "ollama_model": "gemma4:12b",  # exact installed vision tag
    "voice_engine": "Windows",
}
service = DescriptionService(r"C:\work\describer-jobs", with_settings)
try:
    job = service.submit(source=r"C:\media\meeting.mp4")
    print(job["id"])
    project = service.wait(job["id"])
    print(service.read(job["id"], offset=0, limit=50))
    print(service.coverage(job["id"]))
    export = service.export_job(job["id"], export_format="mp4")
    service.wait(export["id"])
    print(service.get_job(export["id"])["artifact"])
finally:
    service.close()
```

`submit(project=...)` accepts an existing `Project`, an `.adproject` path or
project JSON. Original media is read-only. Result edits use `edit(job_id,
revision, cues=..., glossary=...)`; stale revisions are refused. Editing text or
timings invalidates its narration placement and requires export re-planning.

Jobs are durable JSON records with hashed stage checkpoints, a serial worker,
cooperative cancellation and explicit resume. After an owner exits, running or
queued jobs become `interrupted`, not successful. `resume(job_id, settings=...)`
retains completed stages only if source, local model digest, parameters and engine identity
match. Provider keys are never written to jobs/checkpoints; supply keys again
after restarting a cloud-backed engine. Cancellation cannot undo a sent cloud
request. A waiting read can take up to its configured timeout.

One process owns a workspace. Do not start multiple owners against the same
directory. Clients sharing desktop jobs attach to its HTTP service. Separate
workspaces are independent installations, not a cluster.

## CLI

The Python console entry point is `describer`; `describer-workbench` opens the desktop. The Windows portable folder also contains `DescriberCLI.exe` with the same arguments, including `mcp` and `serve`; no Python installation is needed for that build.
Use `describer --help` and subcommand help for actual argument names. Settings
files are ordinary request JSON, not the DPAPI-encrypted desktop settings file.

```powershell
describer --workspace C:\work\jobs --settings local.json describe C:\media\meeting.mp4
describer --workspace C:\work\jobs jobs
describer --workspace C:\work\jobs read JOB_ID --limit 50
describer --workspace C:\work\jobs coverage JOB_ID
describer --workspace C:\work\jobs export JOB_ID --format mp4
describer --workspace C:\work\jobs resume JOB_ID
```

Other commands: `capabilities`, `models`, `batch`, `status`, `cancel`, `edit`,
`ask`, `explore`, `scene`, `voice`, `serve` and `mcp`. Batch JSON is a list of
submission objects; up to20 items are admitted, with per-item results/errors.
Local describe/ask/explore/voice, batch, resume and export commands wait for their jobs before exiting. Remote describe/ask/explore/voice also wait by default; remote batch, resume and export return job handles, so poll status before reading results. `--no-wait` submission requires
`--server-url`, so exiting a short-lived CLI cannot abandon its owning worker.

## HTTP API

Set `DESCRIBER_API_TOKEN` to a private random secret of at least16 characters.
Then run `describer --workspace C:\work\jobs --settings local.json serve`.
The default bind is loopback port8796. Every HTTP request, including documentation
and MCP, requires `Authorization: Bearer TOKEN`. Do not put the token in a URL.
Use a TLS/auth gateway for a deployment outside the machine; that deployment is
separate from the local server. Cross-origin requests and non-loopback Host
headers are refused. The API can read files available to its Windows account;
granting its token grants that capability. Do not give it to untrusted websites.

OpenAPI schema: authenticated `GET /openapi.json`. The API defines:

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/capabilities` | Version, operations, resource limits |
| POST | `/models` | Ollama discovery; settings JSON body |
| POST | `/jobs` | Submit describe/export/ask/explore/voice-preview/prepare; returns202 |
| POST | `/jobs/batch` | Batch submission |
| GET | `/jobs` | List/filter jobs |
| GET | `/jobs/{id}` | Progress and terminal state |
| POST | `/jobs/{id}/cancel` | Request cancellation |
| POST | `/jobs/{id}/resume` | Resume with optional settings JSON |
| GET | `/jobs/{id}/descriptions` | Page/time-filtered cues |
| GET | `/jobs/{id}/coverage` | Event dispositions and unresolved information |
| PATCH | `/jobs/{id}/project` | Revision-checked cue/glossary edits |
| POST | `/jobs/{id}/export` | Start export; format/settings/mode JSON |
| GET | `/jobs/{id}/scene` | Completed question/spatial result |
| GET | `/jobs/{id}/artifact` | Download completed export/voice artifact |

Submission fields are `source` or `project`, `settings`, `prompt`, `start`,
`duration`, `operation`, `export_format`, `mode`. Read pagination filters by the original event interval, not a shifted narration slot. `total` is the filtered count. Pagination uses `offset`,
`limit` (1..500), optional `start`/`end`. Poll terminal states `done`, `error`,
`cancelled`, `interrupted`; do not keep polling an error. Media is not embedded
in job status or MCP tool responses.

Cloud inference/speech requires `settings.allow_cloud=true`. Keys can be supplied
in settings or service configuration. CLI can read `DESCRIBER_GEMINI_API_KEY`,
`DESCRIBER_OPENAI_API_KEY` and `DESCRIBER_OLLAMA_API_KEY`. These are explicit
processing requests, not telemetry. Telemetry/exporter auto-configuration is
disabled; ONNX Runtime telemetry is disabled before inference.

The desktop's **File → Start developer API / MCP** uses the same in-process
engine and writes its bearer token to the private workspace's `api-token.txt`.
Stop it using **File → Stop developer API / MCP**; the same controls are in Settings → Developer API. Closing the desktop stops that server.

## MCP

Standalone stdio configuration for a harness (replace absolute paths):

```json
{
  "mcpServers": {
    "describer": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["-m", "describer.adapters.mcp", "--workspace", "C:\\work\\jobs"]
    }
  }
}
```

To share an already running desktop/server engine, replace `--workspace ...`
with `--server-url http://127.0.0.1:8796` and provide `DESCRIBER_API_TOKEN` in
the subprocess environment. This is a stdio-to-service adapter, not another
inference owner. Developer Python/CLI clients can attach in the same way using
`RemoteService` or `--server-url`.

Streamable HTTP endpoint: `http://127.0.0.1:8796/mcp/`, using the same bearer
header. It is mounted in the HTTP server and shares job IDs and queue ownership.
No obsolete separate HTTP+SSE transport is implemented. MCP negotiation belongs
to the SDK; support in a particular harness must be verified rather than
inferred from the words "supports MCP".

Tools: `capabilities`, `list_models`, `submit_description`, `submit_batch`,
`get_job`, `list_jobs`, `cancel_job`, `resume_job`, `read_descriptions`,
`get_coverage`, `edit_descriptions`, `export_descriptions`, `ask_scene`,
`explore_scene`, `read_scene`, `preview_voice`, `get_artifact`.

## Results and complete exports

Each cue retains its observed `event_start`/`event_end`, event ID, kind, evidence,
uncertainty, narration duration and placement. A cue's output `start`/`end` may
differ after safe placement, but the engine does not move the source event.
Only exact duplicate observations of the same interval/event are removed;
identical words at different times survive.

Independent speech/vocal detection plus supplied captions protect the original
audio. Measured narration can accelerate at most1.15x. A cue that cannot fit
within a safe part of its event becomes `pause`; uncertain observations become
`unresolved`. The engine does not erase either category to obtain a green count.

Complete MP4/MP3/WAV exports insert pause narration into an extended timeline
(MP4 freezes the current image). Unresolved observations refuse a complete media
export. Explicit `mode=in-gap-only` produces an incomplete track and records that
fact. SRT/VTT/text/project exports are scripts, not proof of a complete narrated
track; their sidecar retains pause/coverage information and original event times.

Coverage accounts for observed events. It does not establish that the model
found every essential visual fact or that its statements are true. This version
does not certify legal accessibility compliance or claim99% visual accuracy.

## Shared architecture

![One engine and its desktop and developer consumers](diagrams/system.svg)

See the [architecture guide](ARCHITECTURE.md) for ownership, timing and data boundaries.

Remote hosted model aliases can change upstream without a locally verifiable weight digest. Local Ollama model identity uses the digest reported by `/api/tags`.


## Candidate recovery and export semantics

The common service now accepts `operation="prepare"` to repair narration/placement without vision, using the same durable queue and `core.plan_export` path. It requires speech consent for OpenAI. Both submit and resume check actual-operation cloud permissions; text-only export does not require unrelated speech consent. No GUI dialogs are introduced into developer operations.

`edit` retains existing observation metadata when identity is unambiguous. Preserve `event_id` when changing text and timing together; ambiguous edits involving unresolved observations are rejected instead of silently dropping review safeguards. Stale narration is invalidated.

`damaged_jobs` exposes paths of unreadable/invalid records; these records are excluded from usable job lists and retained unchanged. Valid jobs and owner locking remain available. Desktop recovery uses original job settings, current credentials, and normal checkpoint identity checks.

Developer exports intentionally replace an existing final target and coverage sidecar without interactive confirmation. Callers must choose/approve those destinations. Temporary staging files are uniquely created and owned, so an existing predictable `.partial` file is not used as scratch. Desktop exports add interactive overwrite confirmation and early destination checks.
