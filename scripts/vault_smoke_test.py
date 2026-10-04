"""Verify shared-vault writes as the actual application users, without touching a host vault."""
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parent.parent
name = f'/vault/.connectivity-test-{uuid.uuid4().hex}.md'
content = '# Forgetful Me connectivity test\n'


def run(*args):
    return subprocess.check_output(['docker', 'compose', *args], cwd=root, text=True)


try:
    run('exec', '-T', 'worker', 'python', '-c',
        'from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])', name, content)
    assert run('exec', '-T', '--user', '10001:10001', 'obsidian', 'cat', name) == content
    run('exec', '-T', '--user', '10001:10001', 'obsidian', 'sh', '-c',
        'test -w /vault && test -s /vault/Welcome.md && pgrep -x obsidian >/dev/null')
finally:
    run('exec', '-T', 'worker', 'python', '-c',
        'from pathlib import Path; import sys; Path(sys.argv[1]).unlink(missing_ok=True)', name)
print('PASS: worker write, Obsidian user read/write permissions, welcome note, and running Obsidian process')
