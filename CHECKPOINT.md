# Tokenomics subscription audit release checkpoint

Date: 2026-10-03. Publication builds on the upstream Sol ownership and cache-aware routing update.

The existing dependency-free router/logger/summarizer now pair decisions and outcomes with stable IDs. Original routing fields are preserved. Child usability, task acceptance and escalation are separate. Retrospective and unpaired legacy records are explicit.

Selective measurement reads only associated parent/child runtime metadata, including coordination, review and recovery where available. It handles cumulative counters, repeated events, resets, missing baselines and incomplete intervals without claiming exact subscription allowance savings. Occasional equivalent task pairs use the same acceptance checks and record effort/cache conditions. There is no dashboard, recurring job, billing integration or automatic task duplication.

`install_skill.py` provides a skill-only installer for local or repository use on Windows, macOS and Linux, with backups and hash verification. Repository installation uses `.agents/skills/tokenomics`. Cloud sessions without accessible metadata record unknown usage rather than invented measurements.

## Verification

- 24 fixture tests pass, including pairing, preserved tiers, escalation, missing measurements, deduplication/reset handling, parent/child aggregation, cloud metadata unavailability and installation/backup behavior.
- Skill frontmatter validation and whitespace checks pass.
- A separate live check on the authorized local parent session matched cumulative token counters and observed model/effort against an independent metadata-only read. The session was open, so completed elapsed time and complete-task coverage were unknown.
- Child aggregation, paired comparisons and cloud metadata-unavailable behavior have fixture evidence. Live cloud collection remains unverified. No equivalent observed baseline establishes subscription savings.

Detailed session identifiers, measurements, intake patches and installation backups remain local in ignored paths. They are not published in this repository. Unrelated local guidance/settings edits are preserved.

See README.md and skills/tokenomics/SKILL.md for installation and selective audit instructions. Updating a local skill does not configure every cloud environment; each cloud project needs its repository skill installed once or included in environment setup.
