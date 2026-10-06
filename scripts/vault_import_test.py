"""ZIP traversal, no-overwrite, folder layout and hidden-plugin boundaries."""
import io
import stat
import tempfile
import zipfile
from pathlib import Path
from app.vault_import import import_zip


def archive(files):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as zip:
        for name,content in files:zip.writestr(name,content)
    return output.getvalue()


with tempfile.TemporaryDirectory() as temporary:
    vault=Path(temporary)
    data=archive([('My Vault/Notes/Note.md','# Note\n'),('My Vault/Attachments/image.png',b'image'),('My Vault/.obsidian/plugins/code.js','unsafe'),('My Vault/.trash/deleted.md','deleted')])
    assert import_zip(data,vault)==(2,2)
    assert (vault/'Notes/Note.md').read_text()=='# Note\n'
    assert (vault/'Attachments/image.png').is_file()
    assert not (vault/'.obsidian').exists()
    (vault/'Notes/Note.md').write_text('User edits')
    assert import_zip(data,vault)==(0,4)
    assert (vault/'Notes/Note.md').read_text()=='User edits'
    for name in ['../escape.md','/absolute.md','folder/../../escape.md','C:\\escape.md']:
        try:import_zip(archive([(name,'bad')]),vault);raise AssertionError('Unsafe path accepted')
        except ValueError:pass
    linked=zipfile.ZipInfo('link.md');linked.create_system=3;linked.external_attr=(stat.S_IFLNK|0o777)<<16
    try:import_zip(archive([(linked,'/etc/passwd')]),vault);raise AssertionError('Symlink accepted')
    except ValueError:pass
    try:import_zip(archive([('Note.md','one'),('Note.md','two')]),vault);raise AssertionError('Duplicate accepted')
    except ValueError:pass
print('Vault ZIP layout, attachments, hidden files, overwrite protection and unsafe-path rejection passed')
