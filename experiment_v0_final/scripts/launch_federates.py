#!/usr/bin/env python3
"""Launch real federates, share clock epoch, capture exits and independent streams."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    folder = Path(sys.argv[1])
    cfg = {k.lower(): int(os.environ[k]) for k in (
        'PERIOD_MS', 'MAXWAIT_MS', 'WARMUP_EVENTS', 'MEASURED_EVENTS', 'GRACE_PERIOD_MS')}
    # Both native runtime clocks have the same epoch; clock sync is disabled.
    env = dict(os.environ, LF_CLOCK_EPOCH_NS=str(time.time_ns() - 1_000_000_000))
    meta = dict(cfg, run_id=folder.name, scenario=os.environ['SCENARIO'],
        repetition=int(os.environ['REPETITION']), phase=os.environ['PHASE'],
        campaign_id=os.environ['CAMPAIGN_ID'], seed=int(os.environ['RUN_SEED']),
        base_delay_ms=int(os.environ['RUN_DELAY']),
        configured_jitter_ms=int(os.environ['RUN_JITTER']),
        distribution='normal' if int(os.environ['RUN_JITTER']) else 'none',
        reactor_uc_commit=subprocess.check_output(['git','-C',env['REACTOR_UC_PATH'],'rev-parse','HEAD'],text=True).strip(),
        source_sha256=sha(ROOT/'src/JitterV0.ulf'), config_sha256=sha(ROOT/'config/experiment.env'),
        clock_epoch_ns=int(env['LF_CLOCK_EPOCH_NS']), physical_instrumentation='CLOCK_MONOTONIC',
        started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), exit_codes={})
    procs = {}
    handles = []
    def stop(signum=None, frame=None):
        for proc in procs.values():
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
        if signum is not None:
            raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for role in ('receiver', 'sender'):
            binary = ROOT/'bin'/f'JitterV0_{role}'
            meta[f'{role}_binary_sha256'] = sha(binary)
            stdout = (folder/f'{role}.log').open('x')
            stderr = (folder/f'{role}.stderr.log').open('x')
            handles += [stdout, stderr]
            procs[role] = subprocess.Popen([str(binary)], stdout=stdout, stderr=stderr,
                env=env, start_new_session=True)
        deadline = time.monotonic() + 35
        for role, proc in procs.items():
            meta['exit_codes'][role] = proc.wait(timeout=max(.1, deadline-time.monotonic()))
    except (subprocess.TimeoutExpired, KeyboardInterrupt, Exception) as exc:
        meta['launch_error'] = f'{type(exc).__name__}: {exc}'
        stop()
    finally:
        for role, proc in procs.items():
            if proc.poll() is None:
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            meta['exit_codes'][role] = proc.returncode
        for stream in handles: stream.close()
        meta['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (folder/'metadata.json').write_text(json.dumps(meta, indent=2)+'\n')
    return 0 if meta['exit_codes'] == {'sender':0,'receiver':0} and 'launch_error' not in meta else 1

if __name__ == '__main__':
    sys.exit(main())
