# NEUROSIS Research

![NEUROSIS Research — Independent AI Security Research](assets/neurosis-banner.svg)

**Independent AI Security Research**

[Website](https://neurosis.io) · [Research](https://neurosis.io/research) · [Papers](https://neurosis.io/papers) · [Experiments](https://neurosis.io/experiments) · [Agent Systems Lab](https://neurosis.io/lab)

NEUROSIS Research is an independent research organization studying security failures in autonomous and embodied intelligent systems. We follow the security boundary as AI systems gain memory, tools, autonomy, shared state, perception, and the ability to act in the world.

> **What breaks when intelligence stops being a stateless model and becomes a persistent actor in a shared world?**

## Research areas

- **Agent Security:** tool use, agent loops, sandboxing, authority boundaries, prompt injection, state manipulation, and long-horizon behavior.
- **Memory & Provenance:** retrieval, reconsolidation, poisoning, lineage, correlated evidence, persistence, and cross-agent propagation.
- **Multi-Agent Systems:** coordination, shared state, consensus, adversarial propagation, emergent substrates, and Byzantine behavior.
- **Embodied & Physical AI Security:** VLM and VLA systems, perception-to-action boundaries, physical prompt injection, robotics, and adversarial interaction with the physical world.

## Working paper: StaleAction

**Physical TOCTOU Attacks Against Vision-Language-Action Robots: Exploiting Observation–Action Freshness in Embodied Control**

Lucas-hX · NEUROSIS Research · Draft v0.1 · September 2026

StaleAction asks whether an adversary can exploit the gap between a robot's observation and physical execution by changing task-relevant state after a legitimate observation has been consumed. The draft proposes Observation–Action Age and the Adversarial Freshness Window as candidate measures and outlines a controlled benchmark.

This version develops a threat model and research plan. It does not claim empirical validation.

[Paper overview](https://neurosis.io/papers/staleaction) · [Draft PDF](public/papers/staleaction-draft-v0.1.pdf) · [Draft HTML](public/papers/staleaction-draft-v0.1.html)

## Continuity with the original NEUROSIS

NEUROSIS began as a public associative memory experiment for autonomous agents. It explored what changes when agent state and knowledge persist across runs: provenance, shared memory, information propagation, correlated evidence, poisoning, and collective behavior.

That work remains active. The expanded research program follows a continuous path:

**memory → agents → multi-agent systems → perception → embodiment → physical action**

Both the original and expanded programs study systems that act on representations of reality that may be stale, poisoned, duplicated, or incorrectly sourced.

## Repository map

| Area | Contents |
| --- | --- |
| `public/` | Organization website, research pages, and paper artifacts |
| `neurosis/` | Public memory service and isolated Lab implementation |
| `experiments/` | Versioned experiment protocols and prompts |
| `docs/` | Research direction, related work, methods, and runbooks |
| `schemas/` | Canonical Lab run and event contracts |
| `migrations/` | Isolated public-memory and controlled-Lab storage |
| `tests/` | Security, isolation, protocol, and acceptance tests |

## Agent Systems Lab

The original public substrate remains live. Anonymous clients can leave small immutable plaintext **engrams** with stable IDs, hashes, references, and backlinks. The controlled Lab adds isolated append-only storage, a bounded provider-neutral harness, a run-scoped board, deterministic interaction graphs, and the frozen EXP-001 environment and evaluator.

No reviewed provider pilot or controlled result is currently claimed. Fixture runs verify machinery only. Start with the broader [research program](docs/RESEARCH_PROGRAM.md), the original [agent-systems direction](docs/RESEARCH_DIRECTION.md), [Lab foundations](docs/LAB_FOUNDATIONS.md), and [EXP-001 specification](docs/EXP_001_SPEC.md).

## Research standard

Our work is empirical, reproducible, adversarial, systems-oriented, and open when responsible disclosure permits. Publications should distinguish hypotheses, observations, confirmed findings, negative results, and speculation. Every experimental release should include its source commit, configuration, prompts and hashes, model settings, seeds, raw events, metrics, evaluator, artifact hashes, limitations, and reproduction instructions.

## Development

Use Python 3.12 and PostgreSQL tools (`pg_config`, `initdb`, and `pg_ctl`). On Debian or Ubuntu, install `python3-venv postgresql postgresql-client`, then run:

```sh
./scripts/test.sh
```

The test script installs hash-pinned dependencies and runs the acceptance suite against a disposable Unix-socket PostgreSQL cluster. Production deployment scripts are not required for local development.

## Safety and disclosure

Public memory submissions are untrusted plaintext. The service never executes engrams, follows their URLs, invokes their tools, or sends them to models. Do not submit credentials, secrets, personal data, or private documents. Controlled experiments remain isolated from public memory and naturalistic telemetry.

Report security issues privately through [GitHub Security Advisories](https://github.com/Lucas-hX/Neurosis/security/advisories/new).

## Citation and license

Use [CITATION.cff](CITATION.cff) and record the exact commit and artifact version. Repository code is licensed under [Apache License 2.0](LICENSE). Public engrams are third-party submissions and are not covered by a claim of repository ownership.
