"""Build a six-section report from actual terminal records, never desired counts."""
from pathlib import Path
import datetime,hashlib,json,shutil,sys
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c');OLD=Path('/data/group4/20261009-021611-codex-415484ce');W=B/'work'/R.name
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
count=int(sys.argv[1]);evaluations=[json.loads((R/'analysis'/f'wave{i}-evaluation.json').read_text()) for i in range(1,count+1)]
rows=[r for e in evaluations for r in e['rows']];assert len(rows)==4*count and all('success' in r for r in rows)
byid={r['id']:r for r in rows};tracking=json.loads((R/'analysis'/f'tracking-{count}.json').read_text());poses={r['id']:r for r in tracking['rows']}
assert len(poses)==len(rows)
for r in rows:
    assert all(r['pretreatment_prefix_identical'].values()) and all(r['frozen_reference_arrays_identical'].values())
    assert r['geometry_identity'] and sha(R/'out'/r['id']/'result.json')==r['source_result_sha']
    if r['whole_baseline_arrays_identical'] is not None:assert all(r['whole_baseline_arrays_identical'].values())
paired=[]
for prefix,source in [('A','A000'),('B','B000'),('C','C000'),('D','D000'),('B080','B080'),('C020','C020'),('D020','D020'),('B051','B051')]:
    base,best=byid[prefix+'_base'],byid[prefix+'_combo3'];bm,im=base['metrics']['HOLD'],best['metrics']['HOLD']
    plan=json.loads((OLD/'out'/('plan_'+source)/'plan.json').read_text())
    paired.append({'source':source,'baseline_success':base['success'],'improved_success':best['success'],
                   'wrist_rms_before_mm':bm['wrist_detrended_rms_mm'],'wrist_rms_after_mm':im['wrist_detrended_rms_mm'],
                   'wrist_rms_reduction_pct':100*(1-im['wrist_detrended_rms_mm']/bm['wrist_detrended_rms_mm']),
                   'arm_velocity_before':bm['arm_velocity_rms_rad_s'],'arm_velocity_after':im['arm_velocity_rms_rad_s'],
                   'arm_velocity_reduction_pct':100*(1-im['arm_velocity_rms_rad_s']/bm['arm_velocity_rms_rad_s']),
                   'slip_before_mm':base['local_slip_mm'],'slip_after_mm':best['local_slip_mm'],
                   'goal_error_before_mm':poses[base['id']]['hold_wrist_goal_error_mean_norm_mm'],
                   'goal_error_after_mm':poses[best['id']]['hold_wrist_goal_error_mean_norm_mm'],
                   'rotation_rms_before_deg':poses[base['id']]['hold_wrist_orientation_detrended_component_rms_deg'],
                   'rotation_rms_after_deg':poses[best['id']]['hold_wrist_orientation_detrended_component_rms_deg'],
                   'trial_config':plan['trial_config'],'root_x_m':plan.get('root_x',0)})
videos=json.loads((R/'configs/render25clip-done.json').read_text())['rows'];assert len(videos)==4 and all(v['rc']==0 and v['replay']['decode_verified'] for v in videos)
for v in videos:assert sha(R/'out'/v['id']/'replay25clip/grasp-25fps.mp4')==v['replay']['video_sha']
success_cases=[p for p in paired if p['baseline_success']]
assert len(success_cases)==7 and all(p['improved_success'] for p in success_cases)
summary={'task':R.name,'physics_trial_count':len(rows),'physics_success_count':sum(r['success'] for r in rows),
         'physics_failure_ids':[r['id'] for r in rows if not r['success']],
         'matched_source_cases':len(paired),'all_prefix_exact':True,'all_exogenous_references_exact':True,'all_original_baselines_bitwise_exact':True,
         'improved_successful_source_cases':len(success_cases),'matched_cases':paired,'valid_clip_videos':4,
         'recommended_profile':{'arm_target_tau_s':0,'arm_damping_scale':3,'servo_gain':.03,'change_start_s':42},
         'runtime_stamp':evaluations[0]['runtime_stamp']|{'model_sha':{r['id']:r['runtime_stamp']['model_sha'] for r in rows}},'source_evaluation_sha':{f'wave{i}':sha(R/'analysis'/f'wave{i}-evaluation.json') for i in range(1,count+1)},
         'tracking_source_sha':sha(R/'analysis'/f'tracking-{count}.json'),'report_builder_sha':sha(__file__),
         'scope':'paired case studies with iterative development, not a new100/300-run generalization estimate, realrobot test or fullARDY end-to-end validation'}
with (R/'analysis/summary.json').open('x') as f:json.dump(summary,f,indent=2,ensure_ascii=False)
stamp=summary['runtime_stamp'];lo=min(p['wrist_rms_reduction_pct'] for p in success_cases);hi=max(p['wrist_rms_reduction_pct'] for p in success_cases)
report=f'''# 成功抓取手部抖动排查与改进报告

任务：{R.name}；生成：{datetime.datetime.now().astimezone().isoformat()}。

## 一、结论

已完成{len(rows)}次真实物理试验；推荐闭手开始后将右臂额外阻尼从2提高到3、手腕位置/方向统一修正增益从0.10降到0.03，禁用60ms目标低通。
7个原成功场景全部保持原v2成功标准，HOLD手腕平移抖动指标降低{lo:.1f}%–{hi:.1f}%；原失败B051的重试成功，但平移RMS略增，不能宣称所有指标改善。
主要现象是整手随右臂/腕运动，非手指自身快速振荡；仍有方向摆动、轻微跟踪偏差与抓取前接触，未声称实机或完整Track4完成。

## 二、操作步骤

1. 先完整读取当前AGENTS.md、README及告示，并重新测磁盘/内存/压力。登记新任务；10-09凌晨已归档批次只读，未覆盖成功案例、别人的源码、模型或环境。
2. 审查7个旧病例的原始状态、力矩、手指/手臂速度和控制源码。旧视频6.25fps有采样跳动；不能用肉眼将其直接判成高频物理抖动。
3. 冻结每个旧病例实际执行的body/hand/wrist参考数组、初态、场景及闭手目标；不重新规划接近动作。保持成功门、接触几何、摩擦、重力、物体质量和执行器上限。
4. 在50Hz SONIC策略、1kHz PD/动力学上增加200Hz状态/力矩/目标/接触诊断记录。先跑A000单因素：原版、60ms右臂目标低通、阻尼3、腕修正0.03。
5. 在A000组合测试阻尼3/4与修正0.03/0.01，再测试34s提前启用。所有失败保留；不因结果差而放宽门槛。
6. 在B000/C000/D000与B080/C020/D020复核默认组合；另重试原失败B051。逐数组检查处理前状态、原外部输入完全一致；8个原版基线完整轨迹也逐数组相等。
7. 追加方向修正分量增益0.06的探索试验：对位置与方向的正规方程右端分开求解，仍只修正SONIC输入参考，不以IK输出直接替代电机目标。其适用性看下方全量表，未悄悄设为默认。
8. 独立按记录qpos重新做FK，分析保持目标位置误差、方向摆幅、角速度和力矩饱和。输出25fps真实状态回放，无插值、无虚构运动、无重新积分；关键段34–53s，包含末段伸臂、闭手、试抬、抬升、保持。
9. 所有大文件放本任务/data目录；报告、源码清单及关键分析同时归档至本机与服务器。调度偏差/依赖缺失/渲染首试中止独立登记；不删失败或不完整文件。

## 三、实测证据

运行环境：MuJoCo3.2.7，dt=0.001s；200Hz观测间隔0.005s；50Hz策略。版本/解释器/模型/场景生成器/SONIC库SHA均在每条数值记录的runtime_stamp中。

### 对旧成功案例的定位

A000基线HOLD右臂速度RMS={byid['A_base']['metrics']['HOLD']['arm_velocity_rms_rad_s']:.6f}rad/s，右手指={byid['A_base']['metrics']['HOLD']['finger_velocity_rms_rad_s']:.6f}rad/s。该比较是分组平均，不代表每个关节或所有阶段均如此。
同初态、同外部轨迹的单因素与组合试验支持：现有手臂PD阻尼和腕参考反馈修正的耦合是可调改善点。50Hz阶跃只是候选因素；60ms低通试验失败说明不能据此将根因简单等同为“更新慢”。
HOLD主要右臂关节谱峰在约1–3Hz，参考修正、策略输出与自由底座共同运动；不能据此证明唯一根因。指端接触载荷有变化，个别病例手指微动指标反增，仍须保留这个结果。

### 同一病例改前改后（默认组合）

平移RMS：对50.5–53s的500个200Hz样本做线性去趋势，再在时间与XYZ三个分量上计算RMS；不是三维向量模长RMS，也不是最大偏移。改善率=(1−改后/改前)×100%；负值表示更差。

| 原病例 | 原版→组合结果 | 手腕平移RMS mm（前→后） | 降低 | 右臂速度RMS rad/s（前→后） | 手内最大滑移 mm（前→后） |
|---|---|---|---:|---|---|
'''
for p in paired:
    report+=f"| {p['source']} | {'成功' if p['baseline_success'] else '失败'}→{'成功' if p['improved_success'] else '失败'} | {p['wrist_rms_before_mm']:.3f}→{p['wrist_rms_after_mm']:.3f} | {p['wrist_rms_reduction_pct']:.1f}% | {p['arm_velocity_before']:.4f}→{p['arm_velocity_after']:.4f} | {p['slip_before_mm']:.3f}→{p['slip_after_mm']:.3f} |\n"
report+='''
这8个病例是有目的选取的诊断/回归集合，不是8个全新随机抽样。A000用于选择参数；其他数据也参与后续调优，不能把8/8当未见分布成功率，更不能替代之前300轮结果。所有方块保持原病例配置；C/D尺寸70–90mm，D站位后移20mm。

### 位置与方向的代价

| 原病例 | 保持目标平均位置误差mm（前→后） | 手腕方向去趋势分量RMS deg（前→后） |
|---|---|---|
'''
for p in paired:report+=f"| {p['source']} | {p['goal_error_before_mm']:.3f}→{p['goal_error_after_mm']:.3f} | {p['rotation_rms_before_deg']:.3f}→{p['rotation_rms_after_deg']:.3f} |\n"
report+='''
姿态RMS与角速度不是同一个指标：动作更慢可以同时有较大缓慢方向摆幅。B000/C020/B051的目标平均位置误差略增，D000/B080/D020方向摆幅有增加。不可称为全指标最优。
过慢腕修正0.01虽能减小关节速度，但A000位置平均误差约7mm，比默认组合约2.9mm大；阻尼4也不比3更好。没有用“更慢”替代“更准确”。

位置0.03/方向0.06的探索支路在B080、D020降低方向RMS，却提高了平均位置误差，D020平移RMS也高于统一0.03；A000没有获益，D000方向改善很小。四例虽都成功，但不适合直接替换所有场景默认值。更合理的后续方向是按接触阶段和方向误差带限调整，不是简单全局提高方向增益。

### 全部物理试验

| ID | 成功 | 启用s | 阻尼系数 | 位置增益 | 方向增益 | 目标低通s | 手腕RMSmm | 方向RMSdeg | 目标平均误差mm | 手内滑移mm |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
'''
for r in rows:
    c=r['config'];v=poses[r['id']]
    report+=f"| {r['id']} | {'是' if r['success'] else '否'} | {c['start']} | {c['damping']} | {c['servo_gain']} | {c.get('rotation_gain',c['servo_gain'])} | {c['tau']} | {r['metrics']['HOLD']['wrist_detrended_rms_mm']:.3f} | {v['hold_wrist_orientation_detrended_component_rms_deg']:.3f} | {v['hold_wrist_goal_error_mean_norm_mm']:.3f} | {r['local_slip_mm']:.3f} |\n"
report+='''
### 物理真实性与成功门

自由底座、自由方块、原生整手碰撞；人工球形指垫contype/conaffinity均为0，neq=0、nmocap=0、方块执行器=0。主仿真循环只写ctrl，无物体状态覆盖/焊接/外力黏附。独立七关节finger PD仍直接控制手，不输入SONIC；SONIC仍运行并输出全部29个身体关节目标。
原v2门未改：完整运行53s；保持窗至少2000步且每步均满足抬高≥70mm、桌面支持<0.05N、拇指与食指/中指承重各>0.1N、双脚各>1N、无非足地面/机器人桌面支持；全抬升腕局部滑移≤10mm；关节超限<0.002rad。成功病例保持窗2500个1ms步。独立分析比较200Hz/20ms记录，1ms门结果来自执行器内监测，未声称独立全量重算每一接触步。

数据目录：`'''+str(R)+'''/out`；数值分析：`analysis/wave*-evaluation.json`及`tracking-'''+str(count)+'''.json`。
全程保留旧源码/输入SHA、配置冻结、每条rc/日志/原始失败、规则SHA、资源检查。每条模型标识可追溯至具体原机器人XML与mesh资产；未重新训练ARDY或SONIC权重。

### 同帧率真实状态视频

'''
for v in videos:report+=f"- {v['id']}：`out/{v['id']}/replay25clip/grasp-25fps.mp4`，{v['replay']['frames']}帧，{v['replay']['fps']}fps，{v['replay']['duration_s']:.2f}s，解码已核验。\n"
report+='''
## 四、失败项与原因

- A_lpf60物理失败：手内滑移约319.6mm，保持阶段无对置指支持；策略/动力学反馈改变后目标滞后，轨迹抖动与跟踪误差都增大。仅此一组不能证明所有小时间常数滤波均无效，但本次60ms方案明确不采用。
- B051_base忠实复现原失败：方块抬高约89.9mm但腕局部滑移17.55mm超过10mm，因此仍标失败，不能以抬起来的视频替代成功门。
- 全53s/25fps的初次渲染按实际速度预计接近/超出580s单命令上限，核对本任务进程组身份后主动停止，保留4个首试日志/部分视频/rc；新目录重渲染34–53s关键段。部分视频不作为有效交付或有效视频计数。
- 本任务调度曾短时超过最多4个工作进程的声明；已暂停自有进程并加任务级拒绝重叠启动的守卫。没有隐瞒这项偏差，也没有改动他人进程。
- 依赖检查/分析首次错误与原始输出见`operator-errors.md`及`logs/steps.md`。没有为补依赖修改任何已有环境。

## 五、下一步建议

1. 默认保留42s开始的阻尼3+统一修正0.03；未放宽手指/力矩/成功门。参数不足以覆盖所有轨迹，迁移需登记新任务并回归。
2. 位置/方向解耦是探索支路，先看全部方向试验是否兼顾位置、方向和成功门，不按单指标或单病例自动替换默认。
3. 下一批冻结新位置/尺寸、质量和扰动输入后，分阶段评估前馈参考速度与参考位置一致性、接触事件切换、方向反馈和自由底座耦合；可加入较小时间常数但须保留低通失败对照。此处是建议，未声称这些已修好。
4. 接近阶段35s左右已有物体接触；42s前本默认方案完全不改，不能声称伸臂全过程无抖动/无碰撞。仅提前降低增益的支路不作为默认，需先评估完整姿态/接触路径。
5. 完整ARDY动态动作归因、SONIC输入时序一致性、多版本稳健性和实机迁移仍待验证；只在MuJoCo3.2.7确认当前病例改善。

## 六、复现方法

旧批次与本任务关闭后均不覆写或重开；先遵守最新AGENTS.md登记新任务，再复制本任务只读源码至新自有目录并更新任务路径/资源声明。先冻结原病例body/hand/wrist参考及场景SHA，且不要重新规划后伪装同输入对照。

当前试验的实际执行命令、CPU绑定、580s上限、rc和源SHA完整存于`configs/*receipt.json`。关键改进选项：

```text
--native-mesh --retract-raise --wrist-servo
--arm-target-tau 0 --arm-damping 3 --servo-gain 0.03 --change-start 42
```

原版对照用`--arm-damping 2 --servo-gain 0.10`；方向探索用独立`execute_jitter_pose.py --servo-rotation-gain 0.06`，不替换被冻结的旧执行程序。
`launch_safe.py`启动前检查本任务已有仿真/渲染进程；并发上限4、每工人2核、AS4GiB，所有数值库线程1，禁止重叠波次。每轮后执行`evaluate_wave.py`核验冻结输入、原版位相等与原成功门，然后`evaluate_tracking.py`检查姿态/跟踪代价。
`render_clip.py`使用200Hz记录，每8帧取1帧输出25fps，无插值或物理积分；用同采样规则生成改前/后各一个，不将6.25fps旧片与25fps新片当唯一改善证据。

报告和核心结果均在服务器与本机留档；最终任务关闭与Git入库以独立回执为准，不因本报告出现就推断done。
'''
with (R/'REPORT.md').open('x',encoding='utf-8') as f:f.write(report)
shutil.copy2(R/'REPORT.md',B/'reports'/(R.name+'-report.md'));shutil.copy2(R/'REPORT.md',W/'REPORT.md')
for source in list(R.glob('*.py'))+list(R.glob('*.md'))+list(R.glob('*-spec.json')):
    if source.name=='REPORT.md':continue
    shutil.copy2(source,W/source.name)
for source in (R/'analysis').glob('*.json'):shutil.copy2(source,W/source.name)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- Six-section report built from '+str(len(rows))+' terminal physics records; four true-state clips. REPORT SHA='+sha(R/'REPORT.md')+'; home mirrors byte-equal.\n')
assert sha(R/'REPORT.md')==sha(W/'REPORT.md')==sha(B/'reports'/(R.name+'-report.md'))
print(json.dumps({'report_sha':sha(R/'REPORT.md'),'trial_count':len(rows),'success_count':summary['physics_success_count'],'paired_cases':paired},ensure_ascii=False))
