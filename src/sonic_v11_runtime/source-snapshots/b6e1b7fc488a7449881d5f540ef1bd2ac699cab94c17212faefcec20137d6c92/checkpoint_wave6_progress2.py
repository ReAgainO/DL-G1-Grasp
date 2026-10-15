"""Immutable 13-trial partial-wave checkpoint, preserving strict failures."""
import datetime
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c'); T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T; W=B/'work'/T; L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
launches=[json.loads(row) for row in (D/'wave6-launches.jsonl').read_text().splitlines()]
assert len(launches)==13 and len({r['name'] for r in launches})==13
summary_path=D/'wave6-progress2.json'
report=B/'reports'/f'{T}-wave6-progress2-report.md'
bundle=D/'wave6-progress2.tar.gz'
assert not any(p.exists() for p in [summary_path,report,bundle])
entry=B/f'ardy-grasp-run-{T}.sh'
assert sha(entry)==sha(D/'ardy-server-entry.sh')=='ed99c6e9bc53956c177cb4646eea2c1083da4930a204ce1a1599ea074a357357'
profile_path=D/'out/w6-reach43-input-profile.json'
assert sha(profile_path)=='1b19b0e215117ab922563b3dd23768b50b640ec49ff1175e30d3d6c4e11d31f7'
preflight=json.loads((D/'out/w6-reach43-preflight.json').read_text())
assert preflight['physical_steps']==0 and set(preflight['converted'])=={'reach','lift','hold','release'}
records=[]
for launch in launches:
    folder=D/'out'/launch['name']; path=folder/'result.json'
    assert path.exists() and path.stat().st_size<512*1024
    r=json.loads(path.read_text()); stamp=r['runtime_stamp']
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:
        assert sha(folder/file)==stamp['model_sha'][key]
    sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]
    for key,value in stamp['library_sha'].items():
        if (D/(key+'.py')).exists(): sources.append((key+'.py',value))
    assert {'neutral_pose','execution_monitor'}<=stamp['library_sha'].keys()
    for name,digest in sources:
        saved=D/'source-snapshots'/digest/name
        assert saved.exists() and sha(saved)==digest,(launch['name'],name)
    assert not r['body_action_override'] and not r['base_fixture']
    assert not r['whole_body_balance_validated'] and not r['full_task_com_cop_validated']
    profile=r.get('motion_profile')
    if profile:
        assert sha(profile_path)==profile['profile_sha256']==stamp['library_sha']['input_profile']
        assert sha(D/'out/generated_phases2/summary.json')==profile['generation_summary_sha256']==stamp['library_sha']['generation_summary']
        assert set(profile['roles'])=={'reach','lift','hold','release'}
        for role,source in profile['roles'].items():
            actual=Path(source['source_npz']).resolve()
            assert actual.is_relative_to(D) and sha(actual)==source['source_npz_sha256']
            assert source['source_npz_sha256']==preflight['converted'][role]['source_npz_sha256']
        assert r['source']['source_npz_sha256']==profile['roles']['reach']['source_npz_sha256']
        assert r['ardy_arm_prior_consumed_by_sonic'] and not r['endpoint_branch_seed']
    keys=['success','legacy_success','gates','duration_s','wall_s','fail_reason','hold_min_lift_m',
          'hold_slip_m','hold_min_contact_bodies','actual_to_decoded_motor_target_rms_rad',
          'execution_audit','balance_audit_summary','neutral_shoulder_offset_rad','clearance_approach',
          'endpoint_branch_seed','endpoint_branch_loaded','phase_clips_consumed','user_corrections',
          'source','motion_profile','policy_p95_ms','policy_median_ms','model_load_s']
    records.append(dict(name=launch['name'],launch=launch['launch'],runtime_stamp=stamp,
        result_sha256=sha(path),trajectory_sha256=sha(folder/'trajectory.npz'),
        **{k:r.get(k) for k in keys}))
now=datetime.datetime.now().astimezone().isoformat()
summary=dict(task=T,wave=6,cutoff=now,launches=launches,results=records,completed_launches=13,
    remaining_slots=7,strict_successes=sum(r['success'] for r in records),task_active=True,
    full_track4_complete=False,real_robot_ready=False,profile_sha256=sha(profile_path),
    scope='13-trial partial wave, not a homogeneous method success-rate estimate')
rows=['| 测试 | 版本 | 腕峰速rad/s | 机器人桌面峰力N | HOLD最低mm | 滑移mm | 严格成功 |',
      '|---|---|---:|---:|---:|---:|---|']
for r in records:
    height=f"{r['hold_min_lift_m']*1000:.3f}" if r['hold_min_lift_m']!=-1 else '无有效HOLD窗'
    slip=f"{r['hold_slip_m']*1000:.3f}" if r['hold_slip_m']!=1e9 else '无有效HOLD窗'
    rows.append(f"| {r['name']} | {r['runtime_stamp']['mujoco_version']} | {r['execution_audit']['maximum_actual_arm_speed_rad_s']:.6f} | {r['balance_audit_summary']['robot_table_all_max_normal_N']:.6f} | {height} | {slip} | {r['success']} |")
table='\n'.join(rows)
text=f'''# ARDY直接服务器部署：第六波13次部分检查点
- task={T}；codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；截止{now}；整体目标ACTIVE，仍余7启动槽。

## 一、结论

可以直接在服务器项目根运行共享入口；已部署状态查看、来源清单检查及可选择的实际ARDY NPZ执行接口，没有覆盖队友vendor源码。
两版本旧near_s42配0.2rad双肩参考+先抬腕再转向，全程碰桌0N、右臂峰速1.348/1.345rad/s、身体限位超量0；但抬升途中脱手，不能叫抓取成功，也不是全身/实机认证。
新reach_s43确实改变SONIC输入和输出，不只是改文件名；安全性与夹持并未泛化。前13次严格成功{summary['strict_successes']}，混合策略搜索不是方法成功率，Track4未完成。

## 二、操作步骤

1. 前8次报告/包/摘要本机独立SHA匹配438c194ef8bcefbd99b54cb51e8c0b03c117a5bbb52b8950f4be21514b0961f6 /27e74252eaa56c66ebe0f16a1a7d11a2a58dc288cf1d58c7bb8aeb03e7ea662e /9013e153322c5c1f9a0825876db4e655e4d05fc3b986fa0660f3bedc6ed51786。
2. 原始500Hz接触明确旧路径碰撞发生在APPROACH右腕/食指/中指；0.2rad是显式初始姿态和SONIC中性输入参考适配，并非纯初始条件反事实。保留接触物理、实际速度/限位和旧抓取门。
3. 新MotionProfile校验相对路径、输入与CSV/生成summary SHA、角色、fps25、34骨架、文本/帧数/seed元数据；真实NPZ本地旋转转换与vendor CSV对拍。输入角色不是语义成功证明；seed归于生成summary，不推断NPZ内种子。
4. 默认仍near_s42；显式`--motion-profile out/w6-reach43-input-profile.json`消费reach_s43，另三阶段仍lift/hold/release_s42。参数界面15项正负测试本机与服务器通过，预检4段29身体关节；未重新生成动作、实际用户纠正0。
5. 原endpoint分支距离是各分支自己的seed距离，并非相对统一selected ARDY姿态。新记录更正标签；profile禁止消费未重建的旧endpoint分支，本轮clearance路径加载但不消费旧endpoint。原历史结果/源快照保留。
6. 共享根入口更新sha={sha(entry)}，支持evidence/status/preflight/profile-check/simulate。大数据仍/data避免/home压力；没有覆盖共享环境/权重、KIMODO、系统配置或真实机器人。
操作流水/所有退出码见`logs/{T}/steps.md`及run日志，4CPU/AS16GiB/300s/90s/3GiB累计预算，启动失败也计数。

## 三、实测证据

{table}

默认接口回归：9号旧源与11号新源1509帧，qpos/qvel/SONIC input参考/decoded目标/手指参考/actuator_ctrl/time/phase全部逐元素完全相同，最大数值差0；只变源指纹和更准确标签。不是凭测试退出码称兼容。
旧near输入配0.2姿态两版实际→decoded RMS0.015995/0.015962rad，全程无碰桌，但HOLD物体已落回桌。25.292/42.510mm“滑移”由完整HOLD相对腕运动定义，不能理解成仍夹持时的纯微滑移。
新reach输入SHA62607734726d37cba47ef2b0c1c1fc53d0c2cc9200e6181a1b281376b01dc5b3（旧78eac68c405ceae93cb737b58022e83b5251d9d71def1eedb417caae0b73daff），profileSHA{sha(profile_path)}。实际角色源路径、文本、seed、转换对拍以及policy参考/输出差异保留在JSON和原轨迹。
新输入3.2.7桌面力4.466230N，回归到碰桌失败，不能由近似场景的旧输入零碰桌推泛化；13号的第二版本数字如表，不按期待改结果。
抓持力诊断：波5成功HOLD的1002条阶段遥测都由拇指+中指接触，最小0.285/0.268N；0.2旧near两版HOLD的1002条全部无拇指+中指接触，桌面支撑0.1962N，失效主要在LIFT途中而非“仅保持高度不够”。遥测阶段分界含边界样本，与验收hold窗993样本不同，不混用分母。

## 四、失败与勘误

原18sAPP超时名称不准确（已在13.418s达高但剩余6s转向超预算）；新26s修复后仍夹持失败。0.1偏置不能跨版本默认，旧near0.2能降低碰撞但不能稳定夹持。新seed仍碰桌，不采纳为默认成功路线。
第一次本机来源测试因Windows沙盒系统TEMP ACL失败：`PermissionError: [Errno 13] Permission denied: .../reach.npz`，清理也`WinError5`；改为校验过的工作区新建临时子目录后15项通过，服务器15项亦通过，无仿真时间推进。未强行改系统权限或清理未知临时目录。
第一次只读搜索引用不存在的build_free_replay路径报os error2，并意外匹配单行大JS被工具截断；改用真实文件位置/有界内容，不误判为服务器数据缺失。
前8检查点表格用抬高>=0来标记HOLD，误把第8条-0.046mm实际落桌HOLD写成“未完成HOLD”；本报告依有效HOLD哨兵-1判断，负微量保留。原JSON数值不变，旧报告/包不回写。
新的body速度门只认证29关节限位及右臂显式工程峰速，腿速度记录但未认证，全程COM/COP未验证。真值定位、手指IK、重力补偿/PD增益/平面任务适配均明示；没有实机、必要性或完整用户纠正证据。
生成summary的reach任务3.16s/encode1.07s不含冷载入textencoder68.8s+model0.7s，更不等于文本到物理动作整链时延。零用户纠正不是零人工设置。

## 五、下一步

用`grip_diagnosis.py`保留抬升阶段接触断续的具体时段；先检查物体两侧接触与可达手指姿态连续性，不能加物体weld/外力或删除碰撞。增加必须拇指+指定对指的资格门，防同侧两指被误当对向夹持；本批三份已查样本并未出现该同侧误判，不把预防性改进当本次脱手根因。
对新输入做碰撞感知轨迹适配而非仅腕高度条件，继续新输入/负对照/不同文本及有限用户纠正与整链时延。原phase释放还未实现受控放置；身体控制与平衡/模型实机校准仍有限制。
仍余7启动槽，归档/部署不是关闭目标。共享源需要改时先核在制归属，不触碰KIMODO；实机/公开发布仍须人类安排。

## 六、复现方法

```bash
D=/data/group4/{T}
ENTRY=/home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh
bash "$ENTRY" status
# NEW_JSON未占用；只做输入检查，不占物理启动槽
bash "$ENTRY" profile-check out/w6-reach43-input-profile.json NEW_JSON.json
# 名字须以w6_开头且未占用；不是无限测试入口
bash "$ENTRY" simulate w6_NEW_NAME --motion-profile out/w6-reach43-input-profile.json --neutral-shoulder-offset .2 --clearance-approach --strict-execution --finger-gain 3 --table-front .24 --lift-height .15 --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5
# 去--motion-profile及其值复现旧near默认；3.14仅改MuJoCo包，原Python/NumPy不变
# PYTHONPATH="$D/mujoco314-only" bash "$ENTRY" ...
```

包包含这13例原始数据/场景/全部源快照、新清单/原4段生成NPZ及summary、诊断/操作流水。G1资产与SONIC权重/环境引用保持原归档来源；不重新分发共享权重/环境。报告/包本机独立SHA回读；own-path Git结论另增量回执，不宣布整波/Track4完成。
'''
summary_path.write_text(json.dumps(summary,indent=2)+'\n'); report.write_text(text)
with (L/'steps.md').open('a') as stream:
    stream.write(f'\n## [WAVE6 PROGRESS2] {now}\n-13 launches exited; remaining7, strict positives='+str(summary['strict_successes'])+'; goal ACTIVE.\n-Direct shared root entry status/profile-check deployed; verified NPZ selection used in actual official SONIC body execution. Default1509-frame regression arrays identical.\n-Both old-near 0.2rad cases table0/speed1.35/limits0 but grip fails in LIFT. New reach43 consumed, NOT a successful grasp/generalization claim.\n-Local test first failed due TEMP PermissionError/WinError5; workspace-owned temporary fixtures pass15, server pass15; no permission changes or unknown cleanup.\n-Progress1 table negative-HOLD label erratum; raw JSON unchanged.\n')
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}: shutil.copy2(path,W/path.name)
shutil.copy2(summary_path,W/summary_path.name)
shutil.copy2(profile_path,W/profile_path.name)
shutil.copy2(D/'out/w6-reach43-preflight.json',W/'w6-reach43-preflight.json')
included=[D/'source-snapshots',D/'wave6-launches.jsonl',summary_path,report,L,entry,D/'out/generated_phases2']
included += [D/'out'/r['name'] for r in records]
included += list((D/'out').glob('w6-*'))
included += [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py','.sh'}]
current=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
upper=sum(p.stat().st_size for base in included for p in ([base] if base.is_file() else base.rglob('*')) if p.is_file() and not p.is_symlink())
assert current+upper+16*1024**2<3*1024**3
assert shutil.disk_usage(D).free>upper+30*1024**3
with tarfile.open(bundle,'w:gz',dereference=False) as tar:
    for path in included:
        arc=str(path.relative_to(D)) if path.is_relative_to(D) else 'checkpoint-logs' if path==L else path.name
        tar.add(path,arcname=arc)
manifest={str(report):sha(report),str(bundle):sha(bundle),str(summary_path):sha(summary_path)}
(W/'wave6-progress2-archive.sha256').write_text(''.join(digest+'  '+path+'\n' for path,digest in manifest.items()))
print(json.dumps(dict(manifest=manifest,episodes=13,strict_successes=summary['strict_successes'],remaining_slots=7,task_active=True,pre_archive_bytes=current,archive_upper_bytes=upper),indent=2))
