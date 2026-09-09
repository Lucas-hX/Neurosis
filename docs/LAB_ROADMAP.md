# NEUROSIS Lab — Phase 0/1

The first evidence milestone is a visitor understanding the question, inspecting a real controlled experiment and causal trace/graph, and reproducing it from the repository. This pass establishes the foundation to start building that experiment. No pilot has run.

The exact issue titles, bodies, priorities, labels, dependencies and acceptance criteria live in [the importable backlog](../.github/NEUROSIS_LAB_BACKLOG.json). GitHub Projects access is unavailable with the current token; the file preserves the board columns and import data without requesting broader credentials.

## Implementation order

1. LAB-01/02: public direction, contracts, isolated recorder (integrated).
2. LAB-03: bounded provider-neutral harness and Groq adapters (implemented in this worktree; pending integration).
3. LAB-04/05: controlled board, graph and known-origin analysis.
4. LAB-06/07: finalize the reviewable protocol and implement EXP-001.
5. LAB-08/09: run a pilot, reproduce its artifacts, and publish real experiment/run pages.
6. LAB-10/11: external sensors/baselines and EXP-009 hidden shared resources.

[EXP-001 design](EXP_001_SPEC.md) is ready to guide implementation. Provider/account selection and an explicit cost ceiling are required before a paid pilot, not to build the deterministic environment. The original catalogue retains EXP-002 for Sybil consensus and EXP-009 for emergent shared substrate detection.

## Review and completion gates

Foundation: preserve public-memory behavior and isolation; establish honest documentation, license/citation, backend contracts, append-only storage, discoverable planning pages and a reproducible local test workflow.

Before pilot: bounded agent/provider loop, instrumented isolated board, deterministic graph/ancestry tests, pinned trial protocol, budget/stop rules, evaluator and replay.

Before evidence milestone: real reviewed artifacts, metrics traceable to raw events, honest limitations/negative results, safe run rendering/downloads and commands verified against the published source commit. Fixture tests are not scientific results.

## GitHub issues

- [LAB-01: Embed the two-track research direction and open-source foundation](https://github.com/Lucas-hX/Neurosis/issues/3)
- [LAB-02: Define canonical Lab artifacts and isolated append-only recording](https://github.com/Lucas-hX/Neurosis/issues/4)
- [LAB-03: Build the bounded provider-neutral population harness](https://github.com/Lucas-hX/Neurosis/issues/5)
- [LAB-04: Build the isolated instrumented shared board](https://github.com/Lucas-hX/Neurosis/issues/6)
- [LAB-05: Build interaction graph and known-origin analysis v0](https://github.com/Lucas-hX/Neurosis/issues/7)
- [LAB-06: Finalize the reviewable EXP-001 protocol](https://github.com/Lucas-hX/Neurosis/issues/8)
- [LAB-07: Implement the EXP-001 controlled environment and evaluator](https://github.com/Lucas-hX/Neurosis/issues/9)
- [LAB-08: Run and publish the EXP-001 pilot with reproducible artifacts](https://github.com/Lucas-hX/Neurosis/issues/10)
- [LAB-09: Publish real experiment and run inspection surfaces](https://github.com/Lucas-hX/Neurosis/issues/11)
- [LAB-10: Evaluate ADR ingestion and per-session detector baselines](https://github.com/Lucas-hX/Neurosis/issues/12)
- [LAB-11: Specify and pilot EXP-009 emergent shared substrate detection](https://github.com/Lucas-hX/Neurosis/issues/13)
