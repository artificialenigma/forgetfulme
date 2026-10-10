#!/usr/bin/env python3
"""Restore saved DB/vault backups into generated internal Docker resources only.

No production mounts, published ports, outbound network or provider workers.
Does not restore over the live stack. All generated resources are removed.
"""
import argparse,json,re,secrets,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,type=Path)
    parser.add_argument('--vault',required=True,type=Path)
    parser.add_argument('--image',required=True)
    parser.add_argument('--postgres-image',default='postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24',help='Exact local PostgreSQL image for isolated restore')
    args=parser.parse_args()
    if not re.fullmatch(r'(?:postgres:[a-zA-Z0-9._-]+@)?sha256:[a-f0-9]{64}',args.postgres_image):parser.error('PostgreSQL image must be an exact digest or local image ID')
    for path in (args.database,args.vault):
        if not path.is_file() or not path.resolve().is_relative_to((ROOT/'backups').resolve()):parser.error('Choose a saved backup inside repository backups/')
    if not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',args.image):parser.error('Choose a retained tested candidate image')
    name='forgetfulme-restore-'+secrets.token_hex(6);network=name+'-net';volumes=[name+'-database',name+'-vault'];created=[];container=False
    def run(*parts,input=None):
        result=subprocess.run(['docker',*parts],input=input,capture_output=True)
        if result.returncode:raise RuntimeError('Disposable restore command failed: '+parts[0])
        return result.stdout
    try:
        run('network','create','--internal',network);created.append(('network',network))
        for volume in volumes:run('volume','create',volume);created.append(('volume',volume))
        run('run','-d','--name',name,'--network',network,'--mount','type=volume,source='+volumes[0]+',target=/var/lib/postgresql/data','-e','POSTGRES_DB=forgetfulme','-e','POSTGRES_USER=forgetfulme','-e','POSTGRES_PASSWORD=disposable-restore-only',args.postgres_image);container=True
        for attempt in range(30):
            ready=subprocess.run(['docker','exec',name,'pg_isready','-U','forgetfulme','-d','forgetfulme'],capture_output=True)
            if ready.returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Disposable restore database not ready')
        run('exec','-i',name,'psql','-v','ON_ERROR_STOP=1','-U','forgetfulme','-d','forgetfulme',input=args.database.read_bytes())
        # Restore only regular files/directories into the new empty volume.
        extraction='''import io,os,sys,tarfile
from pathlib import Path
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
 members=archive.getmembers()
 assert len(members)<100000 and sum(m.size for m in members)<2*1024**3
 assert all(m.isdir() or m.isfile() for m in members)
 archive.extractall('/vault',members=members,filter='data')
for root,dirs,files in os.walk('/vault'):
 os.chown(root,10001,10001)
 for filename in files:os.chown(Path(root)/filename,10001,10001)
'''
        run('run','--rm','-i','--network','none','--user','root','--mount','type=volume,source='+volumes[1]+',target=/vault',args.image,'python','-c',extraction,input=args.vault.read_bytes())
        environment=['-e','PGHOST='+name,'-e','PGDATABASE=forgetfulme','-e','PGUSER=forgetfulme','-e','POSTGRES_PASSWORD=disposable-restore-only','-e','ADMIN_PASSWORD=synthetic-restore-no-provider']
        app=['run','--rm','-i','--network',network,'--mount','type=volume,source='+volumes[1]+',target=/vault',*environment,args.image,'python','-']
        verification='''from pathlib import Path
import json,hashlib
from app.db import connect
from app.init_db import SCHEMA
with connect() as db:
 candidates=['browser_visits','page_captures','ai_settings','vault_controls','library_documents','library_overrides','library_connections','library_question_status','wiki_questions','library_index_jobs']
 tables=[table for table in candidates if db.execute('SELECT to_regclass(%s) AS name',(table,)).fetchone()['name']]
 before={table:db.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in tables}
 queries=[]
 for table in tables:
  columns=[r['column_name'] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(table,)).fetchall()]
  # Compare original columns only: migrations may add new fields/defaults.
  names=','.join('"'+column+'"' for column in columns)
  queries.append('SELECT '+names+' FROM '+table)
 digest=lambda query:hashlib.sha256(json.dumps(sorted((json.dumps(row,sort_keys=True,default=str) for row in db.execute(query).fetchall())),sort_keys=True).encode()).hexdigest()
 preserved=[digest(query) for query in queries]
 before_settings=db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()
 before_ai=db.execute('SELECT enabled FROM ai_settings WHERE id=1').fetchone()
 db.execute(SCHEMA);db.execute(SCHEMA)
 after={table:db.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in tables}
 assert before==after
 assert preserved==[digest(query) for query in queries]
 assert db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()==before_settings
 assert db.execute('SELECT enabled FROM ai_settings WHERE id=1').fetchone()==before_ai
 assert db.execute("SELECT to_regclass('library_pdf_jobs') AS name").fetchone()['name']
 notes=sum(1 for path in Path('/vault').rglob('*') if path.is_file())
 assert notes>0
 print(json.dumps({'restored_files':notes,'preserved_rows':after,'migrations':2,'settings_preserved':True,'pdf_schema_available':True,'identities_preferences_connections_questions_citations_unchanged':True}))
'''
        result=run(*app,input=verification.encode()).decode().strip()
        print('PASS disposable DB/vault restore: '+result)
        seed = 'from pathlib import Path\nimport hashlib,json,uuid\nfrom app.db import connect\nfrom app.pdf_extract import EXTRACTOR_VERSION\nroot=Path(\'/vault/Restore fixtures\');root.mkdir(exist_ok=True)\nfor name in (\'source.md\',\'answer.md\'):root.joinpath(name).write_text(\'# Synthetic restore fixture\\nSynthetic evidence.\\n\')\nroot.joinpath(\'selected.pdf\').write_bytes(b\'%PDF-1.7\\nSynthetic restore bytes\')\nwith connect() as db:\n    identities={}\n    for name in (\'source.md\',\'answer.md\',\'selected.pdf\'):\n        path=\'Restore fixtures/\'+name;digest=hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest()\n        identities[name]=db.execute("INSERT INTO library_documents(path,title,origin,kind,fingerprint,content_hash,evidence_scope) VALUES (%s,\'Synthetic restore\',\'imported\',\'note\',\'fixture\',%s,\'imported\') RETURNING document_id",(path,digest)).fetchone()[\'document_id\']\n    db.execute("INSERT INTO library_overrides(path,excluded,reviewed,project) VALUES (\'Restore fixtures/source.md\',true,true,\'Synthetic restore\')")\n    db.execute("INSERT INTO library_connections(source,target) VALUES (\'Restore fixtures/source.md\',\'Restore fixtures/answer.md\')")\n    db.execute("INSERT INTO library_question_status(id,state,answer_path) VALUES (%s,\'resolved\',\'Restore fixtures/answer.md\')",(hashlib.sha256(uuid.uuid4().bytes).hexdigest(),))\n    citations=[dict(id=\'synthetic-source\',document_id=str(identities[\'source.md\']),revision=hashlib.sha256(root.joinpath(\'source.md\').read_bytes()).hexdigest(),excerpt=\'Synthetic evidence.\',path=\'Restore fixtures/source.md\',start_line=2,end_line=2)]\n    db.execute("INSERT INTO wiki_questions(id,question,state,answer,citations,scope) VALUES (%s,\'Synthetic restore question\',\'complete\',\'Synthetic answer\',%s::jsonb,\'all\')",(uuid.uuid4(),json.dumps(citations)))\n    pdf=identities[\'selected.pdf\'];revision=hashlib.sha256(root.joinpath(\'selected.pdf\').read_bytes()).hexdigest()\n    db.execute(\'INSERT INTO library_pdf_selections(document_id) VALUES (%s)\',(pdf,))\n    db.execute("INSERT INTO library_pdf_jobs(document_id,revision,state,extractor_version,pages_total,pages_with_text) VALUES (%s,%s,\'succeeded\',%s,1,1)",(pdf,revision,EXTRACTOR_VERSION))\n    db.execute(\'INSERT INTO library_pdf_pages(document_id,revision,page,text,text_hash,words,extractor_version) VALUES (%s,%s,1,%s,%s,2,%s)\',(pdf,revision,\'Synthetic evidence.\',hashlib.sha256(b\'Synthetic evidence.\').hexdigest(),EXTRACTOR_VERSION))\n    tables=[\'library_documents\',\'library_overrides\',\'library_connections\',\'library_question_status\',\'wiki_questions\',\'library_index_jobs\',\'library_pdf_selections\',\'library_pdf_jobs\',\'library_pdf_pages\']\n    db.execute(\'CREATE TABLE fm_restore_expected(name text PRIMARY KEY,digest text NOT NULL)\')\n    for table in tables:\n        rows=db.execute(\'SELECT to_jsonb(t) AS value FROM \'+table+\' t ORDER BY to_jsonb(t)::text\').fetchall()\n        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()\n        db.execute(\'INSERT INTO fm_restore_expected(name,digest) VALUES (%s,%s)\',(table,digest))\nprint(\'Synthetic nonempty restore state prepared\')\n'
        run(*app,input=seed.encode())
        credential_fixture="""from app.db import connect
from app.ai_provider import secret_key
with connect() as db:
 db.execute(\"INSERT INTO ai_settings(id,provider,base_url,model,enabled,api_key) VALUES (1,'ollama','http://provider-disabled.invalid','synthetic',false,pgp_sym_encrypt(%s,%s)) ON CONFLICT(id) DO UPDATE SET api_key=excluded.api_key\",('synthetic-recovery-key',secret_key()))
print('Synthetic encrypted credential fixture prepared without provider requests')
"""
        run(*app,input=credential_fixture.encode())
        run('exec',name,'createdb','-U','forgetfulme','restore_fixture')
        dump=run('exec',name,'pg_dump','--no-owner','-U','forgetfulme','forgetfulme')
        run('exec','-i',name,'psql','-v','ON_ERROR_STOP=1','-U','forgetfulme','-d','restore_fixture',input=dump)
        restored=list(app)
        restored[restored.index('PGDATABASE=forgetfulme')]='PGDATABASE=restore_fixture'
        check = """import hashlib,json
from app.db import connect
with connect() as db:
 expected=db.execute('SELECT * FROM fm_restore_expected ORDER BY name').fetchall()
 for entry in expected:
  table=entry['name']
  assert table in {'library_documents','library_overrides','library_connections','library_question_status','wiki_questions','library_index_jobs','library_pdf_selections','library_pdf_jobs','library_pdf_pages'}
  rows=db.execute('SELECT to_jsonb(t) AS value FROM '+table+' t ORDER BY to_jsonb(t)::text').fetchall()
  assert hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()==entry['digest']
 from app.ai_provider import secret_key
 assert db.execute('SELECT pgp_sym_decrypt(api_key,%s) AS value FROM ai_settings WHERE id=1',(secret_key(),)).fetchone()['value']=='synthetic-recovery-key'
 from psycopg import Error
 try:
  with db.transaction():db.execute('SELECT pgp_sym_decrypt(api_key,%s) FROM ai_settings WHERE id=1',('incorrect-synthetic-key',)).fetchone()
 except Error:pass
 else:raise AssertionError('Incorrect encryption environment accepted')
 print('PASS synthetic encrypted-key recovery: matching credential environment succeeds; wrong environment rejected')
 print('PASS nonempty restore roundtrip: identities, review/project/exclusions, connections, resolved questions, citation excerpts/revisions, scan jobs and selected PDF jobs/pages')
"""
        print(run(*restored,input=check.encode()).decode().strip())
        # Start only the restored FastAPI app: no worker, host ports or provider calls.
        web=name+'-web'
        try:
            run('run','-d','--name',web,'--network',network,'--mount','type=volume,source='+volumes[1]+',target=/vault',*environment,'-e','ADMIN_USER=restore-fixture',args.image,'uvicorn','app.main:app','--host','0.0.0.0','--port','8000')
            probe="""import base64,os,time,urllib.request
base='http://127.0.0.1:8000'
for attempt in range(30):
 try:
  urllib.request.urlopen(base+'/health/live',timeout=2).close();break
 except Exception:time.sleep(.2)
else:raise RuntimeError('Restored web did not start')
from app.auth import COOKIE,issue_session
headers={'Cookie':COOKIE+'='+issue_session()}
for path in ['/library','/library/projects','/library/health','/library/questions','/library/pdf','/library/jobs']:
 request=urllib.request.Request(base+path,headers=headers)
 with urllib.request.urlopen(request,timeout=30) as response:
  assert response.status==200 and response.url==base+path
  assert '<main id="main">' in response.read().decode()
print('PASS restored FastAPI runtime: six authenticated library/recovery pages; no provider workers or published ports')
"""
            print(run('exec','-i',web,'python','-',input=probe.encode()).decode().strip())
        finally:subprocess.run(['docker','rm','-f',web],capture_output=True)


    finally:
        if container:subprocess.run(['docker','rm','-f',name],capture_output=True)
        for kind,resource in reversed(created):subprocess.run(['docker',kind,'rm',resource],capture_output=True)


if __name__=='__main__':main()
