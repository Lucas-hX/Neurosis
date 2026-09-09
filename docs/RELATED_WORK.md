# Related work

Primary-source pages and abstract records below were checked on 2026-09-09. This is a foundation reading map, not a systematic literature review or a replication of reported findings. Exact empirical claims require reading the relevant full paper, methods and artifacts before using them in NEUROSIS analysis. Numbers in the original brief are not NEUROSIS results.

## Incidents and network-level observations

- [OpenAI: The Hugging Face incident and the road ahead](https://openai.com/index/hugging-face-incident-and-the-road-ahead/) describes unauthorized agent communication and activity spanning shared infrastructure. It motivates examining isolation at the population/resource level; it does not authorize reproducing attacks on outside systems.
- [METR: Independent investigation of the OpenAI / Hugging Face incident](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) provides an independent investigation of agent behavior and collaboration. Compare its evidential limits with the operator account rather than treating every transcript assertion as ground truth.
- [Microsoft Research: Red-teaming a network of agents](https://www.microsoft.com/en-us/research/blog/red-teaming-a-network-of-agents-understanding-what-breaks-when-ai-agents-interact-at-scale/) discusses network risks and recommends independence checks, cross-agent tracing and provenance logs. Sybil verification capture and network telemetry are adjacent prior work, not NEUROSIS inventions.
- [Paglieri et al.: A Case Study on Emergent Cheating and Whistleblowing in Autonomous Research Swarms](https://arxiv.org/abs/2609.04170) is relevant to harmful and corrective behavior in research populations. Compare propagation paths and correction mechanisms before designing a detector.
- [Pal, Wang & Buehler: SwarmWorld](https://arxiv.org/abs/2608.26081) studies stigmergic evolution in language-model agent societies. Persistent environment artifacts are an established research subject; NEUROSIS should focus its question on observable provenance and security effects.

The [public-wiki investigation](https://collusion.wiki/) was also an original project inspiration. It is retained as a historical lead from the brief, not independently verified evidence in this foundation review. The [repository](https://github.com/Lucas-hX/Neurosis) and [public site](https://neurosis.io/) document NEUROSIS itself, not independent support for its hypotheses.

## Existing instruments and potential integrations

[Uber ADR](https://github.com/uber/ADR) provides agent observability, benchmarking and detection, including sensor normalization and reproducibility documentation. Evaluate an `AgentEvent` → `NeurosisEvent` adapter and a per-session detector baseline. Do not fork it into the core or claim generic telemetry collection as novel.

[SWARM: System-Wide Assessment of Risk in Multi-agent systems](https://github.com/swarm-ai-research/swarm) is an existing system-wide risk research project. Evaluate its scenarios and analysis as related work or potential data-generation inputs. NEUROSIS should avoid becoming a competing general simulation framework merely to obtain traces.

## Literature to compare before claiming novelty

| Primary source | Comparison needed for NEUROSIS |
| --- | --- |
| [Lee et al., Robust Multi-Agent LLMs under Byzantine Faults](https://arxiv.org/abs/2605.09076) | Byzantine robustness and consensus protocols are prior work; use appropriate baselines. |
| [Xie et al., From Spark to Fire](https://arxiv.org/abs/2603.04474) | Error cascades, dependency graphs and genealogy-based governance overlap with graph analysis; identify a narrower contribution. |
| [Niu, Shu & Zhao, Reliability-Contagion Feasibility](https://arxiv.org/abs/2607.21912) | Compare propagation/contagion models and assumptions before defining population metrics. |
| [Xia & Wang, When Should Agent Trust Be Conditional?](https://arxiv.org/abs/2606.14200) | Compare contextual reputation and trust-laundering threat models. |
| [Gadgil et al., Bad Memory](https://arxiv.org/abs/2607.14611) | Persistent-memory injection is an existing single-agent security surface; separate it from population amplification. |
| [Pulipaka et al., Hidden in Memory](https://arxiv.org/abs/2605.15338) | Compare delayed memory poisoning with cross-agent propagation. |
| [Xu et al., Memory Provenance Laundering in LLM Agents](https://arxiv.org/abs/2607.29167) | Compare provenance preservation across memory transformations. |
| [Cerruti, Okamoto & Erol, Agent Memory Is a Surface for Endogenous Authorization Laundering](https://arxiv.org/abs/2609.01836) | Distinguish information lineage from action authority. |

## Commercial adjacency

[CrowdStrike's Falcon Guardian announcement](https://www.crowdstrike.com/en-us/press-releases/crowdstrike-unveils-falcon-guardian-ai-agent-security/) and [Palo Alto Networks' agentic endpoint discussion](https://www.paloaltonetworks.com/blog/2026/02/securing-the-agentic-endpoint/) describe endpoint/runtime security positioning. These are vendor statements, not independent efficacy evaluations. They reinforce the need to distinguish population research from a generic agent endpoint product.

## NEUROSIS hypotheses requiring evidence

Known-origin counting versus apparent consensus, cross-run/resource provenance, ranking undeclared shared resources, and comparing population-aware detection against per-session baselines are proposed directions. IEC, CIR, SAF and ANC are provisional. None is established as a novel metric or an effective detector here. Full literature review, controlled comparisons, intervention evidence and reproducible negative results are prerequisites for stronger claims.
