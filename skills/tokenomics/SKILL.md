---
name: tokenomics
description: Route substantial Codex work among GPT-6 Luna, GPT-5.6 Terra, and GPT-6 Sol when bounded delegation can reduce cost or time without reducing correctness. Applies to multi-step tasks with genuinely independent subtasks; skip for small or tightly coupled work.
---

# Tokenomics

Apply the global model-routing policy in `~/.codex/AGENTS.md`.

- At the first meaningful planning checkpoint, recommend a manual switch when the active model is clearly too strong or too weak for a nontrivial task. Give the recommended model and one short reason; do not block progress or repeat the recommendation without a material scope change.
- First compare expected savings with delegation and context overhead. Do small tasks directly.
- Use GPT-6 Luna for clear, bounded, low-ambiguity worker tasks.
- Keep GPT-5.6 Terra as the provisional moderate tier for moderately complex or judgment-bearing worker tasks. Whether GPT-6 Luna or GPT-6 Sol should replace Terra is undecided; do not present either as a chosen replacement.
- Keep planning, architecture, hard debugging, security-sensitive reasoning, integration, and consequential final judgment in GPT-6 Sol.
- Recommend GPT-6 Astra only for the hardest end-to-end work or unusually large/long-horizon tasks when its higher cost is justified by likely quality or rework savings; do not treat Astra as the default.
- Escalate Luna to Terra, then Terra to Sol, when evidence shows the weaker model is mismatched. Do not churn retries.
- When selecting a child model explicitly, use a self-contained prompt with `fork_turns="none"` or a small positive `fork_turns` value; full-history forks inherit the parent and cannot take a model override.
- Treat recorded child-session model metadata as authoritative. An accepted spawn argument alone is not proof that the override took effect, and the child’s prose is not model evidence.

This skill guides decisions; it does not require delegation and does not authorize unrelated work. Poteto Mode's Codex harness guidance reads `~/.agents/pstack-models.md` when present to set per-role model choices. This repository's installer copies `pstack-models.md` there.
