# AI connections — 0.6.1

Version 0.6.1 implements these finite routes. The Windows executables are signed as Scott Converse. See [release acceptance](V061-ACCEPTANCE.md) for executed checks and delivery boundaries.

The [macOS/Linux add-ons](UNIX-INSTALL.md) expose these same routes where the external CLI/server is installed. Re-select executable paths on the new machine. Native sign-in opens Terminal or a Linux desktop terminal; each CLI retains its credentials. Gateway authentication remains external and is not migrated. Saved API keys use macOS Keychain or Linux Secret Service instead of Windows DPAPI. Mac/Linux packages do not inherit the Windows certificate or the historical live-provider acceptance performed on Windows; run Test connection for the selected model/account on the destination computer.

| Route | Authentication and model selection | Verification so far |
|---|---|---|
| Gemini | Existing Google API key and exact Gemini model ID | Existing route; new completion-status classification has regression checks |
| Ollama | Existing server URL, optional key and exact model ID | Existing route; discovery now preserves healthy entries when another entry fails |
| Subscription gateway | Existing local CLIProxyAPI endpoint and client-key **file path** | Synthetic image and bounded16s description/Scene workflows passed through Codex, Claude and Gemini aliases; canonical reported model limits below |
| Codex CLI | Existing native CLI subscription login; exact CLI model ID | Synthetic image and three bounded16s description/Scene workflows completed with requested `gpt-6.1-sol`; actual model identity was not reported |
| Claude CLI | Existing native Claude subscription login; exact CLI model ID | Synthetic image and bounded16s description/Scene workflow completed with reported `claude-sonnet-5-5` |
| Gemini CLI / Antigravity | Existing `agy` subscription login; exact ID from `agy models` | Synthetic image and bounded16s description/Scene workflow completed with requested `gemini-3.8-flash-medium`; response did not report actual model identity |
| OpenAI-compatible | A named profile for LM Studio, llama.cpp or compatible remote server; optional API key and per-profile model ID | Credential isolation plus actual image/description/Scene checks passed against the existing gateway endpoint; separate LM Studio/llama.cpp/OpenAI services remain unverified |
| Anthropic API | Separate Anthropic API key and exact model ID | Explicit API transport implemented; live API acceptance not performed |

Subscriptions, native CLIs and API credits are separate routes. An installed CLI or a listed model does not establish login, entitlement or image support. There is no automatic provider fallback. DeepSeek 1017 remains an existing Ollama route at LOW effort; a duplicate CLI relay and retired Grok integrations are excluded from this bounded connection work.

## Setup

Choose the route in **Draft with AI**, enter an exact model ID, and save. Each route retains its own model ID. For compatible servers, use **File > Manage AI connections** to add, select, disable or delete a profile. Saving a profile selects the connection while preserving the selected provider. Select **OpenAI-compatible** to use it. Cancel discards the edits. API credentials are stored under Windows DPAPI; removing a saved credential is explicit.

Select a discovered row or type in the separate **Exact analysis model ID** field. The visible **Test connection** button uses that ID and the selected route. Subscription/native/compatible/Anthropic routes use the synthetic-image test; Ollama uses its labeled text test. Gemini is checked when a confirmed operation starts. Gemini and Anthropic API have no catalog refresh in this interface. Draft displays the selected destination and whether it receives sampled images without audio or Gemini video; normal external-processing confirmation remains required.

For the shared subscription gateway, enter its URL and the path to its existing client-key file in Settings. Describer reads that key by reference. It does not copy the gateway authentication store, perform a second OAuth login or restart the shared gateway. Gateway aliases can differ from native CLI IDs.

For native routes, select the installed executable or supported PowerShell shim in Settings if discovery cannot find it. Sign in using that CLI's normal login process outside Describer. Native invocations receive an explicit environment allowlist for process startup, native sign-in homes, locale, proxies and TLS trust. They exclude unrelated secrets, API-credit overrides, Google ADC authentication overrides and Node preloads. They run against temporary sampled frames with bounded timeouts; cancellation terminates only the invocation owned by Describer.

**File > Subscription sign-in** opens the selected native tool in a visible window: Codex's device sign-in, Claude's subscription sign-in, or Antigravity's normal startup authentication. You complete the provider's sign-in there; Describer reads no credentials or login output. This window remains under your control after Describer closes. Close it when finished and use **Test connection** to verify image inference; opening the tool or a zero exit status does not establish account/model entitlement. Antigravity uses its [documented native-keyring/browser sign-in](https://antigravity.google/docs/install?tab=cli). The gateway retains its separate existing account-management tools and shared authentication state.

Native Codex disables shell, hooks and agent delegation. Native Claude disables tools, hooks and external MCP configuration. Antigravity permits reading its temporary image workspace and denies commands, file writes, web access and MCP tools using its [documented CLI permission rules](https://antigravity.google/docs/permissions?tab=cli). It disables additional-credit fallback for this invocation. Existing global provider settings and default models are preserved.

## Discovery, testing and data

**Refresh models** uses the selected route's catalog where available. Codex can use its local catalog cache; Claude requires an exact manually entered ID. A cached ID is not proof of current availability. Unknown vision capability is displayed as unknown. Native Anthropic has no catalog refresh in this interface.

**Test connection** on the new routes sends a synthetic blue image after external-processing confirmation. It reports success only if the response identifies blue. This establishes a small image-backed smoke test, not narration quality, all model entitlements or the actual model identity when the provider does not report it. Ollama's existing test is a text test and says so.

These routes send up to eight sampled video frames with timestamps and prompts, without audio. They cannot hear dialogue or establish unseen motion. External processing requires confirmation; local compatible profiles retain their local destination. Available usage records distinguish requested and reported model identity; unavailable counts or identity remain unknown. Gateway Gemini's tested requested alias and reported model differed, so the requested effort variant is not independently established.

Review all descriptions. The retained three120-second samples were compared against source frames. Current Codex output corrected earlier airborne-craft and living-creature errors but still misidentified a person in a dark bedroom, omitted a short fruit-inspection sequence and left some printed text uncertain. Scott accepted a reviewed-draft workflow with these limits on November4: correct facts, missing events, readable text and timing before final export. Successful inference, cue counts and coverage receipts do not establish factual truth or complete event recall.

The working Codex and Gemini gateway aliases also completed one16s description plus Scene workflow each. Gateway Codex reported `gpt-6.1-sol`; gateway Gemini again reported `gemini-3.8-flash-n` for the requested high alias. Gateway Claude initially failed with unavailable authentication after a refresh-token failure. After the existing gateway's normal account recovery, its selected `claude-oauth-sonnet-5-5` alias passed a fresh synthetic-image test and both16s common-engine workflows, reporting `claude-sonnet-5-5` for description and Scene. Completed jobs establish this bounded workflow, not complete-film factual accuracy or every catalog model's entitlement. Scene answers and uncertain descriptions still require review.

After the source-time sampler and child-environment corrections, native Claude, native Antigravity, gateway Codex and gateway Gemini each completed a fresh16-second description plus Scene workflow. Native Codex also passed its synthetic image test with the restricted environment; its full three120-second description comparison used the corrected sampler. No newly tested request changes the selected global provider or downloads/loads a local model. Gateway Claude also completed the corrected-sampler workflows after account recovery. These are actual successful requests, independently of the native Claude route.
