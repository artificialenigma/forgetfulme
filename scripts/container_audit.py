#!/usr/bin/env python3
"""Audit only this stack's running images; never pull/update/remove services."""
import collections,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];reports=ROOT/'reports'
names=['forgetfulme-web-1','forgetfulme-db-1','forgetfulme-backup-1','forgetfulme-proxy-1','forgetfulme-obsidian-1','forgetfulme-archive-desk-1','crawl4ai']
entries=[];scanned={}
for name in names:
    image=subprocess.run(['docker','inspect','--format','{{.Image}}',name],capture_output=True,text=True,check=True).stdout.strip()
    if image not in scanned:
        output=reports/('container-audit-'+name+'-2026-10-07.sarif.json')
        result=subprocess.run(['docker','scout','cves','--format','sarif','--output',str(output),'local://'+image],capture_output=True,text=True)
        if result.returncode:
            (Path('/tmp')/('forgetfulme-scout-'+name+'.log')).write_text(result.stderr+result.stdout)
            scanned[image]={'image':image,'audit_state':'unavailable','exit_code':result.returncode}
            entries.append({'service':name,**scanned[image]});print(json.dumps(entries[-1]),flush=True);continue
        run=json.loads(output.read_text())['runs'][0];rules=run['tool']['driver'].get('rules',[])
        counts=collections.Counter(rule.get('properties',{}).get('cvssV3_severity','UNSPECIFIED') for rule in rules)
        scanned[image]={'image':image,'report':str(output.relative_to(ROOT)),'advisory_counts':dict(counts),'unique_advisories':len(rules)}
    entries.append({'service':name,**scanned[image]});print(json.dumps(entries[-1]),flush=True)
(reports/'container-audit-summary-2026-10-07.json').write_text(json.dumps({'scanner':'Docker Scout 1.24.0','scope':'exact locally running stack images; no pulls/updates; advisory counts not exploitability determinations','images':entries},indent=2)+'\n')
