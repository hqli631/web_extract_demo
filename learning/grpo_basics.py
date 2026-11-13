"""5.1: historical code-agent trajectory plus hypothetical group advantages; no training."""
import argparse
import hashlib
import json
import math
import sys
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/stage5/unit1'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def group_advantages(rewards,epsilon=1e-8):
    if len(rewards)<2 or not all(isinstance(r,(int,float)) and not isinstance(r,bool) and math.isfinite(r) for r in rewards):
        raise ValueError('Provide at least two finite numeric rewards; unknown/null must be resolved or explicitly withheld before grouping.')
    if not math.isfinite(epsilon) or epsilon<=0:
        raise ValueError('epsilon must be positive and finite')
    mean=math.fsum(rewards)/len(rewards)
    variance=math.fsum((r-mean)**2 for r in rewards)/len(rewards)
    std=math.sqrt(variance)
    advantages=[(r-mean)/(std+epsilon) for r in rewards]
    return {'rewards':rewards,'mean':mean,'population_variance':variance,'population_std':std,
            'epsilon':epsilon,'formula':'(r_i - mean(group)) / (population_std(group) + epsilon)',
            'advantages':advantages,'reward_ranking_signal':std>0,
            'origin':'hypothetical same-task candidate trajectories, not measured rollouts'}

def clipped_surrogate(ratio,advantage,clip_epsilon=0.2):
    if not all(math.isfinite(x) for x in [ratio,advantage,clip_epsilon]) or ratio<=0 or not 0<clip_epsilon<1:
        raise ValueError('Invalid probability ratio, advantage or clipping range')
    clipped=max(1-clip_epsilon,min(1+clip_epsilon,ratio))
    return {'probability_ratio':ratio,'advantage':advantage,'clipped_ratio':clipped,
            'unclipped_term':ratio*advantage,'clipped_term':clipped*advantage,
            'surrogate':min(ratio*advantage,clipped*advantage)}

def historical_trajectory():
    paths=['output/stage3/generation/generation_record.json','output/stage3/repair/feedback.json',
           'output/stage3/repair/repair_record.json','output/stage3/repair/results.json']
    generation,feedback,repair,results=[read(ROOT/p) for p in paths]
    patch=next(p for p in repair['patches'] if p['cluster_id']=='sina_shell_v2')
    for name,key in [('learning/generated/sina_v1.py','before_sha256'),('learning/generated/sina_v2.py','after_sha256')]:
        if sha(ROOT/name)!=patch[key]: raise ValueError('Historical code hash mismatch: '+name)
    finding=next(f for f in feedback['findings'] if f['code']=='standalone_byline_in_body')
    page=next(p for p in results['pages'] if p['file']==finding['file'])
    evidence=finding['evidence'][0]
    before=[b for b in page['before']['blocks'] if b['xpath']==evidence['xpath']]
    after=[b for b in page['after']['metadata'] if b['xpath']==evidence['xpath']]
    if len(before)!=1 or len(after)!=1 or before[0]['text']!=after[0]['text'] or after[0]['kind']!='author':
        raise ValueError('Historical byline transition not supported')
    return {'origin':'retrospective reconstruction from saved real code/feedback/results; not an on-policy RL rollout',
            'source_files_sha256':{p:sha(ROOT/p) for p in paths},
            'actor':'current conversation AI generating/repairing Python; no parameter updates',
            'artifact':'learning/generated/sina_v1.py -> sina_v2.py',
            'events':[
              {'step':1,'role':'task_and_observation','summary':'同布局网页任务、输出契约、少量开发样本构成Actor可见上下文。',
               'evidence':{'generation_task_id':generation['task_id'],'samples_per_cluster':generation['generation_inputs_per_cluster']}},
              {'step':2,'role':'action','summary':'Actor生成v1抽取代码；这是动作产物，不是训练参数更新。','code_sha256':patch['before_sha256']},
              {'step':3,'role':'environment_observation','summary':'执行器运行修复页，发现独立署名仍在正文。',
               'evidence':{'file':page['file'],'body_blocks':len(page['before']['blocks']),'record':before[0]}},
              {'step':4,'role':'feedback','summary':'评审给出原文、XPath及要求：仅首段整行署名分流，保留正文中的记者叙述。',
               'evidence':finding},
              {'step':5,'role':'action','summary':'Actor输出v2代码补丁：位置约束加整行署名格式匹配。','code_sha256':patch['after_sha256'],'full_patch':patch['diff']},
              {'step':6,'role':'environment_observation','summary':'回归结果中署名转入作者；正文22块变21块；6篇生成页输出保持不变。',
               'evidence':{'body_before':len(page['before']['blocks']),'body_after':len(page['after']['blocks']),
                           'author_record':after[0],'generation_unchanged':sum(p['role']=='generation' and p['exactly_unchanged'] for p in results['pages'])}}
            ],'numeric_reward':None,'reason_reward_null':'Historical trace did not record a calibrated scalar training reward; do not invent one.'}

def build(rewards):
    mixed=group_advantages(rewards)
    tied=group_advantages([0.8]*len(rewards))
    return {'unit':'5.1','trajectory':historical_trajectory(),'groups':{'input':mixed,'all_equal':tied},
            'clipping_scalar_examples':[clipped_surrogate(1.5,1),clipped_surrogate(0.5,-1),
                                        clipped_surrogate(1.5,-1),clipped_surrogate(0.5,1)],
            'training_status':{'new_model_rollouts':0,'external_model_api_calls':0,'backward_passes':0,
                               'optimizer_steps':0,'parameter_updates':0},
            'limits':['Teaching normalization uses population std and epsilon outside sqrt; framework versions can differ.',
                      'Scalar clipping examples omit token masking, trajectory aggregation and KL; not a complete GRPO implementation.',
                      'Unknown is not zero reward. Existing Rubrics remain uncalibrated; hypothetical rewards are separate.',
                      'All-equal group has no relative reward ranking, but KL/other loss terms may still have gradients.',
                      'Positive advantage means relative to this group, not absolute quality or guaranteed nonzero clipped gradient.']}

def run(rewards):
    result=build(rewards)
    default=rewards==[0.2,0.4,0.8,1.0]
    folder=OUT if default else OUT/'custom'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    lines=['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>5.1 轨迹与GRPO基础</title>',
           '<style>body{font:16px/1.8 system-ui;max-width:1100px;margin:30px auto;padding:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:9px}pre{white-space:pre-wrap;overflow-wrap:anywhere}aside{background:#fff4cd;padding:12px}</style>',
           '<h1>5.1：代码Agent轨迹与组相对优势</h1>',
           '<aside>历史修复轨迹有真实代码和结果，但未记录训练reward。下面数组均是假设奖励，未采样新模型、未训练、未更新参数。第四阶段独立校准仍未完成。</aside>',
           '<h2>一、谁在学习，谁在执行</h2><p>Actor是生成和修复代码的模型；Python/XPath是它生成的产物；执行器和评审提供环境观察。训练要改变Actor的参数，改一个Python文件不是RL。</p>',
           '<h2>二、历史修复轨迹</h2>']
    for event in result['trajectory']['events']:
        lines.append('<details><summary>'+str(event['step'])+' '+event['role']+'：'+escape(event['summary'])+'</summary><pre>'+escape(json.dumps(event,ensure_ascii=False,indent=2))+'</pre></details>')
    lines.append('<p>以上是事后整理的交互轨迹，不是保存了old policy概率的训练rollout；numeric_reward=null。</p><h2>三、假设同任务候选的组内比较</h2>')
    for name,group in result['groups'].items():
        lines+=['<h3>'+name+'</h3><p>mean='+format(group['mean'],'.6f')+'，population_std='+format(group['population_std'],'.6f')+'</p>',
                '<table><tr><th>假设轨迹</th><th>reward</th><th>reward−均值</th><th>advantage</th></tr>']
        for i,(r,a) in enumerate(zip(group['rewards'],group['advantages']),1):
            lines.append(f'<tr><td>T{i}</td><td>{r}</td><td>{r-group["mean"]:.6f}</td><td>{a:.6f}</td></tr>')
        lines.append('</table>')
    lines+=['<p>A=(r−组均值)/(总体标准差+1e−8)。正负表示相对本组，不表示绝对合格。全同分时A=0，只说明reward项没有组内区分信号，不能推出模型已最优或所有训练项都无梯度。</p>',
            '<h2>四、概率比裁剪：可选查看</h2><p>ratio=新policy对同一动作的概率/采样时old policy概率，不是reward的比值。s=min(ratio×A, clip(ratio,0.8,1.2)×A)，作为要最大化的标量项示例；训练loss通常还要取负号并加入其他项。</p>',
            '<pre>'+escape(json.dumps(result['clipping_scalar_examples'],ensure_ascii=False,indent=2))+'</pre>',
            '<p>A=1、ratio=1.5时取1.2；A=−1、ratio=0.5时取−0.8。裁剪不是所有正负情况都切断：另两例分别−1.5、0.5。真正梯度需计算图与参数，本脚本只算数值。KL常约束当前policy与参考policy，参考policy与采样old policy角色不同。</p>',
            '<h2>五、本轮你需要解释</h2><p>1. Actor最终要学会改进什么，是否直接训练XPath？<br>2. 全组都是0.8时，为什么仅靠该组reward不能辨别哪条轨迹更好？</p>',
            '<p>状态s是任务和已有反馈形成的可见上下文；动作a可以是代码或工具调用；观察o来自执行器与评审。rollout是在某个policy下产生的轨迹；policy决定动作概率。终局奖励评价整条结果，credit assignment讨论如何把最终反馈归因给前面的动作。</p>',
            '<h2>执行边界</h2><pre>'+escape(json.dumps(result['training_status'],ensure_ascii=False,indent=2))+'</pre>',
            '<p><a href=results.json>完整数值与轨迹证据</a></p></html>']
    (folder/'index.html').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print('HISTORY: byline body 22 -> 21; moved to author; historical reward=None')
    for name,g in result['groups'].items():
        print(f'{name}: mean={g["mean"]:.6f} std={g["population_std"]:.6f}')
        print('  advantages: '+', '.join(f'{a:.6f}' for a in g['advantages']))
    print('TRAINING: model rollouts=0; parameter updates=0; rewards=hypothetical')
    print(folder/'index.html')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rewards',default='0.2,0.4,0.8,1.0',help='Comma-separated finite hypothetical rewards; custom output kept separate')
    args=parser.parse_args()
    try:
        run([float(v.strip()) for v in args.rewards.split(',')])
    except (ValueError,OverflowError) as exc:
        parser.error(str(exc))
