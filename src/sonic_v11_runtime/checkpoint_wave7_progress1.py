"""Immutable first-ten-trial checkpoint; ongoing wave/Track4 remain ACTIVE."""
import datetime
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert json.loads((D/'active_cpu_wave.json').read_text())['wave']==7
launches=[json.loads(line) for line in (D/'wave7-launches.jsonl').read_text().splitlines()]
assert len(launches)==10 and len({r['name'] for r in launches})==10
assert not any(str(D/'sonic_grasp.py') in row or str(D/'phase_generate_entry.py') in row for row in subprocess.check_output(['ps','-eo','args'],text=True).splitlines())
summary_path=D/'wave7-progress1.json';report=B/'reports'/f'{T}-wave7-progress1-report.md';bundle=D/'wave7-progress1.tar.gz'
assert not any(path.exists() for path in [summary_path,report,bundle])
records=[]
for launch in launches:
    folder=D/'out'/launch['name'];path=folder/'result.json';assert path.is_file() and path.stat().st_size<512*1024
    r=json.loads(path.read_text());stamp=r['runtime_stamp']
    for key,name in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert sha(folder/name)==stamp['model_sha'][key]
    sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]+[(key+'.py',value) for key,value in stamp['library_sha'].items() if (D/(key+'.py')).is_file()]
    for name,value in sources:assert sha(D/'source-snapshots'/value/name)==value,(launch['name'],name)
    assert not r['body_action_override'] and not r['base_fixture'] and r['peak_external_force']==0 and r['user_corrections']==0
    keys=['success','gates','duration_s','wall_s','fail_reason','hold_min_lift_m','hold_slip_m',
        'execution_audit','balance_audit_summary','source','motion_profile','user_corrections',
        'no_grip','setdown_enabled','finger_table_clearance_mm','execution_cycle_latency',
        'policy_p95_ms','model_load_s','post_clearance_native_branch','post_clearance_branch_servo']
    records.append(dict(launch=launch['launch'],name=launch['name'],runtime_stamp=stamp,
        result_sha256=sha(path),trajectory_sha256=sha(folder/'trajectory.npz'),**{key:r.get(key) for key in keys}))
reads={name:json.loads((D/'out'/name).read_text()) for name in ['w7-no-grip-comparison314.json',
    'w7-repeat-comparison327.json','w7-repeat-comparison314.json','w7-text-comparison327.json',
    'w7-text-comparison314.json','w7-observer-regression327.json','w7-input-text-identity.json',
    'w7-table-effect327.json','w7-table-effect314.json']}
assert all(reads['w7-observer-regression327.json']['arrays'][key]['exact'] for key in reads['w7-observer-regression327.json']['arrays'])
generation=json.loads((D/'out/w7-generated-text/run.json').read_text());assert generation['exit_code']==0
binding=json.loads((D/'out/w7-source-binding/input-audit.json').read_text())
assert not binding['text_equal'] and binding['newtext_vs_control']['right_arm_max_delta_rad']>0
now=datetime.datetime.now().astimezone().isoformat()
summary=dict(task=T,wave=7,cutoff=now,launches=launches,results=records,completed_launches=10,
    remaining_slots=10,task_active=True,full_track4_complete=False,real_robot_ready=False,
    comparisons=reads,fresh_generation=generation,input_binding=binding,
    scope='Ten heterogeneous validation/improvement launches, NOT a homogeneous success rate; originalnear positive repetition, fresh same-seed text pair, optional table target constraints, observer regression',
    human_corrections_received=0,controlled_placing_validated=False)
rows=['|启动|测试|版本|HOLD最低mm|滑移mm|全程碰桌N|严格通过|',
    '|---:|---|---|---:|---:|---:|---|']
for r in records:
    height='无HOLD窗' if r['hold_min_lift_m']==-1 else f"{r['hold_min_lift_m']*1000:.3f}"
    slip='无HOLD窗' if r['hold_slip_m']==1e9 else f"{r['hold_slip_m']*1000:.3f}"
    rows.append(f"|{r['launch']}|{r['name']}|{r['runtime_stamp']['mujoco_version']}|{height}|{slip}|{r['balance_audit_summary']['robot_table_all_max_normal_N']:.6f}|{r['success']}|")
lat=reads['w7-observer-regression327.json']['latency']['complete_50Hz_cycles']
table_records=[r for r in records if r.get('finger_table_clearance_mm')]
assert len(table_records)==2
assert not reads['w7-table-effect327.json']['actuator_commands_changed'] and not reads['w7-table-effect314.json']['actuator_commands_changed']
table_claim=' / '.join(r['runtime_stamp']['mujoco_version']+':strict='+str(r['success'])+',tableN='+str(r['balance_audit_summary']['robot_table_all_max_normal_N']) for r in table_records)
text=f'''# 第七波前十次检查点：重复/真实新文本/手指桌面约束/整循环时延
- task={T}；codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；截止{now}。十次退出，余10槽；总目标ACTIVE。

## 一、结论

有条件能：原near输入在两版的新进程中再次严格抓取通过；3.14匹配no-grip闭手前1119帧8数组精确一致，闭手后真实分岔且不抬起；与旧3.2.7对照合并，结论只限该配置族。
真正新文本的NPZ已生成并改变SONIC输入/输出，但两版均被静态可达性筛选拒绝；同文字seed43样本虽抓持却有LIFT指垫碰桌，不能称文本泛化成功。1mm手指目标桌面约束两版没有改变手指指令/扭矩/物理轨迹，未成为有效改进，仍碰桌：{table_claim}。
当前不是实时/完整Track4：3.2.7整循环p95={lat['p95_ms']:.3f}ms，{lat['over_budget_count']}/{lat['samples']}周期超过20ms；尚无用户动作纠正、受控放置、视觉定位、实机和全身COM/COP认证。

## 二、操作步骤

用户明确要求改进直接上传、不改他人文件。本轮部署只替换本会话自有D/sonic_grasp.py、adaptive_hand.py及新增工具；原件hash/权限核验并在work/{T}保留备份。不改vendor/KIMODO/他人文件/共享配置环境，无GPU。
原near两版重复、3.14负对照→8B CPU生成同seed43原文本/新文本→来源清单逐文件NPZ/CSV核对→两版实际执行→500Hz原接触定位→可选1mm桌面目标约束与整循环观察器→原成功轨迹回归→两版约束测试。
资源仍4CPU/物理AS16GiB/300s/90s/45000step/累计3GiB；既有8B生成单独登记AS40/RSS24/285s，两job各100帧，不下载新权重。流水含全部启动/失败：logs/{T}/steps.md。

## 三、实测证据

{chr(10).join(rows)}

原near重复3.2.7的1491帧8类数组精确一致；3.14物理qpos/qvel/decoder/扭矩等精确一致，但body_reference有8.764e-10rad级差，不能写成8类全字节一致。确定性复现≠随机鲁棒成功率。
原near.text与旧reach_s43.prompt逐字相同，journal#2322作废/更正#2320的不同文本说法，旧报告/档案不回改。新两段生成same seed43，原文本重生成NPZ同旧reach43 hash、qpos精确一致；新文本右臂姿态最大变化{binding['newtext_vs_control']['right_arm_max_delta_rad']:.6f}rad。源角色合并JSON明确只是两次生成的逐job来源索引，不伪造单次新生成或聚合冷时延。
实际8B冷文本编码器加载{generation['cold_textencoder_load_s']:.1f}s、动作模型加载{generation['motion_model_load_s']:.1f}s，两温job={generation['warm_jobs_s']}s、整进程{generation['wall_process_s']:.3f}s、peakRSS={generation['peak_rss_MiB']:.1f}MiB。不能把2.55s称整链实时响应。
3.2.7原文本seed43的LIFT46.042–47.698s碰桌来自thumb/middle pads，全程合力峰4.692580N；HOLD仍达114.334mm/滑移3.886mm，却被严格桌接触门拒绝。桌面约束只投影手指IK目标到table_top+pad_radius+1mm且保留对向cube face边界，不改碰撞mask/物体/扭矩门；几何目标不自动成为动态避碰证明。
计时/default投影整理在原near3.2.7回归：1491帧8数组精确一致；完整周期median36.502ms/p95{lat['p95_ms']:.3f}ms/max{lat['max_ms']:.3f}ms；policy-only p95=17.310ms不代表整个20ms周期合规。零pacing观察、不称浏览器播放为实时仿真。
桌面约束对照核对：3.2.7约束前后1500帧8数组精确一致；3.14物理/decoder/手指/扭矩1510帧精确一致，仅body_reference差2.321e-9rad。设置1mm参数并不代表投影已改变实际指令，因此不写“防碰桌解决”。几何与计时模块在服务器实跑5+10个正反测试通过，只证明这些单元分支，不代表物理效果。
所有物理原始JSON/NPZ/接触/模型内有版本、env、权重/源码/模型sha与dt；结果由官方SONIC身体decoder执行，手指是独立任务控制，不由ARDY输出。G1来自官方模型但有任务pad/摩擦/碰撞适配，不等于实机参数完全相同。

## 四、失败项与原因

新文本两版原文`native branch static search rejected: No candidate passes static capture/hand/limits/open-table filters`，不擅自放宽阈值。零步诊断使用最后保存17.602s状态，距live17.620s差18ms，属于近似静态重查；部分分支手指误差3.5–3.7mm超1.5mm，另有关节裕量/姿态/桌间隙失败，不能当实时停止状态或动态成功证据。
seed43原文字两版legacy通过但strict=false，失败`no_robot_table_contact_full_task`；新手指目标约束失败（若有）见上表及各原result.fail_reason/gates，不拿后来的改善覆盖旧失败。
第七波初登记writer在stderr成功journal#2319，stdout-only检查误抛AssertionError，状态仍wave6且物理未启动；查原回执后恢复，不重复start，#2320作废#2319提前部署声明，后#2322更正文本归因。失败日志保留。
保护性代码改动：`--ardy-off`与所选ARDY帧branch seeding同时启用设为拒绝，不让保留源分支的部分消融冒充完全off；该组合尚未另做实际CLI闸门测试，也未构成ARDY必要性证明。
整链实时性明确失败；用户动作纠正仍0（未收到动作纠正输入），人工参数设定不能冒充纠正。SETDOWN尚未补测、全身COM/COP/腿速度/视觉/实机未验证。新手指约束只是本参数族检验，未证明未见物体泛化或真实force closure。

## 五、下一步建议

先分析1mm约束的实际接触/抓持结果，增加同新代码关闭约束的严格匹配对照，再做真正新文本可达性改进；保持源文本/seed/branch/job可审计，不仅改文件名。
保留原成功组以检验contact-qualified SETDOWN，增加连续对向夹持到桌面承重的证据，防止中途掉落后最终落桌被误算受控放置。
以实际周期统计定位参考/IK/物理/审计开销，任何加线程/缓冲日志的优化先做保存轨迹回归，不把冷模型加载藏掉。只有收到用户具体动作纠正才做纠正试验并计数；实机/公开服务需另授权。

## 六、复现方法

```bash
D=/data/group4/{T}
ENTRY=/home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh
bash "$ENTRY" status
# 当前7波余10槽；只用未占用的w7_NEW名字，不能重跑上表名字或绕过预算闸
# 参考通用成功配置：strict-execution/finger-gain3/grip-preload-mm1.5/table-front.24/lift-height.15
# reference-fallback/grip-frame-lift/direct-table/adaptive-hand/kinematic-servo/pinch-geometry
# flat-pinch/surface-capture/phase-clips/capture-radius.007/c2-reference/endpoint-seed/endpoint-seed-native
# contact-close/contact-entry-dwell.04/gravity-arm1/opponentmiddle/close-seconds.5
# neutral-shoulder-offset.2/clearance-approach/clearance-native-branch/clearance-branch-servo
# --motion-profile out/w7-source-binding/control-profile.json 或 newtext-profile.json
# 可选--finger-table-clearance-mm1；默认0保持原目标投影
# PYTHONPATH="$D/mujoco314-only"只切另一MuJoCo包，env/NumPy/ORT不升级
```
压缩包含十次全部原始失败/成功及源码快照/生成来源/比较/流水截止；不打包现有权重/环境，复现依赖相同D/官方G1资产与既有环境，其运行时哈希在结果中。报告、摘要和压缩包均须下载本地并比SHA，再显式own-path Git；后续回执不回写不可变包。
'''
summary_path.write_text(json.dumps(summary,indent=2)+'\n');report.write_text(text)
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 FIRST10 IMMUTABLE CHECKPOINT] '+now+'\n-10 launches exited; wave still ACTIVE,10 slots remain. True text pair failures and actual timing preserved, no complete Track4/real-time/user correction claim.\n-Report='+str(report)+'; source/data/archive stay owned.\n')
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
shutil.copy2(summary_path,W/summary_path.name)
included=[D/'source-snapshots',D/'wave7-launches.jsonl',D/'active_cpu_wave.json',summary_path,report,L,
    B/f'ardy-grasp-run-{T}.sh',D/'out/w7-generated-text',D/'out/w7-source-binding',D/'out/generated_phases2']
included += [D/'out'/row['name'] for row in records]+list((D/'out').glob('w7-*'))
included += [path for path in D.iterdir() if path.is_file() and path.suffix in {'.py','.sh'}]
included += [path for path in W.iterdir() if path.is_file() and (path.name.startswith('rules-read-') or path.name.endswith('before-wave7-table') or path.name.startswith('wave7-'))]
included=list(dict.fromkeys(included))
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
upper=sum(path.stat().st_size for base in included for path in ([base] if base.is_file() else base.rglob('*')) if path.is_file() and not path.is_symlink())
assert actual+upper+16*1024**2<3*1024**3 and shutil.disk_usage(D).free>upper+30*1024**3
with tarfile.open(bundle,'w:gz',dereference=False) as tar:
    for path in included:
        arc=str(path.relative_to(D)) if path.is_relative_to(D) else 'checkpoint-logs' if path==L else 'owned-project/'+str(path.relative_to(B))
        tar.add(path,arcname=arc)
manifest={str(path):sha(path) for path in [report,summary_path,bundle]}
(W/'wave7-progress1-archive.sha256').write_text(''.join(digest+'  '+path+'\n' for path,digest in manifest.items()))
print(json.dumps(dict(manifest=manifest,completed_launches=10,remaining_slots=10,task_active=True,
    archive_upper_bytes=upper,pre_archive_bytes=actual,bundle_bytes=bundle.stat().st_size),indent=2))
