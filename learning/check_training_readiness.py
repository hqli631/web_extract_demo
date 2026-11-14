"""5.2 read-only resource checks; no installs, downloads or training."""
import ctypes
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime,timezone
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/stage5/unit2'
PACKAGES=['torch','transformers','peft','trl','accelerate','ms-swift','bitsandbytes']

def run_probe(command,timeout=15):
    try:
        p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        return {'status':'ok' if p.returncode==0 else 'error','returncode':p.returncode,
                'stdout':p.stdout.strip(),'stderr':p.stderr.strip()[:1500]}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'unavailable','reason':str(exc)}

def physical_memory():
    if sys.platform!='win32': return {'status':'unknown','reason':'Windows memory probe not applicable'}
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),
                  ('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),
                  ('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),
                  ('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),
                  ('ullAvailExtendedVirtual',ctypes.c_ulonglong)]
    record=MEMORYSTATUSEX()
    record.dwLength=ctypes.sizeof(record)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(record)):
        return {'status':'unknown','reason':'GlobalMemoryStatusEx failed'}
    return {'status':'ok','total_bytes':record.ullTotalPhys,'available_bytes':record.ullAvailPhys,
            'meaning':'system RAM, not dedicated GPU VRAM'}

def package_versions():
    versions={}
    for name in PACKAGES:
        try: versions[name]={'status':'installed','version':importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError: versions[name]={'status':'not_installed_in_this_interpreter'}
    return versions

def readiness(packages,torch_probe):
    # Detecting hardware alone never establishes model/reward/data readiness.
    return {
      'training_environment':'not_ready' if packages['torch']['status']!='installed' else 'requires_backend_and_framework_validation',
      'llm_training_backend':'not_verified',
      'model':{'status':'not_selected','checks':['model size and license','local/backend compatibility','memory budget including activations, optimizer and rollout workers']},
      'data':{'status':'requires_new_protocol','reason':'Existing development and previously exposed test pages are historical evidence; define new train/dev/test assignments before a real training experiment.'},
      'reward':{'status':'not_independently_calibrated','reason':'Stage4 citation validity and same-context agreement do not establish reliable training reward.'},
      'budget':{'status':'not_selected','reason':'No paid compute, model download or training authorized/started in this resource check.'},
      'actual_llm_training_completed':False,
      'next_local_action':'Read the report and distinguish SFT examples, reward feedback and actual optimizer updates; select a training route only after resource and reward requirements are explicit.'}

def build():
    packages=package_versions()
    nvidia=shutil.which('nvidia-smi')
    nvidia_probe=run_probe([nvidia,'--query-gpu=name,memory.total,driver_version','--format=csv,noheader']) if nvidia else {'status':'not_found_on_path','meaning':'Not proof that no GPU exists; other vendors/backends require their own checks.'}
    command="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"
    display=run_probe(['powershell.exe','-NoProfile','-NonInteractive','-Command',command]) if sys.platform=='win32' else {'status':'unknown'}
    if display.get('status')=='ok':
        try: display['devices']=json.loads(display['stdout'])
        except json.JSONDecodeError: display['status']='unparsed'
    if packages['torch']['status']=='installed':
        code="import json,torch; print(json.dumps({'torch':torch.__version__,'cuda_available':torch.cuda.is_available(),'cuda_build':torch.version.cuda,'hip_build':getattr(torch.version,'hip',None),'cuda_device_count':torch.cuda.device_count()}))"
        torch_probe=run_probe([sys.executable,'-c',code],timeout=30)
    else: torch_probe={'status':'not_run','reason':'torch is not installed in this Python environment'}
    disk=shutil.disk_usage(ROOT)
    return {'unit':'5.2','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'interpreter':{'executable':sys.executable,'version':platform.python_version(),'platform':platform.platform(),'logical_cpus':os.cpu_count()},
            'system_ram':physical_memory(),'workspace_disk':{'total_bytes':disk.total,'free_bytes':disk.free},
            'packages':packages,'nvidia_smi':nvidia_probe,'display_probe':display,
            'display_memory_warning':'Win32_VideoController.AdapterRAM can be inaccurate/truncated/shared for integrated graphics; it does not establish dedicated/free training VRAM.',
            'torch_backend':torch_probe,'readiness':readiness(packages,torch_probe),
            'side_effects':{'packages_installed':0,'models_downloaded':0,'network_calls':0,'training_updates':0}}

def run():
    result=build()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'resource_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    observed=OUT/'observed_display.json'
    supplemental=json.loads(observed.read_text(encoding='utf-8')) if observed.exists() else None
    parts=['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>5.2训练条件检查</title>',
           '<style>body{font:16px/1.8 system-ui;max-width:1100px;margin:30px auto;padding:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:9px}</style>',
           '<h1>5.2第一步：训练条件检查</h1>',
           '<p>这是本地只读检查，不安装训练包、不下载模型、不启动训练。权限不足的探测记为unknown/error，不能当作没有硬件。</p>',
           '<h2>当前Python与依赖</h2><pre>'+escape(json.dumps({'interpreter':result['interpreter'],'packages':result['packages']},ensure_ascii=False,indent=2))+'</pre>',
           '<h2>显卡、内存与后端</h2><pre>'+escape(json.dumps({k:result[k] for k in ['system_ram','workspace_disk','nvidia_smi','display_probe','torch_backend','display_memory_warning']},ensure_ascii=False,indent=2))+'</pre>']
    if supplemental:
        parts.append('<h3>当前对话先前授权的只读显卡查询记录</h3><pre>'+escape(json.dumps(supplemental,ensure_ascii=False,indent=2))+'</pre><p>该记录不是每次重跑后的实时显卡探测，也不证明后端兼容。</p>')
    parts+=['<h2>训练准备清单</h2><pre>'+escape(json.dumps(result['readiness'],ensure_ascii=False,indent=2))+'</pre>',
            '<h2>三件不同的事</h2><table><tr><th>方式</th><th>输入信号</th><th>实际更新什么</th></tr><tr><td>提示/代码迭代</td><td>当前上下文、错误反馈</td><td>修改上下文或代码产物，模型权重不变</td></tr><tr><td>SFT</td><td>任务与目标输出示例</td><td>优化器更新模型可训练参数</td></tr><tr><td>GRPO等RL</td><td>同任务采样轨迹、执行与奖励</td><td>根据策略目标更新Actor可训练参数</td></tr></table>',
            '<p>LoRA是参数高效微调方式：通常冻结基础权重、训练低秩适配器。它不是reward算法，可与合适的SFT/RL流程结合。只看权重大小不能估计训练总显存，还需激活、梯度、优化器和rollout等内存。</p>',
            '<h2>下一步如何选择</h2><p>当前未验证本机可用的LLM训练后端，训练依赖、模型与新数据协议未准备，reward独立校准未完成。先完成训练数据与流程学习；如选择外部GPU，再确定设备、预算和后端。资源不足时按原计划明确训练未完成，继续5.3有限RSI工程，不将规则补丁冒充RL。</p>',
            '<h2>本轮请解释</h2><p>E：显卡被检测到、磁盘空间充足，为什么仍不能直接宣布可以训练Qwen？<br>F：SFT使用目标示例，GRPO使用采样轨迹与奖励，这两种训练信号有什么区别？</p>',
            '<p><a href=resource_report.json>本次资源报告</a> · <a href=observed_display.json>已观察显卡记录</a></p></html>']
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8',newline='\n')
    print('PYTHON: '+result['interpreter']['version'])
    print('TORCH: '+result['packages']['torch']['status'])
    print('DISPLAY PROBE: '+result['display_probe']['status']+'; a failed query does not prove no GPU')
    print('TRAINING: environment='+result['readiness']['training_environment']+'; backend/model/data/reward/budget need verification')
    print('SIDE EFFECTS: installs=0; model downloads=0; training updates=0')
    print(OUT/'index.html')

if __name__=='__main__':
    run()
