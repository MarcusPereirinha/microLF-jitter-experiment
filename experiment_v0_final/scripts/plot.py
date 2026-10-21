#!/usr/bin/env python3
"""Regenerate figures exclusively from the processed CSV files."""
import csv
from analyze import ROOT, figures, summarize

def main():
    with (ROOT/'results/processed/results.csv').open() as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        row['valid']=row['valid'].lower()=='true'
        for field in ('configured_jitter_ms','repetition'):
            row[field]=int(row[field])
        for field in ('tardy_rate_pct','p95_delay_ms'):
            row[field]=float(row[field]) if row[field] else None
    if not any(r['valid'] and r['scenario'].startswith('C') for r in rows):
        raise SystemExit('No valid C0–C3 observations: refusing to generate a figure')
    ids={r['run_id'] for r in rows}
    with (ROOT/'results/processed/events.csv').open() as stream:
        delays=[e for e in csv.DictReader(stream) if e['run_id'] in ids]
    for e in delays: e['one_way_delay_ms']=float(e['one_way_delay_ms'])
    figures(rows,summarize(rows),delays)
    print('Figures reconstructed from results.csv and events.csv')

if __name__=='__main__': main()
