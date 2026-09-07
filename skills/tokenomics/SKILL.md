---
name: tokenomics
description: Route substantial Codex work among Luna, Terra, and Sol when bounded delegation can reduce cost or time without reducing correctness. Applies to multi-step tasks with genuinely independent subtasks; skip for small or tightly coupled work.
---

# Tokenomics

Apply the global model-routing policy in `~/.codex/AGENTS.md`.

- First compare expected savings with delegation and context overhead. Do small tasks directly.
- Use Luna for clear, bounded, low-ambiguity worker tasks.
- Use Terra for moderately complex or judgment-bearing worker tasks.
- Keep planning, architecture, hard debugging, security-sensitive reasoning, integration, and consequential final judgment in Sol.
- Escalate Luna to Terra, then Terra to Sol, when evidence shows the weaker model is mismatched. Do not churn retries.
- When selecting a child model explicitly, use a self-contained prompt with `fork_turns="none"` or a small positive `fork_turns` value; full-history forks inherit the parent and cannot take a model override.
- Treat recorded child-session model metadata as authoritative. An accepted spawn argument alone is not proof that the override took effect, and the child’s prose is not model evidence.

This skill guides decisions; it does not require delegation and does not authorize unrelated work.
