"""Immutable eight-trial progress archive; wave6 still has unused slots."""
import datetime
import json
import shutil
import tarfile
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
launches=[json.loads(line) for line in (D/'wave6-launches.jsonl').read_text().splitlines()]
assert len(launches)==8 and len({x['name'] for x in launches})==8
summary_path=D/'wave6-progress1.json'
report=B/'reports'/f'{T}-wave6-progress1-report.md'
bundle=D/'wave6-progress1.tar.gz'
assert not any(p.exists() for p in [summary_path,report,bundle])
records=[]
for launch in launches:
    folder=D/'out'/launch['name'];path=folder/'result.json'
    assert path.exists() and path.stat().st_size<512*1024
    r=json.loads(path.read_text());stamp=r['runtime_stamp']
    assert {'mujoco_version','sys_executable','python_version','model_sha','scene_generator_sha','library_sha','dt'}<=stamp.keys()
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:
        assert sha(folder/file)==stamp['model_sha'][key]
    sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]
    for key,value in stamp['library_sha'].items():
        if (D/(key+'.py')).exists():sources.append((key+'.py',value))
    assert {'neutral_pose','execution_monitor'}<=stamp['library_sha'].keys()
    for name,digest in sources:
        saved=D/'source-snapshots'/digest/name
        assert saved.exists() and sha(saved)==digest,(launch['name'],name)
    assert not r['body_action_override'] and not r['base_fixture']
    assert not r['whole_body_balance_validated'] and not r['full_task_com_cop_validated']
    keys=['success','legacy_success','gates','duration_s','wall_s','fail_reason','hold_min_lift_m',
        'hold_slip_m','hold_min_contact_bodies','actual_to_decoded_motor_target_rms_rad',
        'execution_audit','balance_audit_summary','neutral_shoulder_offset_rad','clearance_approach',
        'endpoint_branch_seed','endpoint_branch_loaded','phase_clips_consumed','user_corrections']
    records.append(dict(name=launch['name'],launch=launch['launch'],runtime_stamp=stamp,
        result_sha256=sha(path),trajectory_sha256=sha(folder/'trajectory.npz'),
        **{k:r.get(k) for k in keys}))
now=datetime.datetime.now().astimezone().isoformat()
summary=dict(task=T,wave=6,cutoff=now,launches=launches,results=records,
    completed_launches=8,remaining_slots=12,strict_successes=sum(r['success'] for r in records),
    task_active=True,full_track4_complete=False,real_robot_ready=False,
    scope='Progress subset, not sealed full wave or a method success-rate estimate')
rows=['| 测试 | 版本 | 腕峰速rad/s | 机器人桌面峰力N | HOLD最低mm | 滑移mm | 严格成功 | 停止/失败门 |',
      '|---|---|---:|---:|---:|---:|---|---|']
for r in records:
    speed=r['execution_audit']['maximum_actual_arm_speed_rad_s']
    load=r['balance_audit_summary']['robot_table_all_max_normal_N']
    height=f"{r['hold_min_lift_m']*1000:.3f}" if r['hold_min_lift_m']>=0 else '未完成HOLD'
    slip=f"{r['hold_slip_m']*1000:.3f}" if r['hold_slip_m']<1 else '无有效保持窗'
    reason=r['fail_reason'] or ','.join(k for k,v in r['gates'].items() if not v)
    rows.append(f"| {r['name']} | {r['runtime_stamp']['mujoco_version']} | {speed:.6f} | {load:.6f} | {height} | {slip} | {r['success']} | {reason} |")
table='\n'.join(rows)
text=f'''# ARDY服务器直接部署与第六波前8次检查点
- task={T}；codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；截止{now}；整体目标ACTIVE，本波仍余12个启动槽，不是完整收工。

## 一、结论

已直接部署服务器项目根入口，并加入真实500Hz按阶段关节运动和全程桌面碰撞审计；官方SONIC身体目标未被脚本覆盖，无固定底座/物体weld/外力。
部分改善但未通过：双肩参考+0.1rad仅去掉准备阶段碰桌；先抬腕再转向明显降低腕峰速和桌面接触，但仍有接触，26s版本的夹持连续性/滑移也未通过，不把抬高当抓取成功。
前8次严格成功{summary['strict_successes']}；不同策略搜索不是方法成功率。第六波仍ACTIVE，完整Track4与实机就绪均未验证。

## 二、操作步骤

1. 第五波20次全量归档双端SHA：report31c2c60184776df3b4fd25767ccd47c1d46207d317465d3f0df31d758f635192，包6cb6bec55e89be1f12f33913f9195c3db2f112968afaed79975865fe5ed341f4。Git69b2cc36776d1a223a72abee81bfb0786e697dbc其他暂存blob保留、无push；journal#2294实际回执已回读。
2. 用户明确允许直接服务器部署；项目根新增`ardy-grasp-run-{T}.sh`（SHAe04f27871c5a8433fe4612b86dae068d9e1afb15048ed312eb4adf716274337a），支持evidence/preflight/simulate，实际试验均由此入口启动。没有覆盖共享vendor源码/队友在制文件。
3. 原500Hz solver2425条桌面接触明确为SETTLE/APPROACH右腕；42个候选零步进初始几何预检，0.1rad双肩姿态为可行候选，但预检不是动态路径或平衡证据。
4. neutral_pose同时改变仿真初始双肩角和SONIC中性输入参考；左臂保留偏置、右臂继续ARDY/task适配，不是纯初始条件对照。execution_monitor不写状态/控制，记录29身体关节分阶段速度/有限差分加速度/软限位超量。
5. 新v5严格门新增实际右臂速度≤2rad/s、29身体软限位超量≤2mrad、全过程机器人桌面接触<.001N；原HOLD/夹持/滑移/真实桌面返回门保留。2rad/s和2mrad是明确工程门，不是课程/实机认证标准；腿速度仅记录，尚未安全认证。
6. clearance_approach先以实测腕完整姿态抬到z≥.9m才允许旋转/接近；目标只进入SONIC参考，endpoint seed可加载但该路径不消费，结果明确标记。原18s阶段超时不足完成13.418s达高后的6s转向，改成26s并保留真实条件；整体90s/300s上限不变。
全部命令、退出码、资源在`logs/{T}/steps.md`及run日志。

## 三、实测证据

{table}

同源码零偏置/0.1rad两版本配对：3.2.7峰速6.684→5.108rad/s、桌面力44.275→42.506N、保持126.430→127.809mm，但仍不安全；3.14.0偏置样本CLOSE超时，不能采用为跨版本改进默认。
原18s接近版两版本在13.418s实际达到安全腕高度，峰速均1.016rad/s、桌面力5.393/5.559N，但尚未完成后续转向就被18s限时停止。原fail_reason“actual wrist clearance timeout”名称不准确，应为转向未完成；旧结果保留，新源停止原因已区分两阶段。
26s版3.2.7完成流程并有最低77.092mm抬高，但HOLD至少2指与滑移门失败（46.265mm），不能称保持抓取成功；腕峰速1.038rad/s，实际→解码RMS.021532rad，桌面力仍5.393N，未通过全程无碰撞。
观察器正负分支本地/服务器11项，接近预算修复后的初始/实际高度阴性/晚通过/终点/时钟越界9项；都零物理步进，不代替8次物理结果。全部模型/执行源/模块快照SHA核对。
物理8次都运行自由底座，身体输出官方1751/994 ONNX；独立手指KP×3和显式重力补偿仍为适配，不是原厂参数或实机验证。物体定位仍为仿真真值，实际用户纠正0。

## 四、失败与勘误

3.14偏置原文：`two-finger contact timeout`。18s接近两版原文：`approach actual wrist clearance timeout`，实际已达高，名称由新源更正为分阶段超时；不删除旧证据。
26s例循环正常完成也不能等同success=true，实际夹持/滑移/碰撞门必须全读；未进入HOLD时hold_min=-1和slip=1e9是哨兵，不解释成真实物体高度/米数。
首次波5归档来源短名断言失败，改完整路径+result/trajectory双SHA后封存；本地rg把Windows通配路径当文件首次报os error123，改-g过滤复查，非远端文件缺失。
追加的预检曾重建factory-neutral而非偏置例实际初始参考，新版同时分别输出initialization与factory_neutral_initialization，旧输出只代表factory基准，不当偏置姿态的直接证据。
旧whole_body_balance_validated命名过强，新物理结果明确false，HOLD支撑另列；原波5result不回改。完整COM/COP、碰撞安全、感知、生成泛化、用户纠正及实机均未完成。

## 五、下一步

先用新保存接触定位剩余5N载荷：`bash "$D/run.sh" "$D/execution_preflight.py" w6_clearance26_free327 NEW_OUTPUT`；比较0.2rad中性姿态或有明确几何间隙的第一段后退-抬腕策略，不能移除碰撞来过门。
身体运动满足后再处理夹持连续性/受控放下；接入已有但尚未消费的生成reach_s43 NPZ及新文本profile，修改硬编码入口，按实际源SHA/seed记录。不能只增加生成次数不验证其是否真正进入SONIC。
本波余12次启动，守原子计数；所有改动先零步进/分支测试再物理比较，并保留两个版本失败。直接共享代码修改仍核属主/在制任务，root入口已可用，不干预KIMODO。

## 六、复现

```bash
D=/data/group4/{T}
ENTRY=/home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh
bash "$ENTRY" evidence
# 新名字须w6_前缀、未占用，计数包含启动失败；当前不是无限启动入口。
bash "$ENTRY" simulate w6_NEW_NAME --neutral-shoulder-offset .1 --clearance-approach --strict-execution --finger-gain 3 --table-front .24 --lift-height .15 --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5
# 实际新名字应以w6_开头；去--clearance-approach重建旧策略，不能称之新安全正例。
# 3.14仅包改变：PYTHONPATH="$D/mujoco314-only"，base Python/NumPy保持不变。
```

历史按每条runtime_stamp和source-snapshots选择完整模块；checkpoint包包含这8条原始数据/场景/源快照/接触诊断和操作流水，G1资产及生成原NPZ依赖已在wave1/wave2及先前归档。共享权重/环境不重新分发。
本进度包双端SHA另回执，Git只本会话路径并核其他暂存blob，不push。本波仍余12槽，不创建done/blocked，不宣布完整Track4。
'''
summary_path.write_text(json.dumps(summary,indent=2)+'\n');report.write_text(text)
with (L/'steps.md').open('a') as f:
    f.write(f'\n## [WAVE6 PROGRESS1] {now}\n-8 launches exited, source/model snapshots verified; remaining12 slots, goal ACTIVE. Strict positives='+str(summary['strict_successes'])+'.\n-New monitor/neutral and wrist-clearance scaffold preserve SONIC targets.18s path failed after clearance13.418s;26s fixes phase budget but safety/grip gates remain unpassed.\n-Shared root entry deployed under direct user authorization; no shared vendor/teammate edits or KIMODO.\n')
for p in D.iterdir():
    if p.is_file() and p.suffix in {'.py','.sh'}:shutil.copy2(p,W/p.name)
shutil.copy2(summary_path,W/summary_path.name)
included=[D/'source-snapshots',D/'wave6-launches.jsonl',summary_path,report,L]
included += [D/'out'/r['name'] for r in records]
included += [p for p in (D/'out').glob('w6-*') if p.is_dir()]
included += [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py','.sh'}]
current=int(__import__('subprocess').check_output(['du','-sb',str(D)],text=True).split()[0])
upper=sum(p.stat().st_size for base in included for p in ([base] if base.is_file() else base.rglob('*')) if p.is_file() and not p.is_symlink())
assert current+upper+16*1024**2<3*1024**3
assert shutil.disk_usage(D).free>upper+30*1024**3
with tarfile.open(bundle,'w:gz',dereference=False) as tar:
    for p in included:
        arc=str(p.relative_to(D)) if p.is_relative_to(D) else 'checkpoint-logs' if p==L else p.name
        tar.add(p,arcname=arc)
manifest={str(report):sha(report),str(bundle):sha(bundle),str(summary_path):sha(summary_path)}
(W/'wave6-progress1-archive.sha256').write_text(''.join(value+'  '+key+'\n' for key,value in manifest.items()))
print(json.dumps(dict(manifest=manifest,episodes=8,strict_successes=summary['strict_successes'],remaining_slots=12,task_active=True),indent=2))
