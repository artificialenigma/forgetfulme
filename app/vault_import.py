"""Import portable Obsidian notes/attachments without overwriting existing files."""
import fcntl
import html
import io
import os
import secrets
import shutil
import stat
import tempfile
import zipfile
import unicodedata
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from app.browser_history import admin, csrf, form
from app.db import connect
from app.layout import render_page

router=APIRouter()
MAX_ZIP=100*1024*1024
MAX_EXPANDED=500*1024*1024


def import_zip(content, vault=Path('/vault'), record_origins=False):
    if len(content)>MAX_ZIP: raise ValueError('ZIP exceeds 100 MiB')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members=archive.infolist()
        if len(members)>10000: raise ValueError('ZIP has more than 10,000 entries')
        selected=[];skipped=0;expanded=0;names=set()
        for item in members:
            name=item.filename
            if not item.flag_bits & 0x800:
                try: name=name.encode('cp437').decode('utf-8')
                except UnicodeError: pass
            name=unicodedata.normalize('NFC',name)
            path=PurePosixPath(name)
            if '\\' in name or path.is_absolute() or '..' in path.parts or ':' in name or '\x00' in name:
                raise ValueError('ZIP contains an unsafe path')
            mode=item.external_attr>>16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                raise ValueError('ZIP links or special files are not supported')
            if item.flag_bits&1: raise ValueError('Password-protected ZIP files are not supported')
            if not path.parts or any(part.startswith('.') or part=='__MACOSX' for part in path.parts):
                skipped+=not item.is_dir();continue
            if item.is_dir():continue
            expanded+=item.file_size
            if expanded>MAX_EXPANDED: raise ValueError('Expanded ZIP exceeds 500 MiB')
            selected.append((item,path))
        if not any(path.suffix.lower()=='.md' for _,path in selected):raise ValueError('ZIP must include Markdown notes')
        # A single enclosing vault folder is packaging, not part of its note paths.
        roots={path.parts[0] for _,path in selected}
        strip=len(roots)==1 and all(len(path.parts)>1 for _,path in selected)
        plan=[]
        for item,path in selected:
            relative=Path(*path.parts[1:] if strip else path.parts)
            if str(relative).casefold() in names: raise ValueError('ZIP contains duplicate file paths')
            names.add(str(relative).casefold())
            target=vault/relative
            if target.exists():skipped+=1;continue
            if any(parent.is_symlink() or (parent.exists() and not parent.is_dir()) for parent in [target,*target.parents] if parent==vault or vault in parent.parents):
                raise ValueError('An import path conflicts with an existing file or link')
            plan.append((item,relative))
        # Validate CRCs and size limits before copying any files into the vault.
        with tempfile.TemporaryDirectory(prefix='vault-import-') as temporary:
            staging=Path(temporary)
            total=0
            for item,relative in plan:
                destination=staging/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(item) as source, destination.open('wb') as output:
                    while chunk:=source.read(65536):
                        total+=len(chunk)
                        if total>MAX_EXPANDED:raise ValueError('Expanded ZIP exceeds 500 MiB')
                        output.write(chunk)
            if record_origins:
                # Commit provenance before files become visible to the indexer.
                # Reserved imports stay imported even if their YAML impersonates
                # an app source or their destination is an archive subfolder.
                with connect() as db:
                    for _,relative in plan:
                        db.execute('INSERT INTO library_import_origins(path) VALUES (%s) ON CONFLICT DO NOTHING',(str(relative),))
            created=[]
            try:
                for _,relative in plan:
                    target=vault/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    with target.open('xb') as output:
                        created.append(target)
                        with (staging/relative).open('rb') as source:shutil.copyfileobj(source,output)
                    os.chmod(target,0o644)
            except Exception:
                for target in created:target.unlink(missing_ok=True)
                raise
    return len(created),skipped


def import_page(request, message='', failed=False):
    with connect() as db:enabled=db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()['automation_enabled']
    body='<section class="panel content-panel"><h2>Bring your local Obsidian vault</h2><p>Compress the vault folder into a ZIP on your computer, then upload it here. Notes, folders and attachments are copied into the shared stack vault. Your local vault stays untouched.</p><p>A single outer vault folder is removed automatically. Existing files are skipped. Hidden folders, including .obsidian, .git and .trash, are excluded; desktop settings and plugins are kept separate.</p><p>Limits: 100 MiB ZIP, 500 MiB expanded, 10,000 entries. For larger vaults, use the folder-copy instructions in the README.</p>'
    if message:body+='<p role="'+('alert' if failed else 'status')+'">'+html.escape(message)+'</p>'
    body+=f'<form method="post" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{csrf(request)}"><label for="file">Vault ZIP</label><input id="file" name="file" type="file" accept=".zip" required><button>Import vault</button></form><p><a href="/vault">Open Obsidian desktop →</a></p></section>'
    body+='<section class="panel content-panel"><h2>Automatic archive processing</h2><p>'+('Running' if enabled else 'Paused: no page downloading, history exports or automatic AI notes.')+'</p><p>Importing a vault does not turn automatic processing on. Enable it when you are ready to process browsing data.</p>'
    body+=f'<form method="post" action="/vault/import/automation"><input type="hidden" name="csrf" value="{csrf(request)}"><input type="hidden" name="enabled" value="{0 if enabled else 1}"><button>{"Pause" if enabled else "Enable"} automatic processing</button></form></section>'
    return HTMLResponse(render_page(body,'Import vault','/vault/import'),status_code=400 if failed else 200)


@router.get('/vault/import',dependencies=[Depends(admin)])
def show(request: Request):return import_page(request)


@router.post('/vault/import',dependencies=[Depends(admin)])
async def upload(request: Request):
    content_type=request.headers.get('content-type','')
    if not content_type.startswith('multipart/form-data') or len(content_type)>512 or '\n' in content_type or '\r' in content_type:raise HTTPException(400,'Use the ZIP upload form')
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>MAX_ZIP+65536:raise HTTPException(413,'ZIP exceeds 100 MiB')
    message=BytesParser(policy=policy.default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
    fields={}
    if not message.is_multipart():raise HTTPException(400,'Invalid upload')
    for part in message.iter_parts():
        name=part.get_param('name',header='content-disposition')
        if name in fields or part.is_multipart():raise HTTPException(400,'Duplicate or invalid fields')
        fields[name]=(part.get_payload(decode=True) or b'',part.get_filename())
    if not secrets.compare_digest(fields.get('csrf',(b'',None))[0],csrf(request).encode()):raise HTTPException(403,'Reload the import page and try again')
    content,filename=fields.get('file',(b'',None))
    if not filename or not filename.lower().endswith('.zip'):return import_page(request,'Choose a ZIP file.',True)
    def perform():
        with open('/tmp/forgetfulme-vault-import.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return import_zip(content, record_origins=True)
    try:
        imported,skipped=await run_in_threadpool(perform)
    except (ValueError,zipfile.BadZipFile,RuntimeError,OSError):
        return import_page(request,'Import failed: check the ZIP structure, limits and file paths. No existing files were overwritten.',True)
    return import_page(request,f'Imported {imported:,} files; skipped {skipped:,} existing or hidden files. Open Obsidian to read your notes.')


@router.post('/vault/import/automation',dependencies=[Depends(admin)])
async def automation(request: Request):
    data=await form(request)
    with connect() as db:db.execute('UPDATE vault_controls SET automation_enabled=%s WHERE id=1',(data.get('enabled')==['1'],))
    return RedirectResponse('/vault/import',status_code=303)
