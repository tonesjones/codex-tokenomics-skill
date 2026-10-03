"""Install only Tokenomics on Windows, macOS or Linux, with a recoverable backup."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

FILES = ('SKILL.md', 'tokenomics_router.py', 'agents/openai.yaml')


def install_skill(target, backup_root=None):
    source = Path(__file__).resolve().parent / 'skills' / 'tokenomics'
    target = Path(target).expanduser().resolve()
    if target.name != 'tokenomics' or target == source or source.is_relative_to(target):
        raise ValueError('target must be a separate tokenomics skill folder')
    if target.exists() and not (target / 'SKILL.md').is_file():
        raise ValueError('existing target is not a skill folder')
    # Backups stay outside discovery locations. No guidance or config is changed.
    backup = None
    if target.exists():
        backup_root = Path(backup_root).expanduser().resolve() if backup_root else Path(__file__).resolve().parent / '.tokenomics' / 'install-backups'
        if backup_root == target or backup_root.is_relative_to(target):
            raise ValueError('backup must be outside the target skill folder')
        backup = backup_root / ('tokenomics-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copytree(target, backup)
    hashes = {}
    for name in FILES:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
        digest = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise OSError(f'installed file hash mismatch: {name}')
        hashes[name] = digest
    return dict(target=str(target), backup=str(backup) if backup else None, sha256=hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--target', type=Path, help='Exact destination tokenomics folder')
    group.add_argument('--repo-root', type=Path, help='Install into this repo under .agents/skills/tokenomics')
    parser.add_argument('--backup-root', type=Path)
    args = parser.parse_args()
    legacy = Path.home() / '.codex' / 'skills' / 'tokenomics'
    current = Path.home() / '.agents' / 'skills' / 'tokenomics'
    target = args.target or (args.repo_root / '.agents' / 'skills' / 'tokenomics' if args.repo_root else legacy if legacy.exists() and not current.exists() else current)
    print(json.dumps(install_skill(target, args.backup_root), indent=2))


if __name__ == '__main__':
    main()
