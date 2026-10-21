#!/usr/bin/env python3
"""Independent acceptance audit: reconstruct every final row and statistical summary."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from analyze import ROOT, FIELDS, inspect_run, summarize
from campaign import assert_frozen, digest

def audit():
    assert_frozen()
    campaign=(ROOT/'logs/completed_final.txt').read_text().strip()
    folder=ROOT/'results/raw/final'/campaign
    plan=list(csv.DictReader((folder/'order.csv').open()))
    runs=[inspect_run(p.parent)[0] for p in sorted(folder.rglob('metadata.json'))]
    expected={(p['scenario'],int(p['repetition'])):p for p in plan}
    actual={(r['scenario'],r['repetition']):r for r in runs}
    assert len(runs)==len(actual)==len(expected)==22, 'Expected 20 factor runs plus 2 infrastructure baselines'
    assert set(actual)==set(expected)
    for key,row in actual.items():
        p=expected[key]
        assert row['valid'], (row['run_id'],row['invalid_reasons'])
        assert row['seed']==int(p['seed'])
        assert row['base_delay_ms']==int(p['delay'])
        assert row['configured_jitter_ms']==int(p['jitter'])
        assert row['sent']==row['received']==100
        assert row['normal']+row['tardy']==100
        assert row['missing']==row['duplicates']==row['sent_duplicates']==0
        assert row['source_sha256']==digest(ROOT/'src/JitterV0.ulf')
        assert row['config_sha256']==digest(ROOT/'config/experiment.env')
        assert row['receiver_binary_sha256']==digest(ROOT/'bin/JitterV0_receiver')
        assert row['sender_binary_sha256']==digest(ROOT/'bin/JitterV0_sender')
    scientific=[r for r in runs if r['scenario'].startswith('C')]
    assert all(sum(r['scenario']==s for r in scientific)==5 for s in ('C0','C1','C2','C3'))
    csv_rows=list(csv.DictReader((ROOT/'results/processed/results.csv').open()))
    assert len(csv_rows)==len(runs)
    by_id={r['run_id']:r for r in runs}
    for row in csv_rows:
        r=by_id[row['run_id']]
        for field in FIELDS:
            expected_value='' if r.get(field) is None else str(r[field])
            assert row[field]==expected_value,(row['run_id'],field,row[field],expected_value)
    saved_summary=json.loads((ROOT/'results/processed/summary.json').read_text())
    assert saved_summary==summarize(runs), 'Bootstrap summary not reconstructible'
    q=json.loads(subprocess.check_output(['tc','-j','qdisc','show','dev','lo'],text=True))
    assert q and all(x.get('kind')=='noqueue' for x in q), 'Loopback not clean'
    runtime=Path(__import__('os').environ['REACTOR_UC_PATH'])
    for p in (runtime,runtime/'external/nanopb'):
        assert not subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True).strip(), 'Vendor checkout changed'
    for name in ('tardy_rate_vs_jitter.png','delay_distribution_by_scenario.png','p95_delay_vs_jitter.png'):
        assert (ROOT/'results/figures'/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert (ROOT/'results/figures/tardy_rate_vs_jitter.pdf').read_bytes().startswith(b'%PDF')
    result=dict(pass_audit=True,campaign=campaign,final_factor_runs_valid=20,
        baselines_valid=2,source_and_binaries_frozen=True,csv_reconstructed=True,
        bootstrap_reconstructed=True,vendor_unchanged=True,loopback_clean=True,
        scenarios=saved_summary)
    (ROOT/'logs/final_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

def manifest():
    files=[]
    for base in ('src','scripts','config','results'):
        files += [p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT/x for x in ('README.md','REPORT.md','PILOT_REPORT.md','EXPERIMENT_SPEC.md','requirements.txt')]
    files += [ROOT/'logs'/x for x in ('final_audit.json','toolchain_versions.txt','python_freeze.txt','status.txt',
        'environment.txt','netem_probe.json','api_evidence.txt','pilot_decision.json','analysis_tests.txt')
        if (ROOT/'logs'/x).exists()]
    lines=[f'{digest(p)}  {p.relative_to(ROOT).as_posix()}' for p in sorted(files)]
    (ROOT/'logs/artifact_manifest.sha256').write_text('\n'.join(lines)+'\n')
    print(f'Manifest: {len(lines)} artifacts')

if __name__=='__main__':
    if '--manifest' in sys.argv: manifest()
    else: audit()
