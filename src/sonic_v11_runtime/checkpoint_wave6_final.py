"""Seal the full bounded20 search wave, not the persistent Track4 goal."""
import datetime
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='68db8493e678a0cab6613610a8d87f4fca6597f8369ccd5a75cea089bfd41db6'
launches=[json.loads(line) for line in (D/'wave6-launches.jsonl').read_text().splitlines()]
assert len(launches)==20 and len({r['name'] for r in launches})==20
summary_path=D/'wave6-summary.json';report=B/'reports'/f'{T}-wave6-report.md';bundle=D/'wave6.tar.gz'
assert not any(p.exists() for p in [summary_path,report,bundle])
records=[]
for launch in launches:
    folder=D/'out'/launch['name'];path=folder/'result.json';assert path.exists() and path.stat().st_size<512*1024
    r=json.loads(path.read_text());stamp=r['runtime_stamp']
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert sha(folder/file)==stamp['model_sha'][key]
    sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]
    sources += [(key+'.py',digest) for key,digest in stamp['library_sha'].items() if (D/(key+'.py')).exists()]
    for name,digest in sources:
        saved=D/'source-snapshots'/digest/name;assert saved.exists() and sha(saved)==digest
    assert not r['body_action_override'] and not r['base_fixture'] and r['peak_external_force']==0
    assert not r['whole_body_balance_validated'] and not r['full_task_com_cop_validated']
    keys=['success','legacy_success','gates','duration_s','wall_s','fail_reason','hold_min_lift_m','hold_slip_m',
        'hold_min_contact_bodies','actual_to_decoded_motor_target_rms_rad','execution_audit','balance_audit_summary',
        'neutral_shoulder_offset_rad','clearance_approach','post_clearance_native_branch','post_clearance_branch_servo',
        'endpoint_branch_seed','phase_clips_consumed','user_corrections','source','motion_profile',
        'policy_p95_ms','policy_median_ms','model_load_s','no_grip','grip_preload_mm','independent_finger_kp_gain']
    records.append(dict(name=launch['name'],launch=launch['launch'],runtime_stamp=stamp,result_sha256=sha(path),
        trajectory_sha256=sha(folder/'trajectory.npz'),**{k:r.get(k) for k in keys}))
positive=[r for r in records if r['success']]
assert {r['name'] for r in positive}=={'w6_branchpreload15_near327','w6_branchpreload15_near314'}
negative=json.loads((D/'out/w6-no-grip-comparison327.json').read_text())
assert negative['on_success'] and not negative['off_success'] and all(negative['preclose_arrays_exact'].values())
replay=D/'out/w6-safe-replay327';video=json.loads((replay/'replay.json').read_text())
assert video['source_episode_sha256']==positive[0]['result_sha256'] and sha(replay/'grasp.mp4')==video['video_sha256']
assert video['physical_steps']==0 and video['final_table_supported'] and video['initial_robot_table_max_normal_N']==0
now=datetime.datetime.now().astimezone().isoformat()
summary=dict(task=T,wave=6,cutoff=now,launches=launches,results=records,completed_launches=20,remaining_slots=0,
    strict_successes=len(positive),task_active=True,full_track4_complete=False,real_robot_ready=False,
    paired_success_versions=['3.2.7','3.14.0'],matched_no_grip_versions=['3.2.7'],
    source='Original near_s42 selected-source ARDY multistart/task retargeting, official SONIC body, independent contact-gated fingers',
    no_grip=negative,video_sha256=video['video_sha256'],replay_manifest_sha256=sha(replay/'replay.json'),
    scope='20 heterogeneous bounded search launches, not a homogeneous success-rate estimate')
rows=['| 启动 | 测试 | 版本 | 右臂峰速rad/s | 全程碰桌N | HOLD最低mm | 滑移mm | 严格成功 |',
      '|---:|---|---|---:|---:|---:|---:|---|']
for r in records:
    height=f"{r['hold_min_lift_m']*1000:.3f}" if r['hold_min_lift_m']!=-1 else '无HOLD窗'
    slip=f"{r['hold_slip_m']*1000:.3f}" if r['hold_slip_m']!=1e9 else '无HOLD窗'
    rows.append(f"|{r['launch']}|{r['name']}|{r['runtime_stamp']['mujoco_version']}|{r['execution_audit']['maximum_actual_arm_speed_rad_s']:.6f}|{r['balance_audit_summary']['robot_table_all_max_normal_N']:.6f}|{height}|{slip}|{r['success']}|")
text=f'''# 第六波：零碰桌自由底座ARDY/SONIC抓取检查点
- task={T}；codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；截止{now}。20启动全部退出；本波封存，整体目标ACTIVE。

## 一、结论

有条件能：同一near_s42输入的自由底座抓取，在MuJoCo3.2.7/3.14.0各1次通过v5全部验收，HOLD最低125.795/127.078mm，滑移6.148/3.798mm；全程机器人桌接触0N，右臂峰速1.348/1.345rad/s，29身体关节限位超量0。
3.2.7同源不闭手负对照失败，闭手前8类轨迹完全相同；3.14新路线负对照还未跑。两例不是随机重复成功率、不是ARDY必要性证明。
仍未完成Track4：没有新文本/物体泛化、交互纠正验收、整链实时性、全身COM/COP、实机；最终释放落桌不等于受控放置。

## 二、操作步骤

前13次来源接口和失败已不可变双档；本轮增加7次，操作/退出码见logs/{T}/steps.md。只写自有实现和已授权项目根入口，不覆盖在制vendor/KIMODO/共享环境/配置。
14/15：在实际腕高度合格后用6个真实ARDY帧+实际姿态共7种有界初值求静态可达分支，不用旧人工arm端点；筛选手指可达、关节裕量、OPEN静态桌间隙。静态可达并不能保证SONIC输入可执行。
16/17：先6s平滑进入所选分支，再5Hz以实际根姿态/实际闭手配方FK求局部IK，把有界60mrad修正加到SONIC输入。C2过滤、官方decoder输出和独立手指不变；APP硬上限26→32s预留闭环修正，全局90s不变，25mm到位/速度0.2rad/s门未放宽。实际两版在24.514/24.566s已进入PREGRASP，均早于原28.004s截止，因此不只是延长等待；隔离超时与servo本身的独立消融尚未做。
18/19：仅手指几何预压0.5→1.5mm，原扭矩上限/增益3/场景碰撞/物体质量不变。两版抓持通过。静态分支筛选仍用固定0.5mm手指可达模板，只是粗筛，不是实际1.5mm手指运行的动态证书。
20：相同源/参数仅no-grip，保存原始分岔而不把几何夹住误算算法抓取。源SHA和模型版本均内嵌；所有旧失败仍在，20次混合搜索不是2/20方法成功率。

## 三、实测证据

{chr(10).join(rows)}

14/15两版静态branch选真实near第19帧；在保存28.002s状态，实际闭手配方抓取点偏50.672/50.676mm，实际→decoded最大关节误差13.712/15.656mrad。原参考在当前根状态FK也偏55.509/53.485mm：固定关节模板随自由根状态变化漂移，且SONIC输入不等于motor目标。零步诊断不把假设FK当可实现状态或真实接触力。
16/17闭环各真实更新5次，实际到位误差24.992/24.971mm；非直接电机/物体改写。16在LIFT3997/4002阶段样本由拇指+中指承重，但HOLD889/1002且最后脱落；18同两个手指LIFT4002/4002、HOLD1002/1002，HOLD最小法向力0.0755/0.0645N、支撑力0。阶段遥测包含边界，不与993验收窗分母混用。
18/19最终原求解器20ms接触白名单只有table_top，floor=false；脚支撑且HOLD没有机器人靠桌/非脚靠地。全程全身平衡不是已证事实。
不闭手3.2.7闭手前{negative['matched_preclose_frames']}帧qpos/qvel/身体输入/decoder/手指参考/扭矩/time/phase精确一致，之后手指参考最大差{negative['postclose_hand_reference_max_difference_rad']:.6f}rad，ON成功/OFF失败。3.14新路线负对照pending，不拿波5旧路线代替。
实际输入仍原near，独立手指是任务控制器、不是ARDY生成。新reach_s43接口确实进入SONIC但先前失败未解决，不宣称新输入泛化。生成与phase原始NPZ/SHA仍保留。
新视频sha={video['video_sha256']}，MuJoCo3.2.7同原Python/NumPy绘制保存qpos，物理步数0；仅截取闭手前1s至末尾，不是实机或实时服务。最终落桌是自由释放。

## 四、失败项与限制

14/15原文`approach native branch settling timeout`；16/17流程完成但HOLD验收失败。静态筛选低IK误差≠物理抓取，不拿第18条覆盖失败历史。
规则闸停rc9 `STOP: collaboration rules changed; read the new rules first`，3段完整复读；当前sha68db8493e678，差异仅标题排版，未改共享AGENTS；note由写者回执journal#2307确认。最初全量输出/聚合输出被工具截断后分别重读到EOF，未假装完整。
SSH初次拼写`Bad configuration option: stricthostchecking`，正确Key拼写后恢复。远端rg未安装，改grep。首次grip_diagnosis误把输出名当第二episode，第一例统计已打印后第二例FileNotFoundError；按单episode复跑rc0，未创建缺失输出。不把本地缺source_physics_core镜像、错误env205555路径或D/rules*不存在解释成远端成果被删。
渲染器旧guard误要求whole_body_balance_validated；修为真实HOLD支撑门，不回写结果或抬高声明。32x32真实渲染分支3.2.7/NumPy1.26.4通过，零物理步。
安全门只含显式右臂速度与身体关节限位/桌接触；腿峰速/COM/COP未认证。G1来源模型有任务手指pad/碰撞/摩擦适配，不等于实机参数完全一致。物体定位是仿真真值，不是视觉；手指增益3、预压1.5mm、肩参考0.2rad均人工方案设定，不计用户文本纠正。
branch静态搜索0.52/0.61s；整段仿真约59.6s、实际wall115.6/117.4s，只能称离线仿真演示。policy p95不是整循环deadline；生成冷载入68.8s未计入旧3.16s生成job读数，整链时延待统一。

## 五、下一步

下一有界波先复现相同新路线3.14 no-grip及成功重复，不覆写本波20槽账本；再选reach_s43清单/不同文本输入检验安全与抓持，不能只调seed称泛化。
保持新物理门，接入contact-qualified SETDOWN，稳定对向接触后再谈受控放置；增加拇指+指定对指资格门/失去夹持的安全停止，不注物体力/weld。
补统一文本生成冷/暖时延与全循环deadline、纠正记录、全身平衡/腿限值；实机、公开发布和小组第二方法仍需人类安排。部署/本波归档不关闭整体目标。

## 六、复现方法

```bash
D=/data/group4/{T}
ENTRY=/home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh
bash "$ENTRY" status
# 本波20槽已用完，下面仅示意配置；须先登记下一有界波并生成未占用w7名字，不能绕过run.sh预算闸
# 官方SONIC输入+独立手指，所有body decoder目标保持原输出
# --strict-execution --finger-gain 3 --grip-preload-mm 1.5 --table-front .24 --lift-height .15
# --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo
# --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference
# --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1
# --opponent middle --close-seconds .5 --neutral-shoulder-offset .2 --clearance-approach
# --clearance-native-branch --clearance-branch-servo
# PYTHONPATH="$D/mujoco314-only"只切MuJoCo包；--no-grip是负对照；--motion-profile选择输入
```
封存20条原始结果/模型/轨迹/接触、源快照/规则复读、生成四段与profile、诊断、动画和操作流水；不重新分发环境/SONIC共享权重。双端报告/摘要/压缩包SHA验证后再做own-path Git；postcommit回执另增量登记，不无限重封已锁包。
'''
summary_path.write_text(json.dumps(summary,indent=2)+'\n');report.write_text(text)
with (L/'steps.md').open('a') as f:
    f.write('\n## [WAVE6 SEALED20] '+now+'\n-20 launches exited; strict successes2 in paired versions, not success-rate estimate. Goal ACTIVE. No-grip327 matched;314 pending.\n-Report='+str(report)+'; new video='+str(replay)+'; untouched old progress8/13 archives.\n-Failures including title-change guard/SSH option spelling/grip argument misuse/local missing source mirror recorded in report.\n')
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
shutil.copy2(summary_path,W/summary_path.name)
included=[D/'source-snapshots',D/'wave6-launches.jsonl',summary_path,report,L,B/f'ardy-grasp-run-{T}.sh',D/'out/generated_phases2']
included += [D/'out'/r['name'] for r in records]
included += list((D/'out').glob('w6-*'))
included += [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py','.sh'}]
included += list(W.glob('rules-read-*'))
included=list(dict.fromkeys(included))
current=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
upper=sum(p.stat().st_size for base in included for p in ([base] if base.is_file() else base.rglob('*')) if p.is_file() and not p.is_symlink())
assert current+upper+16*1024**2<3*1024**3 and shutil.disk_usage(D).free>upper+30*1024**3
with tarfile.open(bundle,'w:gz',dereference=False) as tar:
    for path in included:
        arc=str(path.relative_to(D)) if path.is_relative_to(D) else 'checkpoint-logs' if path==L else path.name
        tar.add(path,arcname=arc)
manifest={str(report):sha(report),str(bundle):sha(bundle),str(summary_path):sha(summary_path)}
(W/'wave6-archive.sha256').write_text(''.join(digest+'  '+path+'\n' for path,digest in manifest.items()))
print(json.dumps(dict(manifest=manifest,launch_count=20,strict_successes=2,task_active=True,pre_archive_bytes=current,archive_upper_bytes=upper),indent=2))
