"""Linux bubblewrap candidate execution; fail closed if isolation unavailable.

Only a minimal Python/lxml runtime and this job are visible. Not a claim of
protection against kernel vulnerabilities; run on a disposable evaluation host.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

WRAPPER = '''import json,runpy,sys
sys.path.insert(0, '/deps')
namespace=runpy.run_path('/work/candidate.py')
result=namespace['extract'](open('/work/input.html','rb').read())
print(json.dumps(result,ensure_ascii=False))
'''

def command(job, deps):
    return ['prlimit','--cpu=8:8','--as=1073741824:1073741824',
      '--nproc=32:32','--fsize=2097152:2097152','--nofile=64:64','--',
      'bwrap','--unshare-all','--die-with-parent','--new-session',
      '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib',
      '--ro-bind','/lib64','/lib64','--ro-bind',str(deps),'/deps',
      '--ro-bind',str(job),'/work','--proc','/proc','--dev','/dev',
      '--tmpfs','/tmp','--chdir','/work','--clearenv',
      '--setenv','PYTHONPATH','/deps','--setenv','LANG','C.UTF-8',
      '--uid','65534','--gid','65534','--cap-drop','ALL',
      '/usr/bin/python3','-B','/work/wrapper.py']

def run(candidate, source, deps, timeout=15):
    if os.name!='posix' or not all(shutil.which(x) for x in ['bwrap','prlimit']):
        raise RuntimeError('Linux bubblewrap and prlimit are required; no unsafe fallback')
    deps=Path(deps).resolve()
    if not (deps/'lxml').is_dir():raise ValueError('isolated lxml runtime missing')
    with tempfile.TemporaryDirectory(prefix='extract-isolation-') as temp:
        job=Path(temp);job.chmod(0o755)
        (job/'candidate.py').write_bytes(Path(candidate).read_bytes())
        (job/'input.html').write_bytes(Path(source).read_bytes())
        (job/'wrapper.py').write_text(WRAPPER,encoding='utf8')
        started=time.monotonic()
        # Files are outside the sandbox mount and bounded by RLIMIT_FSIZE.
        with (job/'stdout').open('w+b') as stdout,(job/'stderr').open('w+b') as stderr:
            try:
                completed=subprocess.run(command(job,deps),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=timeout,check=False)
                stdout.seek(0);stderr.seek(0)
                raw=stdout.read(2097153);err=stderr.read(2097153).decode('utf8','replace')
                if completed.returncode:return dict(status='execution_error',returncode=completed.returncode,stderr=err,seconds=time.monotonic()-started)
                if len(raw)>2097152:raise ValueError('output limit exceeded')
                result=json.loads(raw)
                return dict(status='success',result=result,seconds=time.monotonic()-started,stderr=err)
            except subprocess.TimeoutExpired:
                return dict(status='timeout',seconds=time.monotonic()-started)
            except (ValueError,UnicodeError) as e:
                return dict(status='invalid_json',error=str(e),seconds=time.monotonic()-started)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('source');p.add_argument('--deps',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();report=run(a.candidate,a.source,a.deps)
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(report['status'])
