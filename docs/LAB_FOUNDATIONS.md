# Lab foundations v0

This foundation now supports the bounded harness, isolated board, interaction graph, and frozen EXP-001 fixture environment. No provider pilot or controlled result exists yet. The public FastAPI app serves trusted planning pages at `/lab`, `/experiments`, and `/experiments/exp-001`, including Markdown mirrors. Unknown experiment and run URLs return 404; no placeholder run is presented as evidence.

## Architecture and isolation

Track A retains `memory.*` and private naturalistic `research.requests` telemetry. Migration `002_lab.sql` adds only `lab.runs` and `lab.events`; it changes no existing table or grant. The public API role receives no Lab privileges. No Lab ingestion endpoint or provider client is imported by the HTTP application. Its Unix-socket-only network isolation remains intact.

The initial recorder imports concluded runs from the separately operated harness, using `LAB_DATABASE_URL` explicitly. It never falls back to the public application's `DATABASE_URL`. The harness stages prompt/configuration bytes before execution, fsyncs raw events while it runs, and writes the concluded manifest last, including ordinary failures and cancellations. An interrupted process can leave a staging directory without a manifest; retain it as evidence of an incomplete run. Live database ingestion/finalization is future work; do not claim the offline database recorder captures a running provider session.

Lab experiments use a controlled board, not `/v1/engrams`. Separate database grants and operator processes enforce the normal path; an operator with superuser access can bypass database protections and remains a trust boundary. Do not give a future Lab role access to `memory` or `research`. Browser requests to Lab documentation are ordinary site visits, never experimental evidence. Public service counters measure requests, not organic adoption.

## Canonical manifest

[`RunManifest`](../neurosis/lab.py) and [JSON Schema](../schemas/run-manifest-v0.schema.json) define v0. Required fields:

- `schema_version=0`, `track=lab`, `synthetic=true`.
- Experiment ID/version, UUID run and population IDs, full source commit, seed.
- Model configurations: provider, model, model version, temperature, token budget, system/agent prompt SHA-256 hashes. Multiple configurations permit heterogeneous populations.
- Population size, topology, adversarial fraction, declared channels and shared resources.
- Environment version, exact configuration SHA-256, timezone-aware start/end times, and completed/failed/cancelled outcome.

Pin dependency locks, task/environment versions, and the exact prompts alongside the manifest. Provider model aliases may drift: record the response model/version when exposed and explicitly document unavailable version information. Never invent a provider snapshot. Hashes identify exact UTF-8 prompt/config bytes; they do not replace storing those bytes. Per-agent configuration assignments belong in `agents.json` in the eventual bundle.

The immutable manifest describes a concluded run. Failed/cancelled runs remain records; never silently replace them with successful retries. New trials get new run IDs.

## NeurosisEvent v0

[Event schema](../schemas/event-v0.schema.json) is generated from the same Pydantic model used for ingestion. It rejects unknown top-level fields, non-finite numeric values, naive timestamps, malformed identifiers, self-parenting and duplicate parents. `metadata` is the JSON extension point, not a place to override canonical fields.

Each event has event/run/population/experiment identity, timestamp, agent/model/provider/sandbox, typed source and target entities, an event type, and provenance. The harness adds explicit `model_requested`, `model_responded`, and `model_failed` attempt events. Optional principal, parent agent, resource, artifact, memory, claim, content hash and declared-channel fields support future adapters without depending on one provider.

Use actor → object for writes, object → actor for reads, and agent → claim for claim decisions. Read events mean observed access; `claim_adopted` means an explicit recorded answer/state transition, never an inference from a read. Tool calls record requested invocation, not presumed success. Put returned status/outcome in metadata. Entity IDs are scoped to a run unless a future adapter explicitly defines a cross-run identity mapping.

Provenance kinds are `observed`, `agent_reported`, `inferred`, or `unknown`. `recorder_id` identifies the instrument, not authenticated truth. Parent event IDs record supporting dependency evidence; they must already exist in this run and not have later timestamps. They are not proof of a causal effect. `origin_ids=null` means unknown; even an empty list does not certify independence. Origin assertions require controlled ground truth or independently supported provenance. No IEC calculation is implemented yet.

`append_event` serializes writers per run, validates associations, event time, declared model/channel and ancestry, and rejects conflicting reuse of an immutable event ID. Exact retries are idempotent. Database foreign keys enforce run associations; triggers reject update, delete and truncate. The Python recorder is the canonical semantic validator; direct owner SQL is trusted administration, not a public ingestion contract.

`export_events` returns deterministic canonical JSONL in recorder order. Timestamps capture event time; the sequence captures ingestion order. Neither means unrelated simultaneous events are causally ordered. Cross-run ancestry, semantic fingerprints and causal inference remain future work.

## Local workflow

Run `./scripts/test.sh` as a regular user. Tests initialize a disposable PostgreSQL instance and apply all migrations; no production configuration or credentials are needed. Existing `python -m neurosis.admin migrate` applies checksum-tracked migrations using an operator's `DATABASE_URL`; never use the public app role for migrations.

After a future harness stages a concluded manifest and parent-before-child JSONL:

```sh
# LAB_DATABASE_URL must point to an operator-controlled development Lab database.
.venv/bin/python -m neurosis.lab ingest /path/to/manifest.json /path/to/events.jsonl
.venv/bin/python -m neurosis.lab export RUN_UUID > /path/to/exported-events.jsonl
```

These commands record/export artifacts; they do not run EXP-001. Ingestion is transactional: a malformed event rolls back the whole new run. Reimporting a registered manifest fails rather than overwriting it. Event-level exact retries are available through `append_event`. The export does not authorize publication: review raw provider output, personal data and secrets before any future public artifact release.

## Future self-contained run bundle

```text
runs/exp-001/<run_id>/
  manifest.json
  config.json
  prompts/
  agents.json
  events.jsonl
  graph.json
  metrics.json
  results.csv
  report.html
  SHA256SUMS
  README.md
```

The future README must include the exact commit checkout, install, recorded replay/analysis command, fresh provider rerun command and its cost prerequisites, expected outputs, evaluator version, seed/trial schedule, limitations and exclusions. Metrics must trace back to raw event IDs; the graph must expose supporting evidence. Publish no real secrets. Private material requires explicit omission/redaction records; do not silently pretend a redacted artifact hash is the original.

Run pages and downloads must be backed by reviewed, real artifacts. Do not link a run URL, populate counters or claim a result until those artifacts exist. A graph alone is not a causal experiment, and model seeds alone do not ensure deterministic fresh responses.
