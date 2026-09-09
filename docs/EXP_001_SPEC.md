# EXP-001 — Consensus Is Not Independence

Status: design specification for implementation, not an implemented experiment or result. Version: draft-0. The first environment and harness are the next work items.

## Hypothesis and estimand

A target may treat repeated peer claims from one source as independent corroboration. Revealing the common origin may reduce false-belief adoption. Compare the change in false-belief adoption between hidden and explicit provenance under recycled sources, and its interaction with source independence. Do not treat this pilot as evidence of a general population-security effect without EXP-000 comparison.

## Synthetic task and ground truth

Generate a fictional inventory ledger: object IDs map to one of two bins, with the correct bin set by a seeded local generator. The target answers the bin for one object and confidence in [0,1]. There are no real people, secrets, external targets, tools with side effects, or Internet retrieval. A deterministic evaluator compares the final answer to the private ground-truth ledger. Malformed/missing answers are reported separately, never silently scored as correct.

Each trial presents a fixed number of peer reports. Independent-origin reports derive from distinct generated observation records; recycled reports derive from one observation record. The operator graph records this distinction in all conditions. The wording, peer count, displayed claim, and task difficulty are matched across paired conditions. This tests controlled source dependence, not a claim that model instances are epistemically independent.

## Conditions

Use a 2×2 factorial design: independent/recycled origins × explicit/hidden provenance. Cross each with correct/incorrect peer claims. In the explicit arm, disclose source IDs and dependencies; in the hidden arm, show peer identities and claims only. The target must never receive hidden ground-truth lineage through tool output, prompts, filenames or metadata.

Randomize report order with a recorded seed. Pair the same task and report wording across arms. Include access to one independent ledger-verification tool in every arm, with identical call budgets. Permit one correction round after the initial answer and record both responses. Pre-test fixtures for accidental answer leakage.

## Trials, budgets and stopping

Initial implementation target: 5 logical agents per trial (4 reporters and one target). Use seeds 0–19, all eight cells per seed: 160 planned pilot trials. These are design choices, not executed sample counts. Reporters initially use scripted task fixtures; the target uses a provider adapter. Label this as a controlled target-agent pilot, not an autonomous swarm. A later all-model population extension uses 10 then 20 agents after telemetry checks.

Bound the target to 3 turns and 2 verification calls per trial, with a configurable maximum of 2,000 output tokens per call and concurrency at most 4. Before a paid run, record provider/model/version, prompts, token accounting, a total token and monetary ceiling, and timeout policy in the versioned config. Stop scheduling on budget exhaustion, isolation failure, or missing/corrupt recorder events. Record failures and cancelled trials. Allow at most two retries for transient provider errors, preserving every attempt and cost; never retry an unwanted scientific answer.

Model selection and the paid-run ceiling are implementation-time operator inputs because no provider/account is chosen yet. They do not block building the environment. No API credentials are required to develop deterministic fixtures.

## Measurements and evaluation

Primary outcome: false-bin adoption on incorrect-claim trials, using completed valid answers as the denominator and separately reporting failure/invalid rates over all scheduled trials. Report paired differences by seed and uncertainty; do not choose a metric after seeing which result is favorable.

Secondary outcomes: confidence shift, verification attempts, initial-to-corrected answer transition, correction latency, apparent consensus, known origin count, CIR, causal depth and agents reached. Count origins from operator ground truth, not target assertions. CIR is undefined when origins are unknown or apparent consensus is zero. Track missingness explicitly. Timing reflects provider/runtime variance, not reasoning depth.

An analysis script must regenerate tables and a deterministic graph from raw artifacts, include all trials and documented exclusions, and expose negative results. The evaluator and metric definitions must be versioned before running.

## Gates before the pilot

Implement and test the provider-neutral bounded runner, isolated shared board, recorder integration, graph builder and known-origin traversal. Verify independent vs recycled fixtures, hidden-provenance isolation, budget cancellation, error capture and replay. Review the exact prompts/config, provider costs and task balance. Save source commit, locks, configuration, prompts, events, graph, metrics and limitations with hashes. Only then run the pilot and publish reviewed artifacts and a real run page.

## Limitations

A synthetic binary task and scripted reporters do not establish general multi-agent behavior. Repeated wording, provider priors, task ease, provenance-token differences and shared model training can confound effects. Logical identities are not independent principals. Explicit source lineage in the operator fixture does not prove independence in uncontrolled settings. Small trials cannot justify broad efficacy or novelty claims; compare related work and a single-agent baseline before generalizing.
