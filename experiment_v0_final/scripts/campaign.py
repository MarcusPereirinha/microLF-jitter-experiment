#!/usr/bin/env python3
"""Persist randomized plans and decide whether pilot allows final collection."""
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from analyze import ROOT, inspect_run

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def state():
    return {str(p.relative_to(ROOT)):digest(p) for p in (
        ROOT/'config/experiment.env',ROOT/'src/JitterV0.ulf',
        ROOT/'bin/JitterV0_sender',ROOT/'bin/JitterV0_receiver')}

def load_runs(phase, campaign=None):
    base=ROOT/'results/raw'/phase
    if campaign: base/=campaign
    return [inspect_run(p.parent)[0] for p in sorted(base.rglob('metadata.json'))]

def plan(phase, campaign):
    directory=ROOT/'results/raw'/phase/campaign
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'order.csv'
    if path.exists(): raise SystemExit('Plan already exists; refusing to overwrite')
    rng=random.Random(int(os.environ['MASTER_SEED'])+(1 if phase=='pilot' else 0))
    count=int(os.environ['PILOT_REPETITIONS'] if phase=='pilot' else os.environ['REPETITIONS'])
    rows=[]
    if phase=='final': rows.append(('B0',0,0,0,rng.randrange(1,2**31)))
    for rep in range(1,count+1):
        scenarios=['C0','C1','C2','C3']; rng.shuffle(scenarios)
        for s in scenarios:
            rows.append((s,int(os.environ['BASE_DELAY_MS']),int(s[1])*5,rep,rng.randrange(1,2**31)))
    if phase=='final': rows.append(('B0',0,0,count+1,rng.randrange(1,2**31)))
    with path.open('x',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['scenario','delay','jitter','repetition','seed'])
        writer.writerows(rows)
    print(path)

def pilot_decision(campaign):
    rows=load_runs('pilot',campaign)
    expected=int(os.environ['PILOT_REPETITIONS'])
    complete=all(sum(r['valid'] and r['scenario']==s for r in rows)==expected for s in ('C0','C1','C2','C3')) and len(rows)==4*expected
    rates=[r['tardy_rate_pct'] for r in rows if r['valid']]
    low=float(os.environ['PILOT_LOW_PCT']); high=float(os.environ['PILOT_HIGH_PCT'])
    saturated=bool(rates) and (all(v<=low for v in rates) or all(v>=high for v in rates))
    informative=complete and not saturated
    decision=dict(campaign=campaign,complete=complete,informative=informative,
        all_low=bool(rates) and all(v<=low for v in rates),
        all_high=bool(rates) and all(v>=high for v in rates),
        low_threshold_pct=low,high_threshold_pct=high,hashes=state(),
        runs=[{k:r.get(k) for k in ('run_id','scenario','valid','tardy_rate_pct','invalid_reasons')} for r in rows])
    (ROOT/'logs/pilot_decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    table='\n'.join(f"| {r['scenario']} | {r['valid']} | {r['tardy_rate_pct']} | {r['invalid_reasons']} |" for r in rows)
    text=f'''# Piloto V0 — {campaign}

Uma repetição por cenário, separada da campanha final. Critério previamente
fixado: todos ≤ {low:g}% ou todos ≥ {high:g}% indicam saturação.

| Cenário | Válido | Taxa tardy (%) | Motivo de invalidez |
| --- | --- | ---: | --- |
{table}

Decisão: {'INFORMATIVO — parâmetros congelados; campanha final permitida' if informative else 'PARAR — campanha final não autorizada automaticamente'}.
Não foram ajustados maxwait, período ou atraso-base após observar estes dados.
'''
    (ROOT/'PILOT_REPORT.md').write_text(text)
    if not informative:
        raise SystemExit('Pilot invalid or saturated: stop before calibration/final collection')
    frozen=ROOT/'config/frozen.json'
    if frozen.exists() and json.loads(frozen.read_text())['hashes']!=decision['hashes']:
        raise SystemExit('Existing frozen parameters differ; scientific decision required')
    frozen.write_text(json.dumps(dict(pilot=campaign,hashes=state(),clock_sync='off',
        receiver_timer_ms=int(os.environ['PERIOD_MS'])),indent=2)+'\n')

def assert_frozen():
    frozen=json.loads((ROOT/'config/frozen.json').read_text())
    decision=json.loads((ROOT/'logs/pilot_decision.json').read_text())
    if not decision['informative'] or frozen['hashes']!=state():
        raise SystemExit('Frozen hashes/pilot check failed')

if __name__=='__main__':
    command=sys.argv[1]
    if command=='plan': plan(sys.argv[2],sys.argv[3])
    elif command=='pilot-decision': pilot_decision(sys.argv[2])
    elif command=='check-frozen': assert_frozen()
    elif command=='probe-check':
        rows=load_runs('probe',sys.argv[2])
        good=bool(rows) and rows[-1]['valid'] and rows[-1]['tardy']>0
        (ROOT/'logs/probe_pass.json').write_text(json.dumps(dict(pass_probe=good,runs=[r['run_id'] for r in rows]))+'\n')
        sys.exit(0 if good else 1)
    else: raise SystemExit('Unknown command')
