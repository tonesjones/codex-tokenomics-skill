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
Keep `gpt-6.1-sol` as the owner of a substantial task from intake through final review. Plan, coordinate, integrate, and make consequential judgments in that session. A new model may need to rebuild context, while staying in Sol may reuse cached input. Neither cache behavior nor savings are guaranteed; do not switch the top-level model merely because a task contains a cheap-looking step.

Set Sol's reasoning effort for the work at hand: low for routine coordination, medium for decomposition and ordinary integration, high for difficult reasoning or consequential review. The installed low setting is a starting default, not a ceiling. Use runtime effort controls when available; instructions alone do not change effort. Avoid changing effort on every turn when the benefit is unclear.

Complete small or tightly coupled work in Sol. For substantial, independent, bounded work, consider one compact Luna (`gpt-6-luna`) assignment with an objective, relevant context, acceptance criteria, and a stop condition. Good examples are evidence collection, mechanical edits, a well-scoped implementation, and running defined tests. Assess the actual work's ambiguity and difficulty; a label such as “test” does not make a hard problem suitable for Luna. Delegate only when the expected benefit exceeds preparing the handoff, child context and file reads, Sol review, and possible recovery. Use `$tokenomics` for a plausible decision, not every small task.

Keep task decomposition, architecture, difficult debugging, security decisions, integration, and final review with Sol. Check important child results against source or tests and resolve conflicts between children before reporting completion. If Luna reaches a reasoning barrier, bring its evidence back to Sol instead of repeatedly retrying Luna.

Astra (`gpt-6-astra`) is an exceptional consultation for a specific unresolved question. Before any Astra spawn or top-level switch, present its purpose and scope and obtain explicit human approval for that use. A router flag, Poteto role, or prior approval for another question does not grant it. Complete the already-authorized Sol work first so the request is concrete. After the consultation, Sol owns integration and final review.

When Poteto Mode is active, treat its per-role models as defaults, subject to the same capability and handoff check. A Poteto workflow does not itself justify a child. Use explicit child model overrides when supported, a small context fork or self-contained prompt, and verify the observed model from runtime metadata when accessible. If the override cannot be verified, describe it as requested but unverified. If routing is unavailable, continue in Sol.
