"""Read-only crawler inventory; never collect credentials, arguments or note content."""
import argparse
import json
import subprocess
from pathlib import Path

PROBE = '''import importlib.metadata as m,json,os,pathlib,sys
versions={}
for name in ["crawl4ai","nltk","PyJWT","anyio","litellm","unclecode-litellm","sentence-transformers"]:
 try: versions[name]=m.version(name)
 except m.PackageNotFoundError: versions[name]=None
executables=set()
for path in pathlib.Path("/proc").glob("[0-9]*/exe"):
 try: executables.add(os.readlink(path))
 except OSError: pass
print(json.dumps({"python":sys.version.split()[0],"executable":sys.executable,"distributions":versions,"process_executables":sorted(executables)}))'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', default='crawl4ai')
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def command(*parts):
        return subprocess.check_output(['docker', *parts], text=True, timeout=30)
    image = command('inspect', '--format', '{{.Image}}', args.container).strip()
    audit = json.loads(args.audit.read_text())
    if image != audit['image']:
        raise SystemExit('Refusing classification: audit image does not match container')
    inventory = json.loads(command('exec', args.container, 'python', '-c', PROBE))
    classified = []
    for rule in audit['rules']:
        locations = rule['locations']
        metadata_only = bool(locations) and all(p.startswith('/tmp/project/') for p in locations)
        classified.append({**rule, 'location_class': 'historical_project_metadata' if metadata_only else 'installed_component', 'reachability_verdict': 'not established'})
    result = {'image': image, 'inventory': inventory, 'critical_rules': classified,
              'metadata_only_rules': sum(r['location_class'] == 'historical_project_metadata' for r in classified),
              'installed_component_rules': sum(r['location_class'] == 'installed_component' for r in classified),
              'limitations': 'Location classification is not exploitability proof. Renamed/forked package code requires separate review. No scanner rules suppressed.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['image','metadata_only_rules','installed_component_rules']}))


if __name__ == '__main__':
    main()
