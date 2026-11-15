"""Harmless denial controls for the candidate evaluation environment."""
import json,tempfile
from pathlib import Path
from isolate_extract import run
def main():
    deps='/tmp/web-extract-runtime/deps'
    controls={
      'non_root':"import os\ndef extract(data):return {'uid':os.getuid()}",
      'network_denied':"import socket\ndef extract(data):\n s=socket.socket();s.settimeout(1)\n try:s.connect(('1.1.1.1',443));return {'denied':False}\n except OSError:return {'denied':True}",
      'host_home_hidden':"import os\ndef extract(data):return {'hidden':not os.path.exists('/root/web_extract_sft_20261115')}",
      'input_read_only':"def extract(data):\n try:open('/work/input.html','wb').write(b'x');return {'denied':False}\n except OSError:return {'denied':True}",
      'cpu_limit':"def extract(data):\n while True:pass",
    }
    evidence=[]
    with tempfile.TemporaryDirectory() as d:
        p=Path(d);(p/'input.html').write_text('<p>control</p>')
        for name,code in controls.items():
            (p/'candidate.py').write_text(code)
            result=run(p/'candidate.py',p/'input.html',deps)
            expected=({'uid':65534} if name=='non_root' else {'hidden':True} if name=='host_home_hidden' else {'denied':True})
            passed=result['status']=='execution_error' if name=='cpu_limit' else result.get('result')==expected
            evidence.append(dict(control=name,passed=passed,outcome=result))
    path=Path(__file__).resolve().parents[1]/'output/stage5/multitask/isolation_checks.json'
    path.write_text(json.dumps(dict(checks=evidence,passed=all(x['passed'] for x in evidence),limits='Denial controls do not establish protection against kernel escapes.'),indent=2),encoding='utf8')
    print('ISOLATION CONTROLS',all(x['passed'] for x in evidence))
if __name__=='__main__':main()
