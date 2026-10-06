"""Initialize only the new stack-owned vault; never import the host vault."""
import json
import os
from pathlib import Path

vault = Path('/vault')
config = Path('/obsidian-config')
for directory in (vault, vault / '.obsidian', config, config / '.config', config / '.config/obsidian'):
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, 10001, 10001)
welcome = vault / 'Welcome.md'
if not welcome.exists() and not any(vault.rglob('*.md')):
    welcome.write_text('# Welcome to Forgetful Me\n\nThis vault lives inside your Docker stack. Notes persist across container restarts.\n\nOpen [[Forgetful Me/Home|Home]] for the page library, website indexes and browsing history.\n')
    os.chown(welcome, 10001, 10001)
registry = config / '.config/obsidian/obsidian.json'
if not registry.exists():
    registry.write_text(json.dumps({'vaults': {'forgetfulme': {'path': '/vault', 'ts': 0, 'open': True}}}))
    os.chown(registry, 10001, 10001)
print('Stack-owned vault initialized')
