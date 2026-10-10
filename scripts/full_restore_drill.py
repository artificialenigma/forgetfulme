#!/usr/bin/env python3
"""Rehearse one matched scheduled backup set without altering live resources."""
import argparse,os,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PG='postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24'
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir',required=True,type=Path);parser.add_argument('--image',required=True)
    parser.add_argument('--postgres-image',default=PG)
    args=parser.parse_args();folder=args.backup_dir.resolve()
    if not re.fullmatch(r'(?:postgres:[a-zA-Z0-9._-]+@)?sha256:[a-f0-9]{64}',args.postgres_image):parser.error('Exact PostgreSQL image required')
    if not folder.is_relative_to((ROOT/'backups').resolve()) or not re.fullmatch(r'\d{8}T\d{6}Z',folder.name):parser.error('Choose one scheduled backup directory inside backups/')
    files={name:folder/name for name in ('database.dump','vault.tar.gz','content.tar.gz','obsidian-config.tar.gz')}
    if not all(p.is_file() and not p.is_symlink() for p in files.values()):parser.error('Matched database/vault/content/config set required')
    if not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',args.image):parser.error('Choose a retained tested candidate')
    # Translate the archive offline; private SQL exists only in ignored owner-only storage.
    with tempfile.TemporaryDirectory(dir=ROOT/'backups',prefix='restore-translation-') as directory:
        sql=Path(directory)/'database.sql'
        with files['database.dump'].open('rb') as source,sql.open('wb') as output:
            os.chmod(sql,0o600)
            result=subprocess.run(['docker','run','--rm','-i','--network','none',args.postgres_image,'pg_restore','--no-owner','--no-acl','--file=-'],stdin=source,stdout=output,stderr=subprocess.PIPE)
        if result.returncode:raise RuntimeError('Private database archive conversion failed; output suppressed')
        subprocess.run(['python3',str(ROOT/'scripts/restore_drill.py'),'--database',str(sql),'--vault',str(files['vault.tar.gz']),'--image',args.image,'--postgres-image',args.postgres_image],check=True)
        subprocess.run(['python3',str(ROOT/'scripts/volume_restore_drill.py'),'--content',str(files['content.tar.gz']),'--obsidian-config',str(files['obsidian-config.tar.gz']),'--image',args.image],check=True)
    print('PASS matched scheduled set: forward migrations, retained data/state, restored FastAPI runtime and offline content/config hash/ownership checks. Original credential environment is required for real encrypted-key recovery; Obsidian desktop/third-party runtime rollback is not claimed.')
if __name__=='__main__':main()
