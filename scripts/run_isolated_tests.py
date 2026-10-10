#!/usr/bin/env python3
"""Build and test the checkout in a disposable, disconnected Compose project."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS = [
    'harness_guard_test.py', 'library_test.py', 'metadata_test.py',
    'evidence_scope_test.py', 'source_revision_test.py',
    'ingestion_policy_test.py', 'pdf_extract_test.py', 'retrieval_benchmark_test.py', 'publication_test.py',
    'wiki_test.py', 'page_scraper_test.py', 'crawl4ai_client_test.py',
    'vault_import_test.py', 'ai_provider_test.py', 'obsidian_export_test.py',
    'library_smoke_test.py', 'workflow_test.py', 'worker_fairness_test.py', 'index_restart_test.py', 'ui_shell_test.py',
]
SERVICES = {'test-db', 'test-init', 'test-web', 'test-runner'}
VOLUMES = {'test_database', 'test_vault', 'test_content'}


def source_manifest():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / 'app').rglob('*'))
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'
    }


def validate_config(config, project, run_id, image):
    """Reject edits that would attach fixtures to a production or host resource."""
    if not re.fullmatch(r'forgetfulme-tests-[a-f0-9]{12}', project):
        raise ValueError('Unexpected test project identity')
    if config.get('name') != project or set(config.get('services', {})) != SERVICES:
        raise ValueError('Only the generated disposable services are allowed')
    networks = config.get('networks', {})
    if set(networks) != {'isolated'}:
        raise ValueError('Only the isolated test network is allowed')
    network = networks['isolated']
    if not network.get('internal') or network.get('external') or network.get('name') != project + '_isolated':
        raise ValueError('The test network must be private and project-scoped')
    volumes = config.get('volumes', {})
    if set(volumes) != VOLUMES:
        raise ValueError('Unexpected fixture volumes')
    for name, spec in volumes.items():
        if spec.get('external') or spec.get('driver_opts') or spec.get('name') != project + '_' + name:
            raise ValueError('Fixture volumes must be disposable and project-scoped')
    for name, spec in config['services'].items():
        if set(spec.get('networks', {})) != {'isolated'}:
            raise ValueError('A fixture service has access outside the isolated network')
        for prohibited in ('ports', 'extra_hosts', 'network_mode', 'privileged', 'devices', 'volumes_from', 'env_file'):
            if spec.get(prohibited):
                raise ValueError('Unsafe fixture service option: ' + prohibited)
        for volume in spec.get('volumes', []):
            if volume.get('type') != 'volume' or volume.get('source') not in VOLUMES:
                raise ValueError('Host and external mounts are forbidden in fixtures')
        environment = spec.get('environment', {})
        if name == 'test-db':
            if spec.get('image') != 'postgres:17-alpine':
                raise ValueError('Unexpected fixture database image')
            if environment != {
                'POSTGRES_DB': 'forgetfulme_test', 'POSTGRES_USER': 'test_runner',
                'POSTGRES_PASSWORD': 'disposable-fixture-password',
            }:
                raise ValueError('Fixture database must use only synthetic settings')
        else:
            expected = {
                'FM_TEST_ISOLATED': '1', 'FM_TEST_RUN_ID': run_id,
                'PGHOST': 'test-db', 'PGDATABASE': 'forgetfulme_test', 'PGUSER': 'test_runner',
                'POSTGRES_PASSWORD': 'disposable-fixture-password',
                'ADMIN_USER': 'fixture-admin', 'ADMIN_PASSWORD': 'disposable-fixture-admin',
                'OLLAMA_URL': 'http://provider-disabled.invalid:11434', 'OLLAMA_MODEL': 'fixture-model',
                'FM_TEST_BASE_URL': 'http://test-web:8000',
            }
            if spec.get('image') != image or environment != expected:
                raise ValueError('Fixture app settings must be isolated and synthetic')
            build = spec.get('build', {})
            if Path(build.get('context', '')).resolve() != ROOT or build.get('dockerfile', 'Dockerfile') != 'Dockerfile':
                raise ValueError('Unexpected fixture build context')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-config', action='store_true', help='Validate isolation without starting containers')
    parser.add_argument('--benchmark', action='store_true', help='Also run 1k/10k retrieval latency fixtures when the benchmark script is selected')
    parser.add_argument('--tests', nargs='+', default=DEFAULT_TESTS, metavar='SCRIPT.py')
    args = parser.parse_args()
    paths = []
    for name in args.tests:
        path = ROOT / 'scripts' / name
        if Path(name).name != name or not name.endswith('_test.py') or not path.is_file():
            parser.error('Tests must be existing scripts/*_test.py files: ' + name)
        paths.append(path)
    run_id = secrets.token_hex(6)
    project = 'forgetfulme-tests-' + run_id
    image = 'forgetfulme-test:' + run_id
    environment = dict(os.environ, FM_TEST_RUN_ID=run_id, FM_TEST_IMAGE=image)
    # Explicit file/project and an empty env file avoid inheriting .env/Compose configuration.
    for key in tuple(environment):
        if key.startswith('COMPOSE_'):
            environment.pop(key)
    command = ['docker', 'compose', '--project-name', project, '--env-file', '/dev/null',
               '-f', str(ROOT / 'compose.test.yaml')]

    def run(*parts, input=None, capture=False):
        return subprocess.run(command + list(parts), cwd=ROOT, env=environment, input=input,
                              text=True, check=True, capture_output=capture)

    rendered = run('config', '--format', 'json', capture=True)
    validate_config(json.loads(rendered.stdout), project, run_id, image)
    print('Validated isolation: synthetic database/settings, private network, disposable volumes, no host ports or mounts.', flush=True)
    if args.check_config:
        return 0
    print('Disposable project: ' + project, flush=True)
    print('Candidate image: ' + image, flush=True)
    manifest = source_manifest()
    build_inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ("Dockerfile","requirements.txt","requirements.lock","compose.test.yaml","compose.yaml")}
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    fixtures = {path: path.read_text() for path in paths}
    print('App source fingerprint: ' + fingerprint, flush=True)
    cleanup_needed = False
    try:
        run('build', '--build-arg', 'FM_APP_FINGERPRINT='+fingerprint, 'test-runner')
        identity = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                                  env=environment, text=True, check=True, capture_output=True)
        print('Built image ID: ' + identity.stdout.strip(), flush=True)
        cleanup_needed = True
        run('up', '-d', '--wait', '--wait-timeout', '90', 'test-db')
        run('run', '--rm', '-T', '--no-deps', 'test-init')
        for repetition in (1, 2):
            print(f'Applying idempotent migrations ({repetition}/2).', flush=True)
            run('run', '--rm', '-T', '--no-deps', 'test-runner', 'python', '-m', 'app.init_db')
        # Never start inference/capture workers in this harness.
        setup = '''from app.db import connect, require_isolated_test
require_isolated_test()
with connect() as db:
    db.execute("UPDATE vault_controls SET automation_enabled=false WHERE id=1")
    db.execute("INSERT INTO ai_settings(id,provider,base_url,model,enabled) VALUES (1,'ollama','http://provider-disabled.invalid:11434','fixture-model',false) ON CONFLICT(id) DO UPDATE SET enabled=false")
print('Disposable database identity and vault marker verified; automation and AI paused.')
'''
        run('run', '--rm', '-T', '--no-deps', 'test-runner', 'python', '-', input=setup)
        verify = '''import hashlib, json
from pathlib import Path
expected = json.loads(%r)
actual = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(Path('app').rglob('*')) if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}
assert actual == expected, 'Candidate app code differs from the source snapshot; rebuild before testing'
print('All candidate app files match the recorded source snapshot.')
''' % json.dumps(manifest)
        run('run', '--rm', '-T', '--no-deps', 'test-runner', 'python', '-', input=verify)
        run('up', '-d', '--wait', '--wait-timeout', '90', 'test-web')
        for path in paths:
            print('Running fixture: ' + path.name, flush=True)
            script_args = ['--benchmark'] if args.benchmark and path.name == 'retrieval_benchmark_test.py' else []
            run('run', '--rm', '-T', '--no-deps', 'test-runner', 'python', '-', *script_args, input=fixtures[path])
        if source_manifest() != manifest or any(path.read_text() != fixtures[path] for path in paths) or any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest for name,digest in build_inputs.items()):
            raise ValueError('Source or fixture scripts changed while tests ran; rebuild and repeat the delivery checks')
        print(f'PASS: {len(paths)} fixture scripts; migrations repeated; no production resources attached.', flush=True)
        return 0
    finally:
        if cleanup_needed:
            print('Removing only disposable project ' + project + ' and its fixture volumes.', flush=True)
            run('down', '--volumes', '--remove-orphans', '--timeout', '10')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError) as error:
        print('Isolated tests failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
