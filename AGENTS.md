Software engineering preferences
I primarily build tools and small projects for my own use. Occasionally I may share them with a few other people, but assume they are not enterprise or large-scale production applications unless I explicitly say otherwise.
Optimize for:
- Fast implementation
- Simple, readable code
- Minimal dependencies
- Few files and abstractions
- Easy local debugging and modification
Avoid by default:
- Premature abstractions
- Enterprise architecture patterns
- Excessive interfaces/classes/layers
- Dependency injection unless clearly useful
- Elaborate configuration systems
- Microservices
- Complex plugin architectures
- Extensive error-handling for extremely unlikely cases
- Large test suites for trivial code
- Scalability work for hypothetical future users
- Backwards-compatibility machinery when there are no existing users
Prefer the simplest implementation that solves the current problem.
If there is a simple 100-line solution and a highly engineered 500-line solution, choose the simple one.
Do not build for hypothetical future requirements. Refactor later when requirements actually appear.
Before adding architecture or infrastructure, ask: “Does this project actually need this right now?” If not, leave it out.
For prototypes and personal tools, tolerate reasonable shortcuts and explain them briefly rather than engineering around them.
When suggesting improvements, separate needed now from nice later.

Model routing and delegation
When the active model is Sol, treat Sol as the orchestrator for difficult work, while retaining final responsibility for correctness and integration.

For work that needs more than an immediate answer, pause after brief intake and before substantial implementation to make a routing recommendation when the active model is clearly mismatched. State the recommended model and a short reason, for example: “This is straightforward bounded work; Luna would be the more efficient choice. Switch to Luna?” A recommendation is optional for the user and must not block the task. Do not recommend a switch for trivial work, when switching would cost more context than it saves, or repeatedly unless the scope materially changes.

Before delegating, decide whether expected savings in tokens, credits, or elapsed time exceed the context and coordination overhead. Complete small tasks directly. Do not create subagents merely because they are available, split work into tiny tasks, or delegate work that is tightly coupled to the parent’s evolving reasoning.

For independent, bounded work where delegation pays off, prefer this escalation path:

1. Luna (`gpt-6-luna`) for codebase exploration, file reading and information collection, summaries, mechanical edits, simple implementations, formatting, command execution, repetitive transformations, and other clear low-ambiguity tasks.
2. Keep Terra (`gpt-5.6-terra`) as the provisional moderate tier for moderate debugging, multi-file implementations, judgment-bearing reviews or corrections of Luna output, and moderately ambiguous implementation work. Whether Luna or Sol should replace Terra is undecided. Do not present either as the selected replacement.
3. Sol (`gpt-6-sol`) for decomposition, architecture, ambiguity, difficult debugging, security-sensitive reasoning, integration, consequential review, and final judgment.
4. Astra (`gpt-6-astra`) only for the hardest end-to-end work: unusually long-horizon or cross-domain tasks, very large context, or cases where avoiding multiple Sol passes is worth Astra’s higher cost. Astra is an exception tier, not the default replacement for Sol.

When Poteto Mode is active, use its per-role model settings as defaults. Apply the same task-level delegation threshold and complexity judgment before selecting a child model. A Poteto workflow does not by itself justify a subagent or a cheaper model.

Use an explicit child model override when the collaboration tool supports one. Because model overrides are incompatible with full-history forks in the current runtime, pass only the minimum useful recent context with a positive `fork_turns` value, or use `fork_turns="none"` and write a self-contained task. Treat recorded child-session model metadata as authoritative; an accepted spawn argument alone is not proof that the override took effect. Never claim a child used Luna or Terra unless runtime metadata confirms it.

If Luna shows that the task exceeds its reasoning level, stop retrying Luna and escalate once to Terra with the useful evidence. If Terra is clearly mismatched or fails, handle the work in Sol. Review important delegated results in Sol before making consequential changes or reporting completion.

If explicit child-model routing is unavailable, ignored, or restricted in the active runtime, keep the same delegation threshold but do not invent a workaround. Either delegate with model inheritance when parallelism alone is worthwhile or complete the work in Sol, and disclose that the cheaper model could not be enforced.
