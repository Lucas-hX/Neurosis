# EXP-001 protocol v1

`protocol-v1.json` freezes the pre-pilot design, schedule, prompts, model settings, metrics, exclusions, uncertainty method, budgets and stop rules. Changes require a new experiment version; do not edit the meaning of v1 after a provider pilot begins.

The four reporters are deterministic fixtures. Only the target uses Groq `openai/gpt-oss-120b`. Every trial is a separate five-agent run and every seed has all eight matched cells. Hidden-provenance prompts omit source IDs and dependency fields, while operator events retain controlled origin truth for evaluation.

Fixture execution is an implementation check and is never a scientific result. A paid preflight requires a clean commit, a rotated credential, current price review, and a provider-side spend limit.
