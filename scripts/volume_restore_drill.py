#!/usr/bin/env python3
"""Restore content/config archives into new offline disposable volumes only."""
import argparse,hashlib,io,json,re,secrets,subprocess,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content',required=True,type=Path)
    parser.add_argument('--obsidian-config',required=True,type=Path)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',args.image):parser.error('Choose a retained tested candidate image')
    for archive in (args.content,args.obsidian_config):
        if not archive.is_file() or not archive.resolve().is_relative_to((ROOT/'backups').resolve()):parser.error('Choose a saved private backup inside repository backups/')
    def run(*parts,input=None):
        result=subprocess.run(['docker',*parts],input=input,capture_output=True)
        if result.returncode:raise RuntimeError('Disposable volume restore failed; private output suppressed')
        return result.stdout
    created=[]
    extraction='''import io,os,sys,tarfile
from pathlib import Path,PurePosixPath
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
 members=archive.getmembers()
 assert len(members)<100000 and sum(m.size for m in members)<2*1024**3
 for member in members:
  path=PurePosixPath(member.name)
  assert not path.is_absolute() and '..' not in path.parts
 members=[m for m in members if m.isfile() or m.isdir()]
 archive.extractall('/restore',members=members,filter='data')
for root,dirs,files in os.walk('/restore'):
 os.chown(root,10001,10001)
 for filename in files:os.chown(Path(root)/filename,10001,10001)
'''
    def restore(label,data):
        expected={};skipped=0
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
            members=archive.getmembers()
            if len(members)>=100000 or sum(m.size for m in members)>=2*1024**3:raise ValueError('Archive exceeds rehearsal budget')
            for member in members:
                path=PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe archive path')
                if member.isfile():
                    name=str(path)
                    if name in expected:raise ValueError('Duplicate archive member')
                    expected[name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                elif not member.isdir():skipped+=1
        volume='forgetfulme-volume-restore-'+secrets.token_hex(6)
        run('volume','create',volume);created.append(volume)
        options=['run','--rm','-i','--network','none','--mount','type=volume,source='+volume+',target=/restore']
        run(*options,'--user','root',args.image,'python','-c',extraction,input=data)
        check="""import hashlib,json,os
from pathlib import Path
expected=json.loads(%r)
root=Path('/restore')
actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
assert actual==expected
assert all(not p.is_symlink() and p.stat().st_uid==10001 and p.stat().st_gid==10001 for p in (root,*root.rglob('*')))
print(len(actual))
""" % json.dumps(expected)
        count=run(*options,'--user','10001:10001',args.image,'python','-',input=check.encode()).decode().strip()
        print(json.dumps({'archive':label,'verified_regular_files':int(count),'uid_gid':10001,'offline':True,'runtime_links_or_special_files_skipped':skipped}))
    try:
        restore('content',args.content.read_bytes())
        restore('obsidian-config',args.obsidian_config.read_bytes())
        # An empty production content archive cannot test nonempty recovery.
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as archive:
            for name,data in [('nested/content.bin',b'Synthetic nonempty content\x00\xff'),('.settings/preferences.json',b'{"synthetic":true}')]:
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o640;archive.addfile(member,io.BytesIO(data))
        restore('synthetic-nonempty',output.getvalue())
        print('PASS offline content/config restore: exact regular-file hashes, readable ownership, nonempty/hidden/binary fixtures; runtime links not restored')
    finally:
        for volume in reversed(created):subprocess.run(['docker','volume','rm',volume],capture_output=True)

if __name__=='__main__':main()
