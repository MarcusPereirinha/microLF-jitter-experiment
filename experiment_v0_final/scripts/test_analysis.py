#!/usr/bin/env python3
"""Validation regression checks in temporary copies; no test data enters results/."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from analyze import ROOT, inspect_run, summarize

class ValidationTests(unittest.TestCase):
    def setUp(self):
        originals=sorted((ROOT/'results/raw/sanity').rglob('validation.json'))
        self.assertTrue(originals, 'A real baseline is required')
        self.tmp=tempfile.TemporaryDirectory(prefix='microlf-validation-')
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'copy'
        shutil.copytree(originals[0].parent,self.folder)

    def test_baseline_warmup_excluded(self):
        row,delays=inspect_run(self.folder)
        self.assertTrue(row['valid'])
        self.assertEqual(row['sent'],100)
        self.assertEqual(row['received'],100)
        self.assertEqual(len(delays),100)
        self.assertEqual({x['seq'] for x in delays},set(range(10,110)))

    def test_missing_message_invalid(self):
        log=self.folder/'receiver.log'
        log.write_text('\n'.join(x for x in log.read_text().splitlines()
            if not (x.startswith('EVENT,') and ',seq=10,' in x))+'\n')
        row,_=inspect_run(self.folder)
        self.assertFalse(row['valid'])
        self.assertEqual(row['missing'],1)
        self.assertIsNone(row['tardy_rate_pct'])

    def test_duplicate_cannot_replace_missing(self):
        log=self.folder/'receiver.log'
        lines=log.read_text().splitlines()
        duplicate=next(x for x in lines if x.startswith('EVENT,') and ',seq=11,' in x)
        log.write_text('\n'.join(x for x in lines
            if not (x.startswith('EVENT,') and ',seq=10,' in x))+'\n'+duplicate+'\n')
        row,_=inspect_run(self.folder)
        self.assertFalse(row['valid'])
        self.assertEqual(row['received'],100)
        self.assertEqual(row['missing'],1)
        self.assertEqual(row['duplicates'],1)

    def test_unclean_network_invalid(self):
        (self.folder/'tc_cleared.txt').write_text('qdisc netem 7e00: root delay 10ms\n')
        row,_=inspect_run(self.folder)
        self.assertFalse(row['valid'])
        self.assertIn('qdisc_cleanup_not_verified',row['invalid_reasons'])

    def test_failed_process_invalid(self):
        path=self.folder/'metadata.json'
        meta=json.loads(path.read_text()); meta['exit_codes']['receiver']=1
        path.write_text(json.dumps(meta))
        self.assertFalse(inspect_run(self.folder)[0]['valid'])

    def test_summary_deterministic_and_excludes_invalid(self):
        a=[dict(scenario='C0',valid=True,tardy_rate_pct=x) for x in (0,10,20,30,40)]
        a.append(dict(scenario='C0',valid=False,tardy_rate_pct=100))
        s=summarize(a)
        self.assertEqual(s,summarize(a))
        self.assertEqual(s[0]['n_valid'],5)
        self.assertEqual(s[0]['mean'],20)

if __name__=='__main__': unittest.main()
