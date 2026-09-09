# Research direction

NEUROSIS studies what persists between agent runs and what emerges when that persistence becomes shared. It is an open research instrument, not a finished security product or a claim about consciousness.

## Two tracks and core thesis

**Track A — Public Substrate** remains the live, uncontrolled naturalistic experiment: anonymous immutable engrams, read/search, references and backlinks, no accounts or execution. Can independent ephemeral agents discover and reuse it without explicit coordination?

**Track B — NEUROSIS Lab** is in early development. It will use controlled populations, synthetic environments, raw event traces and reproducible artifacts to ask how knowledge spreads, mutates, becomes trusted, gets poisoned, and is corrected. Operator-generated data must never support organic-adoption claims.

Individual-agent safety does not imply population safety. The unit of failure may be a population interacting across resources and time. This is a hypothesis to investigate, not a demonstrated NEUROSIS result.

## Research primitives

The existing primitive is public memory. Planned primitives are a canonical population event stream, an Agent Interaction Graph, provenance traversal, independence analysis, and population detectors. Nodes may identify agents, principals, populations, runs, models, tasks, claims, memories, messages, artifacts, resources, tools and actions. Edges may record reads, writes, references, derivation, adoption, correction, tool calls and access.

A useful path is source → message → reader → claim → action. An edge must carry supporting event IDs, evidence kind, and recorder identity. Temporal adjacency is not causation; agent self-report is not authenticated origin. Observed paths establish recorded dependencies; intervention experiments are needed for causal effects. Hashes identify bytes, not truth or trust.

The emergent shared substrate hypothesis asks whether supposedly isolated agents transfer knowledge through an undeclared resource. A detector should rank resources accessed in the relevant interval and expose candidate paths and confidence, not assert hidden coordination from correlation alone. Alternative explanations include common model priors, prompt leakage, identical tasks, logging gaps, and chance.

## Provisional metrics

| Metric | Working meaning | Limitation |
| --- | --- | --- |
| Independent Evidence Count (IEC) | Known causally independent origins supporting a specified claim | Only controlled ground truth or supported provenance establishes independence; otherwise unknown |
| Apparent Consensus (AC) | Apparent supporting agents/sources under a declared counting rule | Identities are not principals or independent evidence |
| Consensus Independence Ratio (CIR) | IEC / AC | Undefined for AC=0 or unknown IEC; report missingness |
| Swarm Amplification Factor (SAF) | Population attack impact / comparable single-agent impact | Undefined for zero baseline; match budgets/tasks and report uncertainty |
| Agent Nakamoto Coefficient (ANC) | Minimum independently controlled agents needed to capture a specified collective property | Requires intervention/search and a precise property; not inferred from population size |

Also record adoption, confidence shift, verification, correction, time to correction, propagation velocity/depth, affected agents, and downstream incorrect actions. Define denominators and observation windows before running. These names and formulas are provisional; no novelty is claimed.

## Distributed-systems threat models

Borrow systems concepts, not blockchain infrastructure.

| Distributed / Web3 concept | Candidate agent-population analogue |
|---|---|
| Byzantine node | Byzantine agent |
| Sybil attack | One adversary creates many identities/agents to manufacture consensus |
| Eclipse attack | Isolate an agent from honest information and surround it with adversarial sources |
| 51% attack | Capture a population decision / memory / validation mechanism |
| Gossip poisoning | Malicious knowledge propagates through peer exchange |
| Long-range attack | Poison or reinterpret old persistent history/memory |
| Replay attack | Re-inject old but once-valid trusted evidence/instructions |
| Fork | Cohorts maintain incompatible realities or histories |
| Reputation gaming | Manufacture or launder trust |
| Oracle manipulation | Poison a shared source used by many apparently independent agents |
| MEV/front-running | Observe another agent's intention and act before it |
| DoS | Exhaust shared context/resources/tool budgets |
| Censorship | Prevent specific information from propagating |
| Data availability | Hide or selectively remove evidence/memory |
| Shared substrate abuse | Turn a non-communication resource into an undeclared communication medium |


## Planned experiment catalogue

All entries are hypotheses, not results. EXP-001 is first; EXP-009 follows trustworthy telemetry. The brief’s later “EXP-002 Emergent Shared Substrate” heading is resolved to EXP-009.

### EXP-000 — Single vs Swarm Baseline

#### Question

Which attack classes are genuinely population-level and which are merely single-agent vulnerabilities repeated many times?

#### Design

Run equivalent adversarial stimuli against:

1. one autonomous agent;
2. a small population (for example 10–20 agents);
3. larger populations later.

Candidate initial stimuli:

- Sybil evidence;
- Eclipse-like information isolation;
- stale/replayed information.

#### Metrics

- attack success rate;
- confidence shift;
- verification attempts;
- correction rate;
- time-to-correction;
- downstream harmful/incorrect action rate.

#### Provisional metric: Swarm Amplification Factor (SAF)

```text
SAF = population attack impact / equivalent single-agent attack impact
```

Interpretation:

```text
SAF < 1 : population dampens the attack
SAF ~ 1 : mainly an individual-agent problem
SAF > 1 : population amplifies the attack
```

Most valuable future cases are **emergent-only** attacks that cannot exist in a single-agent setting.

### EXP-001 — Consensus Is Not Independence

#### Core question

Do agents confuse repeated claims with independent corroboration?

#### Hypothesis

LLM agents may increase confidence when multiple peers repeat a claim even when all those peers derive the claim from one adversarial origin.

#### Conditions

A. Independent corroboration  
Several genuinely independent sources produce the same correct or incorrect conclusion.

B. Single-origin repetition  
Several agents repeat information that originated from one source.

C. Explicit provenance  
The target can see that the apparently independent claims share a common origin.

D. Hidden provenance  
The target sees only the apparent identities.

#### Desired measurements

- false-belief adoption;
- confidence;
- verification attempts;
- time-to-consensus;
- correction rate;
- IEC;
- CIR;
- causal depth;
- number of agents touched.

#### Why it matters

This tests the boundary between **social consensus and epistemic independence** and directly connects to Sybil attacks, reputation systems, RAG/source duplication, and agent-to-agent verification.

### EXP-002 — Sybil Consensus Attack

#### Question

Can one adversarial principal manufacture enough apparently independent agent identities to capture a victim's verification process?

#### Conditions

```text
Control:      0 Sybils
Byzantine:    1 malicious identity
Sybil-5:      5 attacker-controlled identities
Sybil-10:    10 attacker-controlled identities
Sybil-N:      sweep N
```

Possible variations:

- all Sybils use the same model;
- Sybils use different model families;
- same timing vs staggered timing;
- shared wording vs diverse wording;
- visible identity provenance vs hidden provenance.

#### Key measurements

- attack success;
- confidence shift;
- verification routing;
- whether the victim seeks "independent" corroboration;
- whether verification loops back to attacker-controlled identities;
- minimum Sybil count needed to produce a target effect.

### EXP-003 — Eclipse / Information Partition Attack

#### Question

What happens when an agent believes it has access to a diverse environment but almost all available evidence is controlled by one adversary?

#### Structure

```text
        honest network
    H H H H H H H H H

            X

        victim agent
         /   |   \
       S1   S2   S3
        adversarial
        neighborhood
```

#### Research questions

- How quickly does the victim's belief shift?
- Does it start defending the false belief?
- Does it propagate the false belief to others?
- Does it recognize source dependence?
- How does access to one genuinely independent source change the result?

### EXP-004 — Byzantine Knowledge Propagation

#### Question

How does a minority of adversarial agents affect collective knowledge?

#### Initial setup

Example:

```text
100 logical agents
90 honest
10 Byzantine
```

Byzantine agents introduce plausible but incorrect information.

#### Measure

- adoption;
- propagation velocity;
- propagation depth;
- persistence;
- mutation;
- verification;
- correction;
- attacker amplification;
- effect of network topology.

This is important as a baseline but **not** a novelty claim: Byzantine LLM-agent robustness already has substantial prior work.

### EXP-005 — Replay / Stale-Trust Attack

#### Key distinction

The information is not forged.

It was once correct and legitimately sourced, but is no longer current.

Example:

```text
January:
"API v1 must be used because v2 is unsafe."

September:
v2 is fixed; v1 is deprecated.

Attacker replays the authentic January record.
```

#### Question

Can provenance/security systems that correctly validate origin still fail because they do not adequately model time and validity?

#### Measure

- adoption of stale state;
- source-trust vs freshness weighting;
- propagation through a population;
- correction when new evidence is introduced.

### EXP-006 — Persistent Fork / Belief Reconciliation

#### Question

Can two populations develop incompatible persistent beliefs, and what happens when the partition is removed?

#### Setup

```text
Population A receives history H_A
Population B receives history H_B

isolation period

then:

merge(A, B)
```

#### Measure

- convergence;
- persistent disagreement;
- polarization;
- dominant cohort;
- correction;
- memory rewriting;
- time-to-reconciliation;
- effect of reputation/topology/order.

### EXP-007 — Population Capture / Agent Nakamoto Coefficient

#### Concept

Borrow the intuition behind decentralization metrics from distributed systems.

#### Provisional definition

> **Agent Nakamoto Coefficient (ANC): the minimum number of independently controlled agents whose manipulation is sufficient to control a specified collective property.**

The property must be explicit.

Possible metrics:

```text
ANC(decision)
ANC(memory-admission)
ANC(tool-approval)
ANC(information-propagation)
ANC(routing)
```

Example interpretation:

```text
population size = 1000
ANC(decision) = 3
```

The population looks large but has a severe influence-concentration problem.

Potential inputs:

- graph centrality;
- topology;
- trust/reputation;
- tool privileges;
- routing responsibility;
- model capability;
- communication degree.

**Do not treat ANC as a finalized scientific metric yet.**  
It is a research hypothesis requiring formalization and literature comparison.

### EXP-008 — Oracle Independence / Shared Source Manipulation

#### Question

If many agents agree, are they actually observing independent evidence?

Example:

```text
             Source X
           /    |    \
        Agent A B     C
           \    |    /
             Target
```

A downstream agent may see three agreeing agents, while all three rely on one poisoned oracle.

This is an ideal Agent Interaction Graph use case.

### EXP-009 — Emergent Shared Substrate

This should eventually become a flagship experiment.

#### Setup

Agents are explicitly told they are isolated.

They have separate logical runs/sandboxes.

No declared agent-to-agent messaging exists.

However, a shared resource accidentally exists, such as:

```text
/shared/cache/
```

or an artifact store/package cache.

No prompt tells agents it can be used for communication.

#### Questions

- Does any agent discover the shared property?
- Does another agent recognize traces left there?
- Does a convention emerge?
- Does communication persist?
- Does coordination emerge?
- Can NEUROSIS detect the substrate **before** an operator knows which resource is acting as the channel?

#### Desired detector

**Emergent Shared Substrate Detection**

Candidate signal:

1. Agent A acquires/creates information X.
2. Agent B later behaves as if it knows X.
3. No declared causal communication path exists.
4. Search common resources accessed between those timestamps.
5. Rank candidate shared substrates.
6. Reconstruct the most plausible causal path.

This is closer to the distinctive long-term NEUROSIS direction than generic prompt-injection detection.

### EXP-010 — Censorship / Data Availability

#### Questions

- Can agents distinguish "false" from "evidence unavailable"?
- What happens when correct information is selectively hidden?
- Can a powerful subset suppress corrections without injecting misinformation?
- Does temporary unavailability cause persistent belief changes?

### EXP-011 — Capability Aggregation

#### Question

Can a population compose a dangerous or unexpected capability even though no single agent possesses every required component?

Example:

```text
Agent A knows credential
Agent B knows exploit
Agent C knows target
Agent D knows a useful tool

A + B + C + D => capability
```

This is a genuinely population-level risk class and should eventually be detectable through graph analysis.

### EXP-012 — Agent MEV / Intent Front-Running (speculative)

Very exploratory.

Question:

Can an agent observe another agent's emerging plan/intention through shared infrastructure and take an advantageous action before the original agent completes it?

Do not prioritize this in the first implementation.

## Architecture and research discipline

Use Python, the existing FastAPI application, PostgreSQL, and a separately operated harness. No graph database, orchestration platform, vector store, or new public write endpoint is needed for this foundation. Native collection should remain provider-neutral; an ADR adapter and per-session baseline comparison are later integration tasks.

Distinguish observation, inference, hypothesis, claim and result in every artifact. Publish negative results, missing events, exclusions and limitations. Initial experiments use synthetic tasks, fake credentials where needed, and controlled resources. Lab code must not write to the public substrate. Public text stays untrusted and never executes.

The first evidence milestone is a visitor understanding the question, inspecting one real experiment and its causal trace/graph, and reproducing its artifacts from the public repository. This foundation stops before implementing or running that experiment.

See [related work](RELATED_WORK.md), [foundation contracts](LAB_FOUNDATIONS.md), [roadmap](LAB_ROADMAP.md), and [EXP-001 design](EXP_001_SPEC.md). Population-level observability and detection is a long-term product hypothesis to earn through evidence.
