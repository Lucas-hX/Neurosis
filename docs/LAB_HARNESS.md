# Bounded population harness v0

The LAB-03 harness is a separate operator process. It is not imported by the public FastAPI application and does not use the public memory API. It runs logical agents through a provider-neutral adapter protocol, stages raw evidence locally, and returns a concluded `RunManifest`. This is infrastructure, not a controlled experiment or result.

## Agent and adapter boundary

`LogicalAgent` records an agent ID, optional parent/principal IDs, sandbox ID, mutable synthetic state, conversation context, exact system and initial agent prompts, a model adapter, a maximum turn count, and an optional next-turn callback. A `ModelAdapter` declares its provider/model/settings, produces a conservative token and cost reservation before each call, and returns text, provider response ID, reported model/version information, finish reason, service tier, and usage.

`DeterministicAdapter` is the credential-free test implementation. `GroqAdapter` calls [Groq Chat Completions](https://console.groq.com/docs/api-reference) directly with no tools and supports only the explicitly priced `openai/gpt-oss-20b` and `openai/gpt-oss-120b` model IDs. LAB-03 uses 20B for concurrency/failure diagnostics and reserves 120B for the future EXP-001 target. The request seed and returned `system_fingerprint` are recorded; Groq documents seeded output as best-effort rather than guaranteed determinism.

The configured September 9, 2026 [Groq list prices](https://console.groq.com/docs/models) are $0.075/M input and $0.30/M output tokens for 20B, and $0.15/M input and $0.60/M output tokens for 120B. They are versioned in code and copied into each adapter configuration and reservation/cost record. Recheck pricing before a paid pilot. Calculated costs are labeled `configured_list_price`; Groq returns token usage but not a charged-dollar field.

## Bounds and stopping

`RunnerLimits` caps concurrent provider calls, request attempts, reserved tokens, calculated dollars, timeout, retries, and retry backoff. The default concurrency is four and the default retry count is two. Every request reserves a conservative maximum before it can enter the semaphore. Active and queued reservations count toward the ceiling, so concurrent scheduling cannot knowingly cross it.

Successful responses settle against reported usage. Any timeout, cancellation, network failure, HTTP error, malformed response, or unexpected adapter failure without trustworthy usage is charged its full reservation in the local budget. This deliberately overcounts uncertain spend. If reported usage exceeds the reservation, the run fails with an accounting error. A provider-side project spend limit remains necessary before a paid pilot because list prices can change and provider billing may be delayed.

Only transient failures are retried. Scientific answers are never retried merely because their content is unwanted. External cancellation and budget exhaustion stop new work and cancel active model calls. Ordinary adapter failures produce a failed run. Recorder or accounting failures stop the population because missing instrumentation invalidates the run.

## Event and artifact evidence

Each attempt emits an immutable `model_requested` event followed by `model_responded` or `model_failed`. Events include exact model input, settings, reservations, output text or sanitized error type, usage, calculated cost, provider response ID, and reported backend fingerprint. Credentials and provider error bodies are excluded.

`DirectoryRecorder` creates a new mode-0700 staging directory, saves exact prompt bytes under their SHA-256 names, writes `config.json` and `agents.json`, and fsyncs every JSONL event. It closes `events.jsonl`, then writes `results.json` and the immutable `manifest.json`. Existing output paths are rejected. A directory without `manifest.json` is an interrupted/incomplete staging record and must not be imported or presented as a run.

Run the deterministic 20-agent diagnostic without credentials:

```sh
.venv/bin/python -m neurosis.harness fixture .local/harness-fixture --agents 20 --concurrency 4
```

For a bounded Groq diagnostic, place `GROQ_API_KEY` in the ignored mode-0600 `.env` or export it only in the operator shell:

```sh
.venv/bin/python -m neurosis.harness groq .local/harness-groq-20b \
  --model openai/gpt-oss-20b --agents 20 --concurrency 4 \
  --max-output-tokens 64 --request-ceiling 25 \
  --token-ceiling 50000 --cost-ceiling 0.05
```

The CLI labels these as `EXP-000` harness diagnostics. They do not implement or produce evidence for EXP-001. Review local raw output before sharing it. The eventual controlled environment must supply its own prompts, state transitions, board instrumentation, evaluator, and run-bundle checksums.

Diagnostics may run from a dirty development tree. In that case `config.json` records `source_worktree_dirty=true` and a SHA-256 digest of the tracked diff plus untracked source bytes. This identifies the local state but cannot reproduce files that were never committed. A publishable pilot must run from a clean, exact commit; future EXP-001 orchestration must enforce that gate.
