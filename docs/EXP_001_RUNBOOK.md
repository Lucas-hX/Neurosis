# EXP-001 pre-pilot runbook

The frozen protocol is [`experiments/exp-001/protocol-v1.json`](../experiments/exp-001/protocol-v1.json). It defines twenty seeds, eight cells per seed, four scripted reporters, one target, prompt templates, answer schemas, verification limits, evaluator v1, uncertainty, exclusions, budgets and stop rules. Any semantic change requires a new experiment version.

## Credential-free fixture gate

Run all sixteen preflight-shaped fixture trials from a clean commit:

```sh
.venv/bin/python -m neurosis.exp001 fixture .local/exp001-fixture-v1 --seeds 0 1
```

Fixture mode exercises the full ledger, board, provenance, graph, verification, evaluator, checksum and report path. Its scripted target is not a scientific result.

Regenerate graphs, metrics, CSVs and HTML without model calls:

```sh
.venv/bin/python scripts/analyze_exp001.py \
  .local/exp001-fixture-v1 .local/exp001-fixture-v1-replay
```

The command reports whether regenerated per-trial artifacts match byte-for-byte.

## Paid Groq preflight gate

Before execution, rotate any credential previously shared through chat, set a provider-side project spend limit, confirm the current Groq price, and verify `git status --short` is empty. The runner rejects provider execution from a dirty tree and requires explicit launch flags:

```sh
.venv/bin/python -m neurosis.exp001 groq .local/exp001-groq-preflight-v1 \
  --seeds 0 1 --pricing-reviewed --provider-spend-limit-confirmed
```

The frozen preflight ceiling is $0.25; each trial also has a $0.02 ceiling. Review every response, invalid/failure table, hidden-view prompt, model fingerprint, checksum and replay comparison before running seeds 0–19. The full pilot ceiling is $2.00 and the code never retries an answer because its content is unfavorable.

## Bundle semantics

Each trial is an independent five-agent run under `trials/<trial-id>/`. `manifest.json` is written last. `SHA256SUMS` includes the prospective manifest hash and every earlier file. A directory without a manifest is incomplete. The schedule bundle provides aggregate `summary.json`, `results.csv`, `report.html`, and checksums; it never overwrites an existing output path.

[Uber ADR](https://github.com/uber/ADR) is useful later for comparing external coding-agent session telemetry with NEUROSIS events. Its open-source sensor parses existing tool logs and its detection project targets enterprise agent security. It does not enforce our experimental hidden/explicit views or controlled source lineage, so it is not in the EXP-001 measurement path. Evaluate it as the planned LAB-10 adapter after the native experiment establishes a replayable baseline.
