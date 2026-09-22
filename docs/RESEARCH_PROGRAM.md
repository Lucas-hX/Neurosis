# NEUROSIS Research — Research Program

NEUROSIS Research is an independent AI security research organization studying security failures in autonomous and embodied intelligent systems.

Its guiding question is:

> **What breaks when intelligence stops being a stateless model and becomes a persistent actor in a shared world?**

## Origin and continuity

NEUROSIS began with a question about autonomous agents: what happens when they stop operating as isolated, ephemeral processes and begin to accumulate, retrieve, modify, share, and inherit knowledge over time?

The original work explored external and associative memory, persistent shared substrates, collective behavior, stigmergic and blackboard coordination, reconsolidation, forgetting, contamination, provenance, Byzantine propagation, Sybil consensus failures, correlated evidence, and adversarial agent ecologies.

The central concern was broader than agent memory: new security failures appear when intelligent systems acquire persistence, shared state, autonomy, and influence over one another. That concern remains central to NEUROSIS Research.

The organization now follows a continuous path:

**memory → agents → multi-agent systems → perception → embodiment → physical action**

This expansion preserves the original public memory and agent-population research as part of a larger security model.

## Research areas

### Agent Security

Autonomous LLM systems, tool use, agent loops, sandboxing, authority boundaries, prompt injection, state manipulation, and long-horizon behavior.

### Memory & Provenance

Machine memory, retrieval, reconsolidation, poisoning, provenance, shared knowledge, trust, correlated evidence, persistence, and cross-agent propagation.

### Multi-Agent Systems

Coordination, collective behavior, shared state, consensus, adversarial propagation, emergent substrates, Byzantine behavior, and properties that do not exist in isolated agents.

### Embodied & Physical AI Security

Vision-language models, Vision-Language-Action systems, physical prompt injection, perception-to-action boundaries, robotics, autonomous systems, and adversarial interaction with physical environments.

Future work may include robotics security, robot fleets, collaborative robots, VLA and VLM red teaming, ROS ecosystems, shared robotic memory, autonomous vehicles, drones, and other cyber-physical intelligent systems.

## Bridge project: StaleAction

The first working paper under the expanded scope is **Physical TOCTOU Attacks Against Vision-Language-Action Robots**, with the project name **StaleAction**.

The hypothesis is that a VLA robot can correctly observe a physical scene, generate or commit to an action sequence, and execute that sequence after task-relevant physical state has changed. The adversary targets the observation-to-action gap rather than corrupting the observation, model, training data, or software stack.

The project proposes two candidate quantities:

- **Observation–Action Age (OAA):** how old the task-relevant observation is when an action reaches the physical world.
- **Adversarial Freshness Window (AFW):** the post-observation interval in which a physical change can still produce a target failure before corrective evidence is incorporated.

The current draft defines the threat model and experimental plan. It does not claim empirical validation.

StaleAction continues the original NEUROSIS question. In memory systems, a representation can be stale, poisoned, duplicated, or incorrectly sourced. In embodied systems, a representation can become physically stale between perception and action. In future fleets, the chain can combine both:

**physical observation → local memory → shared memory → other agents → physical actions**

## Research principles

- **Empirical:** support claims with measurable experiments whenever possible.
- **Reproducible:** publish configurations, metrics, code, and relevant artifacts when practical.
- **Adversarial:** study intentional manipulation, unexpected environments, correlated failures, and hostile inputs.
- **Systems-oriented:** examine complete systems and interaction boundaries.
- **Open:** publish work when responsible disclosure and safety permit.
- **Evidence-aware:** distinguish hypotheses, observations, confirmed vulnerabilities, negative results, and speculation.

Negative results and failed hypotheses are acceptable. Unreproducible claims are not treated as findings.

## Organizational position

NEUROSIS Research is a small independent research organization. It does not present itself as a university, established institute, large company, or physical laboratory. Credibility must come from good questions, rigorous experiments, public methodology, useful open tools, thoughtful papers, and careful engagement with existing literature.

## Long-term thesis

AI security is moving from securing models to securing intelligent systems. Those systems increasingly combine memory, tools, autonomy, multiple cooperating agents, perception, persistent state, infrastructure access, and physical embodiment.

NEUROSIS Research exists to investigate the security boundaries that emerge along that transition.
