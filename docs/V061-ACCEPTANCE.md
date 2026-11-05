# 0.6.1 acceptance

November 4, 2026. This patch addresses the eight findings from the whole-repository audit-lite review of 0.6.0. The [0.6.0 acceptance record](V060-ACCEPTANCE.md) preserves earlier native provider, media, speech and quality evidence; those unchanged behaviors were not all rerun for this patch.

## Fixes and executed source verification

| Finding | Corrected behavior and evidence |
|---|---|
| F001 | A malformed observation's metadata rejects the whole chunk. Mixed valid/invalid metadata cannot yield a successful partial result. Regression cases cover null/non-string metadata, invalid disposition, exact duplicates and genuine recurrence. |
| F002 | Only validated responses are reusable checkpoints. A rejected response is retained separately; after service reopen, resume reuses a good prior chunk, requests the failed chunk again and completes with every expected event in coverage. Legacy invalid cache entries are retained without reuse. |
| F003 | The visible Draft dialog enables each supported connection test, uses the exact typed model, requires applicable consent and dispatches to the selected adapter. Cancel preserves settings. Disclosure distinguishes sampled images without audio from Gemini video; direct compatible servers are not described as subscription gateways. |
| F004 | Nested connection/model/CLI choices and enums are validated before UI startup. Recovery warns, preserves original bytes, uses the existing defaults policy and backs up the damaged file before saving. Existing valid profiles without a display name remain compatible. |
| F005 | Available Ollama family, parameter size, quantization, byte size and context reach the visible model list through actual discovery. Missing fields remain unknown; failed per-model detail requests preserve healthy entries. |
| F006 | README, Help, manual and connection guidance agree with the separate exact-ID field, duration-preserving Start edits, independent End edits and measured-audio gain. The focused Qt regression observes timing and gain; HTML/downloadable guides are regenerated from the same source. |
| F007 | VTT imports accept optional hours, mixed valid forms and UTF-8/UTF-16/Windows-1252 while retaining legacy SRT and bounds checks. |
| F008 | Explicit per-language preset rename preserves text and selection, replaces one key and survives settings reopen. Cancel and rejected collisions preserve saved bytes. |

The source suite passed **182 tests and 3 subtests**. Required Ruff F checks and whitespace checks passed. One upstream Starlette/httpx deprecation warning remains. Provider, media and synthesis boundaries are mocked in the new deterministic shared-service regressions; these checks do not establish fresh live-provider entitlement or factual accuracy. Actual normalization, checkpoint reuse, durable service completion, Qt dialogs and settings persistence run in those tests.

## Release verification

The release's `release-verification.json` records the exact build source, required CI, Azure Trusted Signing run, independent Scott Converse signature/timestamp verification, packaged acceptance, public downloads, installed update/rollback, launcher and documentation delivery. Prepared source or a successful build alone does not establish delivered acceptance. Signing follows [the established procedure](CODE-SIGNING.md).

The reviewed-draft quality policy and measured Windows narration policy remain unchanged. Correct visual facts, missing events, readable text and timing before final export. Placement coverage is not factual recall. Existing limits for keyed services, separate local compatible servers, active screen readers, native-speaker review, public YouTube extraction and full-film quality remain explicit in the [connection guide](AI-CONNECTIONS.md) and [prior acceptance](V060-ACCEPTANCE.md). No macOS release is established by this patch.
