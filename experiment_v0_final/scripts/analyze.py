#!/usr/bin/env python3
"""Reconstruct measurements from raw logs; never substitute generated observations."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as stats
import sys

ROOT = Path(__file__).resolve().parents[1]

def read_json(path):
    return json.loads(path.read_text())

def percentile(values, p):
    a = sorted(values)
    if not a: return None
    index = (len(a)-1)*p/100
    lo = int(index)
    return a[lo] + (a[min(lo+1,len(a)-1)]-a[lo])*(index-lo)

def records(path):
    events, summaries = [], []
    for line in path.read_text(errors='strict').splitlines():
        if line.startswith('EVENT,'):
            parts = line.split(',')
            item = dict(part.split('=',1) for part in parts[2:])
            events.append(dict(kind=parts[1], **{k:int(v) for k,v in item.items()}))
        elif line.startswith('SUMMARY,'):
            summaries.append(dict(part.split('=',1) for part in line.split(',')[1:]))
    return events, summaries

def inspect_run(folder):
    meta = read_json(folder/'metadata.json')
    row = dict(meta)
    errors = []
    delays = []
    w, n = meta['warmup_events'], meta['measured_events']
    expected = set(range(w,w+n))
    try:
        sent, ss = records(folder/'sender.log')
        recv, rs = records(folder/'receiver.log')
        if any(e['kind'] != 'SENT' for e in sent): errors.append('unexpected_sender_event')
        if any(e['kind'] not in ('NORMAL','TARDY') for e in recv): errors.append('unexpected_receiver_event')
        if any(e['seq'] not in range(w+n) for e in sent+recv): errors.append('out_of_range_seq')
        sm = [e for e in sent if e['seq'] in expected]
        rm = [e for e in recv if e['seq'] in expected]
        sc, rc = Counter(e['seq'] for e in sm), Counter(e['seq'] for e in rm)
        normal = sum(e['kind']=='NORMAL' for e in rm)
        tardy = sum(e['kind']=='TARDY' for e in rm)
        missing = len(expected-set(rc))
        duplicates = sum(max(0,c-1) for c in rc.values())
        sent_duplicates = sum(max(0,c-1) for c in sc.values())
        row.update(sent=len(sm), received=len(rm), normal=normal, tardy=tardy,
                   missing=missing, duplicates=duplicates, sent_duplicates=sent_duplicates,
                   missing_sent=len(expected-set(sc)))
        if set(sc)!=expected or len(sm)!=n or sent_duplicates: errors.append('sent_measured_not_exact')
        if set(rc)!=expected or len(rm)!=n or duplicates: errors.append('received_measured_not_exact')
        if len(sent)!=w+n: errors.append('sent_total_not_exact')
        if len(ss)!=1 or len(rs)!=1: errors.append('summary_count')
        elif (int(ss[0]['sent_total'])!=len(sent) or int(ss[0]['sent_measured'])!=len(sm)
              or int(rs[0]['normal'])!=normal or int(rs[0]['tardy'])!=tardy
              or int(rs[0]['warmup'])!=sum(e['seq']<w for e in recv)):
            errors.append('summary_mismatch')
        for e in rm:
            actual = (e['logical_ns'],e['microstep'])
            intended = (e['intended_ns'],e['intended_microstep'])
            if (e['kind']=='TARDY') != (actual>intended) or actual<intended:
                errors.append('handler_tag_mismatch')
                break
        sender_map = {e['seq']:e for e in sm if sc[e['seq']]==1}
        for e in sorted(rm,key=lambda e:e['seq']):
            if rc[e['seq']]!=1 or e['seq'] not in sender_map: continue
            s = sender_map[e['seq']]
            if (s['logical_ns'],s['microstep']) != (e['intended_ns'],e['intended_microstep']):
                errors.append('intended_send_tag_mismatch')
            delay = (e['mono_ns']-s['mono_ns'])/1e6
            if delay<0: errors.append('negative_monotonic_delay')
            delays.append(dict(run_id=meta['run_id'],phase=meta['phase'],campaign_id=meta['campaign_id'],
                scenario=meta['scenario'],seq=e['seq'],type=e['kind'],one_way_delay_ms=delay,
                sender_mono_ns=s['mono_ns'],receiver_mono_ns=e['mono_ns'],
                intended_ns=e['intended_ns'],logical_ns=e['logical_ns']))
        qdisc = read_json(folder/'tc_applied.json')
        kind = 'noqueue' if meta['scenario']=='B0' else 'netem'
        if not qdisc or any(q.get('kind')!=kind for q in qdisc): errors.append('wrong_qdisc_kind')
        if kind=='netem':
            options=qdisc[0].get('options',{})
            timing=options.get('delay',{})
            if not math.isclose(timing.get('delay',-1),meta['base_delay_ms']/1000,abs_tol=1e-9):
                errors.append('netem_actual_delay_mismatch')
            if not math.isclose(timing.get('jitter',0),meta['configured_jitter_ms']/1000,abs_tol=1e-9):
                errors.append('netem_actual_jitter_mismatch')
            if options.get('seed')!=meta['seed']:
                errors.append('netem_actual_seed_mismatch')
            actual_text = (folder/'tc_applied.txt').read_text()
            if 'delay '+str(meta['base_delay_ms'])+'ms' not in actual_text:
                errors.append('netem_delay_not_verified')
            command = (folder/'tc_command.txt').read_text()
            if meta['configured_jitter_ms'] and 'distribution normal' not in command:
                errors.append('netem_distribution_not_verified')
        cleared = (folder/'tc_cleared.txt').read_text()
        if 'qdisc noqueue ' not in cleared or 'qdisc netem ' in cleared: errors.append('qdisc_cleanup_not_verified')
        if read_json(folder/'infrastructure.json')['exit_code']!=0: errors.append('infrastructure_exit')
        if meta['exit_codes']!={'sender':0,'receiver':0} or 'launch_error' in meta: errors.append('process_exit')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        errors.append(f'parse_error:{exc}')
    row['valid'] = not errors
    row['invalid_reasons'] = ';'.join(sorted(set(errors)))
    row['tardy_rate_pct'] = 100*row['tardy']/n if row['valid'] else None
    if delays:
        d = [e['one_way_delay_ms'] for e in delays]
        ipdv = [abs(d[i]-d[i-1]) for i in range(1,len(d))]
        row.update(mean_delay_ms=stats.mean(d),delay_std_ms=stats.stdev(d) if len(d)>1 else None,
            p50_delay_ms=percentile(d,50),p95_delay_ms=percentile(d,95),p99_delay_ms=percentile(d,99),
            ipdv_mean_ms=stats.mean(ipdv) if ipdv else None,
            ipdv_p95_ms=percentile(ipdv,95),ipdv_p99_ms=percentile(ipdv,99))
    return row, delays

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def summarize(rows, seed=20261020):
    rng=random.Random(seed)
    output=[]
    for scenario in ('C0','C1','C2','C3'):
        runs=[r for r in rows if r['scenario']==scenario and r['valid']]
        a=[r['tardy_rate_pct'] for r in runs]
        item=dict(scenario=scenario,configured_jitter_ms=int(scenario[1])*5,n_valid=len(a))
        if a:
            means=[stats.mean(rng.choices(a,k=len(a))) for _ in range(10000)]
            item.update(mean=stats.mean(a),median=stats.median(a),
                std=stats.stdev(a) if len(a)>1 else None,min=min(a),max=max(a),
                ci95_low=percentile(means,2.5),ci95_high=percentile(means,97.5))
        output.append(item)
    return output

def figures(rows, summary, delays):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    target=ROOT/'results/figures'
    target.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(6.4,4))
    for s in summary:
        if not s['n_valid']: continue
        x=s['configured_jitter_ms']; m=s['mean']
        a=[r['tardy_rate_pct'] for r in rows if r['valid'] and r['scenario']==s['scenario']]
        offsets=[(i-(len(a)-1)/2)*.12 for i in range(len(a))]
        ax.scatter([x+d for d in offsets],a,s=24,alpha=.55,color='0.45',label='Runs individuais' if x==0 else None)
        ax.errorbar([x],[m],yerr=[[m-s['ci95_low']],[s['ci95_high']-m]],fmt='o',color='#185a8d',capsize=4,
            label='Média e IC 95% bootstrap por run' if x==0 else None)
    ax.set(xlabel='Jitter configurado no NetEm (ms)',ylabel='Mensagens tardy/STP (%)',
        title='Tardy/STP sob variabilidade da comunicação',xticks=[0,5,10,15],ylim=(-3,103))
    ax.legend(fontsize=8)
    fig.tight_layout()
    for suffix in ('png','pdf'): fig.savefig(target/f'tardy_rate_vs_jitter.{suffix}',dpi=300)
    plt.close(fig)
    by_scenario=[[e['one_way_delay_ms'] for e in delays if e['scenario']==s and any(r['run_id']==e['run_id'] and r['valid'] for r in rows)] for s in ('C0','C1','C2','C3')]
    if all(by_scenario):
        fig,ax=plt.subplots(figsize=(6.4,4))
        ax.boxplot(by_scenario,tick_labels=['C0','C1','C2','C3'],showfliers=True)
        ax.set(xlabel='Cenário',ylabel='Envio → reação de entrada (ms)',title='Atraso observado na aplicação')
        fig.tight_layout(); fig.savefig(target/'delay_distribution_by_scenario.png',dpi=300); plt.close(fig)
        fig,ax=plt.subplots(figsize=(6.4,4))
        for r in rows:
            if r['valid'] and r['scenario'].startswith('C'):
                ax.scatter(r['configured_jitter_ms'],r['p95_delay_ms'],color='#185a8d',alpha=.65,s=30)
        ax.set(xlabel='Jitter configurado no NetEm (ms)',ylabel='P95 envio → reação (ms)',title='P95 do atraso da aplicação por run',xticks=[0,5,10,15])
        fig.tight_layout(); fig.savefig(target/'p95_delay_vs_jitter.png',dpi=300); plt.close(fig)

FIELDS='run_id campaign_id phase scenario repetition base_delay_ms configured_jitter_ms distribution maxwait_ms period_ms warmup_events measured_events sent received normal tardy missing duplicates missing_sent sent_duplicates valid invalid_reasons tardy_rate_pct mean_delay_ms delay_std_ms p50_delay_ms p95_delay_ms p99_delay_ms ipdv_mean_ms ipdv_p95_ms ipdv_p99_ms seed source_sha256 config_sha256'.split()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--validate',type=Path)
    parser.add_argument('--campaign')
    args=parser.parse_args()
    if args.validate:
        row,_=inspect_run(args.validate)
        (args.validate/'validation.json').write_text(json.dumps({k:row.get(k) for k in FIELDS},indent=2)+'\n')
        print(json.dumps({k:row.get(k) for k in ('run_id','valid','sent','normal','tardy','missing','duplicates','invalid_reasons')}))
        return 0 if row['valid'] else 2
    rows=[]; delays=[]
    for meta in sorted((ROOT/'results/raw').rglob('metadata.json')):
        row,d=inspect_run(meta.parent)
        rows.append(row); delays+=d
    processed=ROOT/'results/processed'
    write_csv(processed/'all_runs.csv',rows,FIELDS)
    finals=[r for r in rows if r['phase']=='final' and (not args.campaign or r['campaign_id']==args.campaign)]
    campaigns={r['campaign_id'] for r in finals}
    if len(campaigns)>1: raise SystemExit('Select one final campaign with --campaign; refusing to pool campaigns')
    write_csv(processed/'results.csv',finals,FIELDS)
    write_csv(processed/'events.csv',delays,list(delays[0]) if delays else ['run_id','seq','one_way_delay_ms'])
    summary=summarize(finals)
    write_csv(processed/'summary.csv',summary,'scenario configured_jitter_ms n_valid mean median std min max ci95_low ci95_high'.split())
    (processed/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if finals and any(r['valid'] for r in finals):
        # Plot in a separate process: its only data inputs are the written CSVs.
        import subprocess
        subprocess.run([sys.executable,str(ROOT/'scripts/plot.py')],check=True)
    print(json.dumps(summary,indent=2))
    if not finals: print('No final runs; no experimental figures generated.')
    return 0

if __name__=='__main__': sys.exit(main())
