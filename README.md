# Use Tokenomics in Codex

Tokenomics helps you delegate bounded work to Luna while keeping GPT-6.1 Sol responsible for the task. You can also audit selected tasks to compare observed token use, cache use, and time. Tokens do not measure exact Codex subscription allowance, and savings remain unknown without an equivalent baseline.

## Update only the skill

To install or update Tokenomics, use Python and Git. If you already have a checkout, skip step 1 and use its directory in step 2.

1. Clone the repository:

   ```powershell
   git clone https://github.com/tonesjones/codex-tokenomics-skill.git
   ```

2. Enter the repository directory:

   ```powershell
   cd codex-tokenomics-skill
   ```

3. Update the checkout from `main`:

   ```powershell
   git pull --ff-only origin main
   ```

4. Run the skill installer:

   ```powershell
   python install_skill.py
   ```

On macOS or Linux, use `python3` if `python` is unavailable.

The installer copies the skill's managed files and verifies their hashes. It backs up an existing installation under this checkout's `.tokenomics/install-backups` directory and prints the backup path. Your global guidance, model settings, and Poteto roles stay unchanged.

By default, the installer uses `~/.agents/skills/tokenomics`. If `~/.codex/skills/tokenomics` exists and the newer location does not, the installer updates that existing folder.

To update an explicit installation on Windows, run:

```powershell
python install_skill.py --target "$env:USERPROFILE\.codex\skills\tokenomics"
```

Start a new Codex task to load the updated instructions. If the skill does not appear, restart Codex. See the [official skill discovery guide](https://learn.chatgpt.com/docs/build-skills) for supported locations.

## Install the skill in a project

To make Tokenomics available in a local or cloud project, run the installer with the target repository's path. Replace `/path/to/project` with that path:

```bash
python3 install_skill.py --repo-root /path/to/project
```

Run this command from the Tokenomics checkout. The installer copies the skill into the target repository's `.agents/skills/tokenomics` directory. Keep the maintained source in this repository under `skills/tokenomics`.

For cloud use, add the command to environment setup or commit the installed skill files in the target repository. Configure each cloud environment or repository once. Updating your local installation does not update cloud environments.

Routing and outcome records work in both environments. Token measurement requires accessible session metadata. If a cloud session has no accessible log, associate its actual runtime ID with `environment="cloud"` and `path=None`. The collector reports unknown usage. Live cloud collection remains unverified.

## Use Tokenomics

Invoke `$tokenomics` when a substantial task has bounded work that Luna can complete independently. Keep small or coupled tasks in Sol without another routing check.

Keep Sol responsible for planning, integration, and final review. Delegate only when the expected benefit exceeds preparation, review, and possible recovery. Return inadequate Luna work to Sol. Use Astra only after explicit approval for the specific question.

Verify the child's model through runtime metadata. Record whether its output is usable separately from whether the full task meets the acceptance checks. A routing recommendation alone does not establish that delegation worked or saved usage.

Follow the [Tokenomics skill instructions](skills/tokenomics/SKILL.md) for execution and record examples. The skill cannot change the current model or reasoning effort.

## Audit a selected task

Ask Codex to audit a selected task when you need usage evidence. The skill maintains the decision, outcome, and session associations. You do not need to run an audit each turn or keep a separate manual log.

After the skill records a decision and associates its sessions, collect its measurements. Replace `DECISION_ID` with the recorded ID:

```powershell
python skills/tokenomics/tokenomics_router.py --log .tokenomics/decisions.jsonl --collect DECISION_ID
```

Then summarize the log:

```powershell
python skills/tokenomics/tokenomics_router.py --log .tokenomics/decisions.jsonl --summary
```

Run these commands from this checkout. From another project, use the router path in that project's installed skill folder.

Include the parent session's preparation, review, and recovery work, plus every related child. Label children created for Tokenomics separately from reviews required by another skill. The collector reads only explicitly associated sessions and stores metadata and measurements, without message text, source code, or credentials.

Read measurement coverage alongside the totals. Missing fields, ambiguous counter resets, and incomplete intervals remain unknown. Cached input is part of total input. Estimates stay separate from observations. Account snapshots describe account-wide usage and can include concurrent chats or resets.

For an occasional comparison, use equivalent Sol-only and Sol-plus-Luna tasks with the same acceptance checks. Include coordination, review, and recovery in both runs. Record effort and cache conditions. Compare consumption and time per accepted result without claiming exact subscription savings. Record existing runs through the skill's comparison workflow. Do not duplicate tasks just to populate a report.

See [CHECKPOINT.md](CHECKPOINT.md) for fixture results and the separate live local verification.

## Verify a change

Run the focused tests from this checkout:

```powershell
python -m unittest discover -s tests -v
```

Check the [skill instructions](skills/tokenomics/SKILL.md) against the implementation before changing routing or measurement behavior. Keep runtime logs, session metadata, and installation backups out of Git. The repository's [`.gitignore`](.gitignore) allows only the maintained configuration, skill, installer, test, and documentation files.

## Restore the bundled Windows configuration

To restore the accompanying global guidance and model preferences, use the full installer:

```powershell
.\install.ps1
```

This command also installs `AGENTS.md` and `pstack-models.md` and updates model preferences in `config.toml`. Review [install.ps1](install.ps1) before running it. Use `install_skill.py` for a skill-only update.

The full installer uses `$env:CODEX_HOME` when set, otherwise `$env:USERPROFILE\.codex`. It writes backups beneath that directory's `backups/tokenomics-<timestamp>` folder. Poteto roles go to `$env:USERPROFILE\.agents\pstack-models.md`.

To roll back a skill update, restore its folder from the backup path printed by `install_skill.py`. To restore an older full configuration, select that version in Git and rerun `install.ps1`.
