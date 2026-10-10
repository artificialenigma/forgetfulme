"""Frozen synthetic evidence labels; real isolated SQL recall and latency.

Run through scripts/run_isolated_tests.py. Pass --benchmark through its runner
for the separate 1,000/10,000-record SQL baseline. No provider requests occur.
These labels describe invented fixture facts, never real-world research claims.
"""
import argparse
import contextlib
import hashlib
import json
import math
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from app import library
from app.db import connect, require_isolated_test
from app.retrieval import select_evidence,source_key,selection_report,estimate_tokens

require_isolated_test()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--benchmark',action='store_true')
args=parser.parse_args()

CORPUS=[
    ('shoreline','Maldives shoreline observations','The Maldives shoreline fixture surveyed four islands. Shoreline observations exclude monsoon storms; the seawall inspection belongs to the dry season sample.',{'project':'Maldives','archive':'shoreline'}),
    ('budget','Maldives water project budget','The Maldives rainwater budget fixture assumes 2024 sample prices. The budget excludes inflation forecasts and cannot predict future procurement prices.',{'project':'Maldives'}),
    ('water','Island rainwater sensor design','The Maldives rainwater sensor fixture uses ultrasonic tank level sensing. The sensor calibration procedure includes an empty tank reference and a full tank reference.',{'project':'Maldives'}),
    ('tourism','Arrival statistics definitions','In the synthetic Maldives arrivals report, arrivals count border entries rather than unique visitors. Repeat entries remain separate arrival records.',{'project':'Maldives'}),
    ('vblank','Game Boy VBlank rendering','Game Boy rendering waits for VBlank before copying sprite data. The GBDK example calls wait_vbl_done() before move_sprite(0, 16, 24).\n```c\n#include <gb/gb.h>\nvoid main(void) { wait_vbl_done(); move_sprite(0, 16, 24); }\n```',{'project':'Game Boy'}),
    ('banks','Game Boy ROM bank calls','Game Boy BANKED functions switch ROM banks while NONBANKED functions remain in ROM0. The banking fixture avoids saving a pointer across an untracked bank switch.',{'project':'Game Boy'}),
    ('collision','Game Boy collision grid','Game Boy collision detection divides sprite coordinates by eight to find the tile grid cell. The fixture performs grid collision checks before updating sprite positions.',{'project':'Game Boy'}),
    ('tiles','Game Boy signed tile indexes','The Game Boy signed tile index fixture offsets tile identifiers by 128 before loading the alternate tile table. Signed tile indexes differ from sprite identifiers.',{'project':'Game Boy'}),
    ('sleep','ESP32 timer wake comparison','The ESP32 timer wake fixture compares thirty wake cycles. UART reconnect latency belongs to the wake comparison; the test does not measure sleep current.',{'project':'ESP32','archive':'sleep'}),
    ('intercom','ESP32 I2S intercom audio','The ESP32 intercom fixture routes I2S audio into a MAX98357 amplifier. Packet jitter is handled by a bounded audio ring buffer, with oldest frames dropped when full.',{'project':'ESP32'}),
    ('riscv','ESP32 C3 versus S3 architecture','The ESP32 architecture fixture records C3 as RISC-V and S3 as Xtensa. The architecture comparison concerns instruction sets rather than a throughput benchmark.',{'project':'ESP32'}),
    ('backoff','ESP32 reconnect backoff','The ESP32 WiFi reconnect fixture applies exponential backoff capped at sixty seconds. A successful reconnect resets the retry backoff counter.',{'project':'ESP32'}),
    ('adc','ESP32 ADC calibration caveat','The ESP32 ADC fixture calibrates voltage with two reference measurements. Raw ADC counts alone are insufficient to infer voltage across different boards.',{'project':'ESP32'}),
    ('draft','Unreviewed source caveat','The synthetic reef survey summary is an unreviewed AI draft. The draft omits sampling uncertainty, so reef coverage estimates require checking the original survey before reuse.',{'project':'Maldives','archive':'draft'}),
    ('late','Heritage wall field notebook','Opening field observations describe access paths.\n'+('Unrelated background observations are retained in the notebook.\n'*900)+'## Late anchor finding\nThe heritage wall anchor fixture requires a stainless isolation washer to prevent galvanic contact. The isolation washer finding appears after the opening observations.',{'project':'Maldives'}),
    ('crowding','ESP32 wake latency comparison','## Intro\n'+('A long title mentions ESP32 wake latency comparison but this section contains unrelated introductory material.\n'*1000),{'project':'ESP32'}),
    ('wake_evidence','Wake latency experiment notes','The ESP32 wake latency comparison fixture attributes slow UART reconnect to boot log transmission. Disabling boot logs reduces the measured fixture reconnect delay.',{'project':'ESP32'}),
    ('cafe','Café fieldwork notes','Café fieldwork records discuss the port sampling protocol. The port sampling fixture uses duplicate grab samples for each marked station.',{'project':'Maldives','aliases':['Cafe protocol']}),
    ('decomposed','Cafe\u0301 sediment lab','The café sediment fixture dries samples at a fixed temperature before weighing. Sediment weighing excludes the container tare mass.',{'project':'Maldives'}),
    ('dhivehi','ދިވެހި ނޯޓު','ދިވެހި ނޯޓު މާލެ ބަނދަރު ފެން ސާމްޕަލް. The Dhivehi harbour fixture records salinity sampling at marked stations.',{'project':'Maldives'}),
    ('alias','Harbour salinity stations','The alias fixture takes harbour salinity samples during slack tide. Each salinity sample label records station and collection time.',{'project':'Maldives','aliases':['Harbor salinity procedure']}),
    ('duplicate_raw','Source duplication experiment','The ArchiveDupMarker fixture concludes that acoustic logging needs a bounded ring buffer. The acoustic logging measurement records overflow rather than overwriting evidence.',{'project':'ESP32','archive':'duplicate','kind':'raw_source'}),
    ('duplicate_summary','Source duplication experiment','The ArchiveDupMarker fixture concludes that acoustic logging needs a bounded ring buffer. The acoustic logging measurement records overflow rather than overwriting evidence.',{'project':'ESP32','archive':'duplicate','kind':'source'}),
    ('independent_one','Independent duplicate note','The IndependentDupMarker fixture describes a reversible label repair. Reversible label repair preserves the original identifier and an operation history.',{}),
    ('independent_two','Independent duplicate note','The IndependentDupMarker fixture describes a reversible label repair. Reversible label repair preserves the original identifier and an operation history.',{}),
    ('personal','Personal project note','The PrivateCorpusMarker fixture records a personal project deadline. The deadline is synthetic private information used solely for explicit-scope safety tests.',{'path':'Forgetful Me/personal/fixture.md'}),
    ('excluded_raw','Excluded source fixture','The ExcludedCorpusMarker fixture must never reach outbound evidence. Its raw record and summary share the same excluded capture source identity.',{'archive':'excluded','kind':'raw_source'}),
    ('excluded_summary','Excluded source fixture','The ExcludedCorpusMarker fixture must never reach outbound evidence. Its raw record and summary share the same excluded capture source identity.',{'archive':'excluded','kind':'source'}),
    ('answer','Saved answer fixture','The PrivateCorpusMarker answer is a generated derivative from imported evidence. Archive scope cannot inherit consent from the answer note folder.',{'kind':'query','path':'Forgetful Me/wiki/queries/fixture.md'}),
]

# Expected evidence units refer to source/document identities, not chunk order.
# Quotes are frozen labels; changing ranking never changes expected answers.
QUESTIONS=[
    ('shoreline','Which storms are excluded from Maldives shoreline observations?',{'shoreline'},'exclude monsoon storms'),
    ('budget','Which price year is assumed by the Maldives rainwater budget?',{'budget'},'2024 sample prices'),
    ('water','How is the rainwater sensor calibrated?',{'water'},'empty tank reference'),
    ('tourism','Do Maldives arrivals represent unique visitors?',{'tourism'},'rather than unique visitors'),
    ('vblank','Which Game Boy function waits for VBlank?',{'vblank'},'wait_vbl_done()'),
    ('sprite','When is move_sprite called in the Game Boy rendering example?',{'vblank'},'before move_sprite'),
    ('banks','Where do Game Boy NONBANKED functions remain?',{'banks'},'remain in ROM0'),
    ('collision','How does Game Boy collision detection find a tile grid cell?',{'collision'},'coordinates by eight'),
    ('tiles','How are signed Game Boy tile identifiers offset?',{'tiles'},'by 128'),
    ('sleep','How many ESP32 timer wake cycles are compared?',{'sleep'},'thirty wake cycles'),
    ('intercom','Which I2S amplifier does the ESP32 intercom use?',{'intercom'},'MAX98357 amplifier'),
    ('jitter','How does the ESP32 intercom handle packet jitter?',{'intercom'},'bounded audio ring buffer'),
    ('riscv','Which ESP32 chip uses RISC-V architecture?',{'riscv'},'C3 as RISC-V'),
    ('backoff','What is the ESP32 WiFi backoff cap?',{'backoff'},'sixty seconds'),
    ('adc','Can raw ESP32 ADC counts infer voltage across boards?',{'adc'},'insufficient to infer voltage'),
    ('draft','What does the unreviewed reef survey draft omit?',{'draft'},'omits sampling uncertainty'),
    ('late','Which isolation washer prevents galvanic contact in the heritage wall anchor?',{'late'},'stainless isolation washer'),
    ('crowding','What slows UART reconnect in the ESP32 wake latency comparison?',{'wake_evidence'},'boot log transmission'),
    ('cafe','What does the cafe port sampling protocol use?',{'cafe'},'duplicate grab samples'),
    ('decomposed','Does café sediment weighing include container tare mass?',{'decomposed'},'excludes the container tare mass'),
    ('dhivehi','ދިވެހި މާލެ ބަނދަރު ސާމްޕަލް',{'dhivehi'},'މާލެ ބަނދަރު'),
    ('alias','When are harbor salinity procedure samples taken?',{'alias'},'during slack tide'),
    ('duplicates','What does ArchiveDupMarker acoustic logging need?',{'duplicate_raw','duplicate_summary'},'bounded ring buffer'),
    ('independent','What does IndependentDupMarker reversible label repair preserve?',{'independent_one','independent_two'},'original identifier'),
    ('personal','What does PrivateCorpusMarker record?',{'personal'},'personal project deadline'),
]
UNANSWERABLE=[
    ('zero_matches','What is the quantumteleportation calibrationconstant?',False),
    ('missing_measurement','What is the measured ESP32 sleep current in nanoamps?',True),
    ('missing_forecast','What is the 2035 Maldives inflation forecast?',True),
]


def percentile(values,quantile):
    ordered=sorted(values);position=(len(ordered)-1)*quantile
    lower=math.floor(position);upper=math.ceil(position)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(position-lower)


with tempfile.TemporaryDirectory() as temporary,connect() as db:
    vault=Path(temporary);paths={};source_ids={};originals={}
    @contextlib.contextmanager
    def same_connection():yield db
    with db.transaction(force_rollback=True),patch.object(library,'connect',same_connection):
        # Disposable only: clean competing fixture records within this rollback.
        for table in ('library_chunks','library_documents','library_overrides','page_captures','library_import_origins'):
            db.execute('DELETE FROM '+table)
        groups={}
        for key,title,body,options in CORPUS:
            path=options.get('path','corpus/'+key+'.md');paths[key]=path
            metadata={'title':title,'type':options.get('kind','note'),'project':options.get('project',''),'aliases':options.get('aliases',[])}
            if options.get('archive'):
                metadata['managed_by']='forgetfulme';metadata['source_id']=hashlib.sha256(('fixture:'+options['archive']).encode()).hexdigest()
                metadata['source_url']='https://example.invalid/'+options['archive']
                metadata['type']=options.get('kind','raw_source');source_ids[key]=metadata['source_id']
                groups.setdefault(options['archive'],[]).append(key)
            elif options.get('kind')=='query':metadata['managed_by']='forgetfulme'
            note='---\n'+'\n'.join(field+': '+json.dumps(value,ensure_ascii=False) for field,value in metadata.items())+'\n---\n\n# '+title+'\n\n'+body+'\n\nThis synthetic corpus note supplies invented fixture evidence for isolated retrieval evaluation, with retained provenance and source coordinates.\n'
            target=vault/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(note)
            originals[path]=note
            if key=='personal':db.execute('INSERT INTO library_import_origins(path) VALUES (%s)',(path,))
        for group,keys in groups.items():
            raw=next((key for key in keys if next(row[3].get('kind','raw_source') for row in CORPUS if row[0]==key)=='raw_source'),keys[0])
            summary=next((key for key in keys if key!=raw),None)
            db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,wiki_source_path) VALUES (%s,%s,'complete',%s,%s)",(source_ids[raw],'https://example.invalid/'+group,paths[raw],paths[summary] if summary else None))
        db.execute('INSERT INTO library_overrides(path,excluded) VALUES (%s,true)',(paths['excluded_raw'],))
        assert library.scan(vault)==len(CORPUS)
        documents={row['path']:row for row in library.documents()}
        base_count=len(documents)
        assert documents[paths['independent_one']]['document_id']!=documents[paths['independent_two']]['document_id']
        coordinate_chunks={}
        for path,original in originals.items():
            _,body,first=library.frontmatter(original)
            coordinate_chunks[path]=library.chunks(body,first)

        def valid(row):
            source=originals[row['path']]
            coordinates=any(chunk['start_line']==row['start_line'] and chunk['end_line']==row['end_line'] and chunk['content']==row['content'] for chunk in coordinate_chunks[row['path']])
            return row['content_hash']==hashlib.sha256(source.encode()).hexdigest() and coordinates and row['content'] and row['document_id']

        results=[];latencies=[];invalid=0;scope_leaks=0;exclusion_leaks=0
        for name,question,expected,quote in QUESTIONS:
            started=time.perf_counter();candidates=library.search(question,scope='all',for_ai=True,limit=24)
            selected=select_evidence(candidates,max_sections=5)
            latencies.append((time.perf_counter()-started)*1000)
            found=any(row['path'] in {paths[key] for key in expected} and quote in row['content'] for row in selected)
            invalid+=sum(not valid(row) for row in selected)
            scope_leaks+=sum(row['evidence_scope'] not in ('archive','imported') for row in selected)
            exclusion_leaks+=sum(row['source_id']==source_ids['excluded_raw'] for row in selected)
            results.append({'id':name,'recall_at_5':int(found),'paths':[row['path'] for row in selected],'expected_quote_found':found})
        recall=sum(row['recall_at_5'] for row in results)/len(results)

        archive=library.search('PrivateCorpusMarker',scope='archive',for_ai=True,limit=24)
        excluded=library.search('ExcludedCorpusMarker',scope='all',for_ai=True,limit=24)
        scope_leaks+=len(archive);exclusion_leaks+=len(excluded)
        duplicate_selected=select_evidence(library.search('ArchiveDupMarker acoustic logging',scope='all',for_ai=True,limit=24))
        assert len([row for row in duplicate_selected if row['source_id']==source_ids['duplicate_raw']])==1
        assert selection_report(duplicate_selected)['estimated_tokens']<=3500
        assert all(row['path']!=paths['answer'] for row in library.search('PrivateCorpusMarker',for_ai=True))
        project_rows=select_evidence(library.search('rainwater sensor calibration',project='Maldives',for_ai=True))
        assert any(row['path']==paths['water'] for row in project_rows) and all(row['project']=='Maldives' for row in project_rows)
        tiny=select_evidence(library.search('Game Boy',for_ai=True),token_budget=1)
        assert tiny==[]
        unanswerable=[]
        for name,question,related in UNANSWERABLE:
            hits=select_evidence(library.search(question,for_ai=True,limit=24),max_sections=5)
            unanswerable.append({'id':name,'related_hits':len(hits),'expected_answerability':False,'requires_model_abstention':bool(hits)})
            if not related:assert not hits
        report={'corpus':'synthetic-v1','questions':len(QUESTIONS),'notes':base_count,'recall_at_5':recall,
                'invalid_citations':invalid,'scope_violations':scope_leaks,'exclusion_violations':exclusion_leaks,
                'search_selection_ms':{'p50':statistics.median(latencies),'p95':percentile(latencies,.95)},
                'results':results,'unanswerable':unanswerable,
                'abstention_limit':'Related-hit questions require provider abstention; this benchmark makes no model requests and does not claim model abstention accuracy.',
                'environment':{'machine':platform.machine(),'python':platform.python_version(),'container_cpu_count':os.cpu_count()}}
        print('RETRIEVAL_METRICS '+json.dumps(report,ensure_ascii=False),flush=True)
        assert recall>=.8, 'Recall@5 below 80%; inspect frozen expected quotes and measured ranking failures'
        assert invalid==scope_leaks==exclusion_leaks==0

        if args.benchmark:
            # Performance measures SQL retrieval over actual indexed note records,
            # not filesystem traversal. Distractor text is deterministic and local.
            for total in (1000,10000):
                current=db.execute('SELECT count(*) AS n FROM library_documents WHERE present').fetchone()['n']
                added=[]
                for number in range(current,total):
                    path=f'performance/note-{number:05d}.md'
                    topic=('Maldives','ESP32','Game Boy','sediment','harbour')[number%5]
                    content=f'{topic} synthetic background record {number}. This deterministic distractor contains general observations, reversible identifiers, local fixture provenance, and no labelled answer facts.'
                    added.append((path,topic,content))
                with db.cursor().copy('COPY library_documents(path,title,origin,kind,words,fingerprint,content_hash,evidence_scope,match_title) FROM STDIN') as copy:
                    for path,topic,content in added:copy.write_row((path,topic+' background record','imported','note',len(content.split()),'synthetic-v1',hashlib.sha256(content.encode()).hexdigest(),'imported',library.normalize_match_text(topic+' background record')))
                with db.cursor().copy('COPY library_chunks(path,heading,start_line,end_line,content,match_content) FROM STDIN') as copy:
                    for path,topic,content in added:copy.write_row((path,'Background',1,1,content,library.normalize_match_text(content)))
                db.execute('ANALYZE library_documents');db.execute('ANALYZE library_chunks')
                for _,question,_,_ in QUESTIONS[:3]:library.search(question,for_ai=True,limit=24)
                timings=[];performance_hits=0
                for repetition in range(2):
                    for _,question,expected,quote in QUESTIONS:
                        started=time.perf_counter();selected=select_evidence(library.search(question,for_ai=True,limit=24),max_sections=5)
                        timings.append((time.perf_counter()-started)*1000)
                        performance_hits+=int(any(row['path'] in {paths[key] for key in expected} and quote in row['content'] for row in selected))
                actual=db.execute('SELECT count(*) AS n FROM library_documents WHERE present').fetchone()['n']
                assert actual==total
                print('RETRIEVAL_PERFORMANCE '+json.dumps({'notes':actual,'queries':len(timings),'warmup_queries':3,'recall_at_5':performance_hits/len(timings),'p50_ms':statistics.median(timings),'p95_ms':percentile(timings,.95),'min_ms':min(timings),'max_ms':max(timings),'seed':'deterministic-v1','measurement':'SQL library.search plus evidence selection; excludes filesystem scan and provider inference','environment':report['environment']}),flush=True)
        assert all((vault/path).read_text()==original for path,original in originals.items())
print('Frozen recall, scope/exclusion boundaries, evidence diversity, token estimates and source preservation passed')
