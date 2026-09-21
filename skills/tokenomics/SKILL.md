---
name: tokenomics
description: Recommend and verify cost-aware routing among Luna, Terra, Sol, and Astra when switching or bounded delegation can reduce cost or time without reducing correctness. Applies to substantial tasks; skip small or tightly coupled work.
---

# Tokenomics

Apply the global model-routing policy in `~/.codex/AGENTS.md`.

- At the first meaningful planning checkpoint, recommend a manual switch when the active model is clearly too strong or too weak for a nontrivial task. Give the recommended model and one short reason; do not block progress or repeat the recommendation without a material scope change.
- First compare expected savings with delegation and context overhead. Do small tasks directly.
- Use Luna for clear, bounded, low-ambiguity worker tasks.
- Use Terra for moderately complex or judgment-bearing worker tasks.
- Keep planning, architecture, hard debugging, security-sensitive reasoning, integration, and consequential final judgment in Sol.
- Recommend Astra only for the hardest end-to-end work or unusually large/long-horizon tasks when its higher cost is justified by likely quality or rework savings; do not treat Astra as the default.
- Escalate Luna to Terra, then Terra to Sol, when evidence shows the weaker model is mismatched. Do not churn retries.
- When selecting a child model explicitly, use a self-contained prompt with `fork_turns="none"` or a small positive `fork_turns` value; full-history forks inherit the parent and cannot take a model override.
- Treat recorded child-session model metadata as authoritative. An accepted spawn argument alone is not proof that the override took effect, and the child’s prose is not model evidence.

Top-level model switches are advisory and require the user or runtime to apply them. Child-model selection is an attempt until recorded child-session metadata confirms the model that ran.

This skill does not require delegation, guarantee model selection, or authorize unrelated work.
