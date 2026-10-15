"""Immutable incremental checkpoint; prior first-ten archive remains intact."""
import datetime,json,shutil,subprocess,tarfile
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert json.loads((D/'active_cpu_wave.json').read_text())['wave']==7
launches=[json.loads(line) for line in (D/'wave7-launches.jsonl').read_text().splitlines()]
assert 17<=len(launches)<=20 and len({r['name'] for r in launches})==len(launches)
ps=subprocess.check_output(['ps','-eo','args'],text=True).splitlines();assert len(ps)<20000
assert not any(str(D) in row and any(n in row for n in ['/sonic_grasp.py','/phase_generate_entry.py']) for row in ps)
report=B/'reports'/f'{T}-wave7-progress2-report.md';summary_path=D/'wave7-progress2.json';bundle=D/'wave7-progress2.tar.gz'
assert not any(p.exists() for p in [report,summary_path,bundle])
prior={str(D/'wave7-progress1.tar.gz'):'e569b85ce382258df50ab78665035b21341e965e5cbc77269a0098006de54a9d',
 str(D/'wave7-progress1.json'):'f2f4c2b43ba07a79acd5f733d91ac161e75680210f089c2d4446437ecafdb4b9'}
for name,value in prior.items():assert sha(Path(name))==value
records=[]
for launch in launches[10:]:
 folder=D/'out'/launch['name'];p=folder/'result.json';assert p.is_file() and p.stat().st_size<512*1024
 r=json.loads(p.read_text());stamp=r['runtime_stamp']
 for key,name in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert sha(folder/name)==stamp['model_sha'][key]
 sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]+[(k+'.py',v) for k,v in stamp['library_sha'].items() if (D/(k+'.py')).is_file()]
 for name,value in sources:assert sha(D/'source-snapshots'/value/name)==value,(launch['name'],name)
 assert not r['body_action_override'] and not r['base_fixture'] and r['peak_external_force']==0 and r['user_corrections']==0
 keys=['success','gates','duration_s','wall_s','fail_reason','hold_min_lift_m','hold_slip_m','execution_audit',
 'balance_audit_summary','source','motion_profile','user_corrections','no_grip','setdown_enabled',
 'execution_cycle_latency','post_clearance_native_branch','post_clearance_branch_servo','branch_face_alignment_enabled','face_aligned_servo']
 records.append(dict(launch=launch['launch'],name=launch['name'],runtime_stamp=stamp,result_sha256=sha(p),trajectory_sha256=sha(folder/'trajectory.npz'),**{k:r.get(k) for k in keys}))
diagnostics={p.name:dict(path=str(p),sha256=sha(p)) for p in sorted((D/'out').glob('w7-*.json'))}
default=json.loads((D/'out/w7-facecode-default-regression327.json').read_text());assert all(v['exact'] for v in default['arrays'].values())
placing={ver:json.loads((D/'out'/f'w7-setdown-audit{ver}-v2.json').read_text()) for ver in ['327','314']}
assert all(not r['controlled_placing_observed'] and r['release_s'] is None and r['table_min_last200ms_before_release_N'] is None for r in placing.values())
now=datetime.datetime.now().astimezone().isoformat();remaining=20-len(launches)
summary=dict(task=T,wave=7,cutoff=now,total_launches=len(launches),incremental_results=records,remaining_slots=remaining,
 task_active=True,full_track4_complete=False,real_robot_ready=False,human_corrections_received=0,
 prior_archive_dependencies=prior,diagnostics=diagnostics,
 scope='Heterogeneous static diagnostics, default-off regression, two-version SETDOWN failures and fresh-text face alignment/servo tests; not a homogeneous success rate.',
 controlled_placing_validated=False,default_off_regression=default)
rows=['|启动|测试|版本|HOLD最低mm|滑移mm|全程碰桌N|严格通过|','|---:|---|---|---:|---:|---:|---|']
failures=[]
for r in records:
 height='无HOLD窗' if r['hold_min_lift_m']==-1 else f"{r['hold_min_lift_m']*1000:.3f}"
 slip='无HOLD窗' if r['hold_slip_m']==1e9 else f"{r['hold_slip_m']*1000:.3f}"
 rows.append(f"|{r['launch']}|{r['name']}|{r['runtime_stamp']['mujoco_version']}|{height}|{slip}|{r['balance_audit_summary']['robot_table_all_max_normal_N']:.6f}|{r['success']}|")
 if not r['success']:failures.append(f"- {r['name']} ({r['runtime_stamp']['mujoco_version']}): fail_reason=`{r['fail_reason']}`; gates="+','.join(k for k,v in r['gates'].items() if not v))
servo=[r for r in records if (r.get('face_aligned_servo') or {}).get('enabled')]
servo_text='；'.join(r['runtime_stamp']['mujoco_version']+':strict='+str(r['success'])+',calls='+str(r['face_aligned_servo']['calls']) for r in servo)
text=f'''# 第七波增量检查点：静态face匹配、动态朝向控制和受控放置失败审计
- codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；task={T}；截止{now}，总启动{len(launches)}/20，余{remaining}槽；总目标ACTIVE。

## 一、结论

有条件能：原near成功路径的默认关闭回归在3.2.7中1491帧8类数组逐值完全一致；不同文本的静态face匹配在两版实际运行中进入闭手阶段，不能由此宣称抓取成功。
持续face朝向servo实测：{servo_text}。完整物理验收结果见表，不挑版本，不把mixed tests汇总为成功率。
受控放置两版失败；整链20ms实时周期未达标；用户动作纠正0、视觉、全身COM/COP和实机未完成，不称基本Track4已经完成。

## 二、操作步骤

用户授权改进直接上传，但不改他人文件。只更新本会话自有sonic_grasp/native_branch/branch_face_ik/audit_setdown及新工具；旧SHA/权限备份在work/{T}，官方SONIC和他人源码/权重/环境/配置未改，无GPU。
零物理步诊断20静态候选→有限差分refinement失败保留→两版SETDOWN→桌面投影诊断→cube-face yaw匹配/20.05mrad参数化优化→默认关闭回归→两版新文本静态face实跑→25Hz实际/reference朝向诊断→可选5Hz持续face servo及前缀配对检查。
全部physics通过task-named入口/run.sh/原子启动计数，4CPU/AS16GiB/300s/45000步/90s仿真/累计3GiB；静态与诊断各有采样/迭代硬上界。流水logs/{T}/steps.md保留失败、修复、资源与出处。

## 三、实测证据

{chr(10).join(rows)}

新文本与原control同seed43但实际文本不同、NPZ右臂最大差0.478022rad；源与生成冷/温时延证据在不可变progress1档案。near与旧reach43同文本仍非泛化证据。输入是ARDY混合重定向，不是原生ARDY直接夹持，手指独立控制，物体来自仿真状态而非视觉。
静态20候选与实际预压匹配均不能通过原筛选；有限差分3候选也没有达门限。cube-face yaw匹配后frame0/19可静态通过，但saved17.602s距live17.620s差18ms，只是近似静态诊断。真实live两版均选frame19，原七候选/手指1.5mm/capture1mm/OPEN桌间隙10mm/关节裕量20mrad门没有降低。
旧face-only实际两版strict=false，碰桌峰1.889260/1.820551N。3.2.7闭手超时，3.14虽跑完但物体未抬起（HOLD最低-0.046mm/滑移27.833mm）。25Hz虚拟CLOSED几何检查显示接近末朝向误差0.372/4.153度，闭手起33.683/44.508度；reference同样偏离，提示朝向约束在下降阶段丢失，但该观察本身不是因果证明。
新face servo默认关闭，只在PREGRASP/DESCEND/ALIGN/CLOSE的5Hz虚拟输入IK保持所选物体face轴；单call15迭代/最多450call/参考修正0.06rad/C2边界保持。SONIC仍解码全29身体目标，不写actual qpos/qvel/物体/外力，不改接触mask或安全成功条件；profile/source/runtime hash与真实调用记录保留于各result。
SETDOWN两版夹持间断最大0.156/0.160s、落桌前腕相对滑移122.002/128.074mm；未进入RELEASE。最终落桌不是受控放置，旧审计无RELEASE时误把停止前200ms字段叫before_release，journal#2345及新v2明确更正：before_release=null，at_stop另记；原v1不覆盖。
桌面投影FK诊断仅复查25Hz91/87状态、用虚拟command seed，不是实际10Hz求解调用复放，更不能由“有投影”断言防碰桌已生效。3.14采样漏过实际500Hz接触；之前floor1mm两版8类数组无有效变化的失败仍成立。
所有结果保留版本3.2.7/3.14.0、env、模型/权重/代码sha与dt；官方模型有任务pad/摩擦/碰撞适配，不等于实机完全同参数。抓力>0.01N仅积极接触观察，不冒充团队更强的各对向指>块重或force-closure认证。

## 四、失败项与原因

{chr(10).join(failures)}

第一次face扫描遇`ValueError: Degenerate horizontal pad direction`，两版原日志保留；修复为逐候选拒绝记录，未测度量为null，不以零值假通过。静态优化默认与运行时动态控制区别如上。
refinement原登记arm调用上界少算，journal#2338以voids更正#2337为最多9*15迭代；未启动无界循环。更正原before_release命名不改变物理读数、不抹除旧失败。
整循环延迟仍超过20ms，静态搜索同步峰时延也计入循环；不把policy-only时延或浏览器回放称实时闭环。人工参数调整不是用户动作纠正；目前未收到真正纠正输入。

## 五、下一步建议

只依据两版新servo实际结果决定后续：若仍失败，先逐阶段核对实际/参考朝向、手指误差与500Hz碰桌contact；不能靠放宽成功门、固定base、写物体状态或调整质量获得假成功。
受控放置必须保留连续夹持至桌面承重的500Hz证据，再考虑RELEASE；当前两个失败不可算成功放置。下一步可对比SETDOWN实际身体参考/decoder是否因hold prior与逐秒腕目标冲突导致夹持失稳。
先保持原成功路径，对任何速度/日志优化做同输入逐数组回归；收集真人明确纠正后才测试纠正闭环。实机、公开视频、团队另一方法均需相应授权。

## 六、复现方法

```bash
D=/data/group4/{T}
ENTRY=/home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh
bash "$ENTRY" status
# 所有物理必须经入口；新名称w7_NEW只能在剩余{remaining}个登记槽内使用。
# 实际已用命令从wave7-launches.jsonl和logs/{T}/steps.md查，不复用旧输出名。
# 新文本profile：out/w7-source-binding/newtext-profile.json
# face-only：--branch-face-alignment；持续servo另加--face-aligned-servo，默认均关闭。
# PYTHONPATH="$D/mujoco314-only"切到3.14.0，既有env/NumPy/ORT不升级。
# 只读保存轨迹审计：
bash "$D/run.sh" "$D/show_wave7_trial.py" w7_faceservo_newtext327 w7_faceservo_newtext314
```
本增量包保存第11次之后的所有原始成败、当前own源码、source-snapshots、诊断、备份、流水截止；前十次及生成源依赖progress1包SHA=e569b85ce382258df50ab78665035b21341e965e5cbc77269a0098006de54a9d，两包联合才是完整Wave7档案。大权重/共享env不打包，运行时hash在原result；仍依赖可访问的相同G1/权重/env。所有报告/摘要/包须本地下载SHA验证；Git结论与最终尾日志独立归档，不回写不可变包。
'''
with summary_path.open('x') as f:f.write(json.dumps(summary,indent=2)+'\n')
with report.open('x') as f:f.write(text)
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 INCREMENTAL IMMUTABLE CHECKPOINT] '+now+'\n-Total '+str(len(launches))+' exited; ACTIVE; report='+str(report)+'; dependencies progress1 unchanged; raw failures preserved.\n')
for p in D.iterdir():
 if p.is_file() and p.suffix in {'.py','.sh'}:shutil.copy2(p,W/p.name)
shutil.copy2(summary_path,W/summary_path.name)
included=[D/'source-snapshots',D/'wave7-launches.jsonl',D/'active_cpu_wave.json',summary_path,report,L,B/f'ardy-grasp-run-{T}.sh']
included += [D/'out'/r['name'] for r in records]+[p for p in sorted((D/'out').glob('w7-*.json'))]
included += [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py','.sh'}]
included += [p for p in W.iterdir() if p.is_file() and (p.name.endswith('before-facebranch') or p.name.endswith('before-faceservo') or p.name.endswith('before-margin') or p.name.endswith('before-fix') or p.name.startswith('wave7-') and p.suffix in {'.json','.txt'})]
included=list(dict.fromkeys(included));actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
upper=sum(p.stat().st_size for base in included for p in ([base] if base.is_file() else base.rglob('*')) if p.is_file() and not p.is_symlink())
assert actual+upper+16*1024**2<3*1024**3 and shutil.disk_usage(D).free>upper+30*1024**3,(actual,upper)
with tarfile.open(bundle,'x:gz',dereference=False) as tar:
 for p in included:
  arc=str(p.relative_to(D)) if p.is_relative_to(D) else 'checkpoint-logs' if p==L else 'owned-project/'+str(p.relative_to(B));tar.add(p,arcname=arc)
manifest={str(p):sha(p) for p in [report,summary_path,bundle]}
with (W/'wave7-progress2-archive.sha256').open('x') as f:f.write(''.join(value+'  '+p+'\n' for p,value in manifest.items()))
print(json.dumps(dict(manifest=manifest,total_launches=len(launches),remaining_slots=remaining,task_active=True,archive_upper_bytes=upper,pre_archive_bytes=actual,bundle_bytes=bundle.stat().st_size),indent=2))
