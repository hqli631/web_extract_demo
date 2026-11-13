"""5.1 second experiment: scalar update signals and paired cost examples, no training."""
import json
import math
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/stage5/unit1/update_signals'

def probability_example(old,current,advantage,epsilon=0.2):
    if not all(math.isfinite(x) for x in [old,current,advantage,epsilon]) or not 0<old<=1 or not 0<current<1 or not 0<epsilon<1:
        raise ValueError('Invalid action probabilities, advantage or epsilon')
    ratio=current/old
    clipped=max(1-epsilon,min(1+epsilon,ratio))
    flat=(advantage>0 and ratio>1+epsilon) or (advantage<0 and ratio<1-epsilon)
    kink=(advantage>0 and math.isclose(ratio,1+epsilon,rel_tol=0,abs_tol=1e-12)) or (advantage<0 and math.isclose(ratio,1-epsilon,rel_tol=0,abs_tol=1e-12))
    return {'old_action_probability':old,'current_action_probability':current,'advantage':advantage,
            'ratio':ratio,'unclipped_term':ratio*advantage,'clipped_term':clipped*advantage,
            'surrogate':min(ratio*advantage,clipped*advantage),
            'local_slope_wrt_ratio':None if kink else 0 if flat else advantage,
            'slope_scope':'Only this scalar term away from clip boundaries, not a full model gradient.'}

def categorical_kl(current,reference):
    if len(current)!=len(reference) or not current or any(not math.isfinite(x) or x<=0 for x in current+reference):
        raise ValueError('Require equal-length strictly positive finite distributions')
    if not math.isclose(sum(current),1) or not math.isclose(sum(reference),1):
        raise ValueError('Probabilities must sum to one')
    return sum(p*math.log(p/q) for p,q in zip(current,reference))

def metrics(rows):
    if not rows or len({r['task_id'] for r in rows})!=len(rows):
        raise ValueError('Nonempty unique task ids required')
    if any(r['outcome'] not in {'pass','fail','unknown'} or not isinstance(r['rounds'],int) or r['rounds']<1 or r['cost_units']<0 for r in rows):
        raise ValueError('Invalid outcome, rounds or cost')
    passed=[r for r in rows if r['outcome']=='pass']
    return {'total_tasks':len(rows),'pass':len(passed),
            'fail':sum(r['outcome']=='fail' for r in rows),'unknown':sum(r['outcome']=='unknown' for r in rows),
            'confirmed_pass_rate_all_tasks':len(passed)/len(rows),
            'mean_rounds_all_tasks':sum(r['rounds'] for r in rows)/len(rows),
            'mean_rounds_pass_tasks':sum(r['rounds'] for r in passed)/len(passed) if passed else None,
            'total_cost_units':sum(r['cost_units'] for r in rows),
            'cost_units_per_confirmed_pass':sum(r['cost_units'] for r in rows)/len(passed) if passed else None}

def build():
    outcomes=['pass','pass','fail','unknown']
    def rows(rounds,costs):
        return [dict(task_id=f'T{i}',outcome=o,rounds=n,cost_units=c) for i,(o,n,c) in enumerate(zip(outcomes,rounds,costs),1)]
    baseline=rows([3,2,4,2],[90,60,120,60])
    efficient=rows([1,1,4,2],[30,30,120,60])
    examples=[dict(name=name,**probability_example(old,current,a)) for name,old,current,a in [
        ('positive_below_clip',0.2,0.22,1),('positive_past_clip',0.2,0.3,1),
        ('negative_past_clip',0.2,0.1,-1),('negative_worse_direction',0.2,0.3,-1),
        ('positive_worse_direction',0.2,0.1,1)]]
    return {'unit':'5.1','origin':'Hypothetical numerical teaching cases, not measured policies or real rollouts.',
            'probability_examples':examples,
            'kl_example':{'reference':[0.5,0.5],'current':[0.75,0.25],
                          'KL_current_reference_nats':categorical_kl([0.75,0.25],[0.5,0.5]),
                          'note':'Exact two-action KL only; real LLM training uses token-level implementation-specific estimators. Old rollout policy and reference policy serve distinct roles.'},
            'paired_experiment':{'baseline':{'tasks':baseline,'metrics':metrics(baseline)},
                                 'efficient':{'tasks':efficient,'metrics':metrics(efficient)},
                                 'controls':'Same four tasks, outcome categories and total attempt budget of 4, assumed common evaluation and cost accounting. Rounds include the initial generation/execution attempt; repair-only rounds equal rounds minus one. Categories alone do not prove full quality equivalence. Not all tasks are established initial failures, so 2/4 is not a repair-success rate.',
                                 'conclusion':'Same assumed confirmed pass rate 2/4, all-task rounds 2.75 -> 2.00, pass-task rounds 2.50 -> 1.00, cost 330 -> 240 hypothetical units. Failed/unknown costs remain counted.',
                                 'reward_rule':'No cost penalty formula selected. Unknown has no semantic score; keep it separate. Prefer reducing cost subject to quality and evidence constraints, not buying a higher number by dropping hard tasks.'},
            'training_status':{'new_model_rollouts':0,'backward_passes':0,'optimizer_steps':0,'parameter_updates':0},
            'learner_checks':['C: positive advantage at ratio 1.5 has a flat scalar surrogate; why is stronger probability growth not always rewarded?',
                              'D: same pass/fail/unknown outcomes but lower rounds/cost: what improved, and can we claim accuracy rose?']}

def run():
    result=build()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    lines=['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>5.1更新信号与开销</title>',
           '<style>body{font:16px/1.8 system-ui;max-width:1100px;margin:30px auto;padding:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:9px}pre{white-space:pre-wrap}aside{background:#fff4cd;padding:12px}</style>',
           '<h1>5.1后半：从优势到更新信号，再看质量与开销</h1>',
           '<aside>所有概率、两策略结果及成本均为假设，未训练或调用模型。原真实修复轨迹不补造奖励，第四阶段独立校准缺口保留。</aside>',
           '<h2>一、概率比不是奖励比</h2><p>取同一已采样动作：old概率0.2，current概率0.3，ratio=1.5。这里的动作概率是教学标量；LLM通常计算同一生成token的条件概率比，不能用这一项代表整条轨迹概率或完整训练目标。</p>',
           '<p>最大化s=min(ratio×A,clip(ratio,0.8,1.2)×A)。以下斜率只对ratio这个标量、且在边界之外求局部变化，不是模型权重梯度。</p>',
           '<table><tr><th>例子</th><th>A</th><th>old→current</th><th>ratio</th><th>s</th><th>局部斜率ds/dratio</th></tr>']
    for e in result['probability_examples']:
        lines.append(f'<tr><td>{e["name"]}</td><td>{e["advantage"]}</td><td>{e["old_action_probability"]} → {e["current_action_probability"]}</td><td>{e["ratio"]:.2f}</td><td>{e["surrogate"]:.2f}</td><td>{e["local_slope_wrt_ratio"]}</td></tr>')
    lines+=['</table><p>正优势：提高动作概率通常有利，但ratio越过1.2后，这个项不继续给增加收益。负优势：降低概率通常有利，但ratio低于0.8后，这个项也不继续给增加收益。反方向的变化仍会受惩罚。裁剪不是把概率硬限制在区间内；其他token或KL项仍可能推动共享参数变化。</p>',
            '<h2>二、old policy和reference policy</h2><p>old用于记录采样时的概率，ratio比较current与old；reference提供稳定约束基准，KL衡量current相对它的偏离。两者可能暂时数值相同，职责仍不同。</p>',
            '<p>假设两种动作：reference=[0.5,0.5]，current=[0.75,0.25]，KL(current||reference)='+format(result['kl_example']['KL_current_reference_nats'],'.6f')+' nats。分布相同KL为0；这不是模型准确率。训练目标可含减去β×KL的项，β和具体估计依框架配置，不在此临时调参。</p>',
            '<h2>三、固定四任务比较两种假设策略</h2><p>共同假设：任务/评价/最多4次尝试/成本口径相同。轮数包含首次生成与执行，纯修复轮数=总尝试轮数−1。2/4是全任务确认通过比例，不是已知初始失败任务的修复成功率。成本含失败与unknown任务全部已发生支出，单位不是人民币或真实账单。unknown不被填成0分，也不从分母消失。</p>',
            '<table><tr><th>策略</th><th>pass/fail/unknown</th><th>确认通过/全任务</th><th>全任务平均轮数</th><th>通过任务平均轮数</th><th>总成本</th><th>成本/确认通过</th></tr>']
    for name in ['baseline','efficient']:
        m=result['paired_experiment'][name]['metrics']
        lines.append(f'<tr><td>{name}</td><td>{m["pass"]}/{m["fail"]}/{m["unknown"]}</td><td>{m["confirmed_pass_rate_all_tasks"]:.0%}</td><td>{m["mean_rounds_all_tasks"]:.2f}</td><td>{m["mean_rounds_pass_tasks"]:.2f}</td><td>{m["total_cost_units"]}</td><td>{m["cost_units_per_confirmed_pass"]}</td></tr>')
    lines+=['</table><p>在这个假设对照中，确认通过率仍2/4，减少的是轮数和成本，不能称准确率提高。全任务轮数保留了失败和未知的投入，通过任务轮数回答“成功时要多久”，两个口径都要报。分组标签相同也不能证明全部内容质量完全相等；真实实验还需相同标准的逐题证据与重复测量。</p>',
            '<details><summary>每个任务的原始记录</summary><pre>'+escape(json.dumps(result['paired_experiment'],ensure_ascii=False,indent=2))+'</pre></details>',
            '<h2>四、实际训练还缺什么</h2><p>按policy采样代码/工具轨迹 → 执行与可靠评审 → 计算同任务组优势 → 计算token概率和loss（含mask、裁剪、KL等）→ 反向传播与优化器更新Actor → 固定测试集评估质量/轮数/总开销。本脚本只做数值解释，没有这条训练链的参数更新。</p>',
            '<h2>你的反馈</h2><p>C：正优势A=1、ratio=1.5时，为何这个标量项不再奖励继续提高概率？<br>D：两策略确认通过率相同，轮数和成本下降，应该如何描述收益，能说准确率提高吗？</p>',
            '<p><a href=results.json>完整实验数据</a> / <a href=../index.html>上一组轨迹和优势实验</a></p></html>']
    (OUT/'index.html').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print('CLIP: A=+1 ratio=1.50 surrogate=1.20 local_slope=0')
    print('KL: current||reference = '+format(result['kl_example']['KL_current_reference_nats'],'.6f')+' nats (toy)')
    for name in ['baseline','efficient']:
        m=result['paired_experiment'][name]['metrics']
        print(f'{name}: pass={m["pass"]}/4 fail={m["fail"]} unknown={m["unknown"]}; rounds_all={m["mean_rounds_all_tasks"]:.2f}; rounds_pass={m["mean_rounds_pass_tasks"]:.2f}; cost={m["total_cost_units"]}')
    print('TRAINING: parameter updates=0; hypothetical data only')
    print(OUT/'index.html')

if __name__=='__main__':
    run()
