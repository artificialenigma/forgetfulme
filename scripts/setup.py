"""Generate local credentials without printing them or replacing an existing .env."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
text = (root / '.env.example').read_text()
text = text.replace('replace-with-a-long-random-password', secrets.token_hex(32))
text = text.replace('replace-with-a-different-long-random-password', secrets.token_hex(32))
try:
    fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit('.env already exists; left unchanged.')
with os.fdopen(fd, 'w') as output:
    output.write(text)
(root / 'backups').mkdir(exist_ok=True)
print('Created .env with random credentials. Keep it private.')
