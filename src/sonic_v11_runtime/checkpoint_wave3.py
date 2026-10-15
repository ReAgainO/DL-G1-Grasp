"""Third wave immutable evidence checkpoint; claim and goal remain ACTIVE."""
import datetime,hashlib,json,shutil,tarfile
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
bundle=D/'wave3.tar.gz';assert not bundle.exists()
names=['w3_contact_close','w3_more_align','w3_surface1','w3_surface_contact','w3_touch40_live','w3_touch40_hold','w3_gravity_half','w3_gravity_full','w3_middle_slow','w3_middle_fast','w3_teleop_fk','w3_teleop_cart','w3_discrete_inc','w3_discrete_abs','w3_direct_fk','w3_direct_discrete','w3_adaptive_hold','w3_adaptive_live','w3_grip_frame','w3_lock_grip']
records=[];source_missing=[]
for name in names:
 p=D/'out'/name/'result.json';r=json.loads(p.read_text());st=r['runtime_stamp']
 records.append(dict(name=name,result_sha=sha(p),version=st['mujoco_version'],success=r['success'],gates=r['gates'],duration_s=r['duration_s'],wall_s=r['wall_s'],max_lift_m=r['max_lift_m'],hold_min_lift_m=r['hold_min_lift_m'],hold_slip_m=r['hold_slip_m'],hold_min_contact_bodies=r['hold_min_contact_bodies'],motor_rms_rad=r.get('actual_to_decoded_motor_target_rms_rad'),final_position_error_m=r['final_wrist_position_error_m'],phases_consumed=r.get('phase_clips_consumed',[]),fail_reason=r['fail_reason']))
 for filename,h in [('sonic_grasp.py',st['scene_generator_sha'])]+[(key+'.py',value) for key,value in st['library_sha'].items() if key in ['sonic_v11','reference_filter','motion_input','grasp_geometry','policy_reference','discrete_reference','adaptive_hand']]:
  if not (D/'source-snapshots'/h/filename).is_file():source_missing.append(dict(episode=name,file=filename,sha=h))
summary=dict(task=T,wave=3,task_active=True,physical_script_launches=20,physics_episodes=20,successes=sum(v['success'] for v in records),source_snapshot_missing=source_missing,results=records)
(D/'wave3-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
table='| 测试 | 峰值抬升 mm | HOLD最低抬升 mm | 成功 | 原因 |\n|---|---:|---:|---|---|\n'
for r in records:table+=f"| {r['name']} | {r['max_lift_m']*1000:.3f} | {r['hold_min_lift_m']*1000:.3f} | {r['success']} | {r['fail_reason'] or '完成阶段序列但保持门未通过'} |\n"
report=f'''# ARDY→官方SONIC物理抓取：第三波检查点
- task={T}；{datetime.datetime.now().astimezone().isoformat()}；任务与目标仍ACTIVE。

## 一、结论

本波20次启动均进入物理步进并退出，严格完整成功0/20（MuJoCo3.2.7）。末次w3_lock_grip首次持续夹住：HOLD最低抬升42.941mm、全段至少2指接触、无桌面支撑、相对腕滑移3.080mm、释放下落与落回桌面通过；但未满足HOLD最低70mm和最低离桌40mm，因此不作Track4完成或成功率正值断言。峰值132.734mm不能替代全保持段最低值。

## 二、操作步骤

保留原near_s42 NPZ直接转换及25fps对拍；几何姿态约束→C2参考→官方1751/994 SONIC→原始力矩限位的PD执行。尝试物理表面接触点、单指入闭合门、接触驻留、静态模型重力前馈0/.5/1、thumb/index或thumb/middle、闭指时冻结参考、官方三点VR模式、冻结观察离散候选参考搜索。全部身体位置目标来自官方SONIC，没有脚本IK目标直接送电机；重力前馈是显式的非原厂执行器适配。
随后增加独立手指相对面IK（1.5rad/s命令限速、原手指力矩上限），抬升时使用真实捕获腕姿态的完整位置/方向参考，最后保持已捕获手指命令（不是物体约束）。ARDY没有输出手指，这一部分不能归因于原生ARDY。
direct-table对照移除35mm窄柱，将宽桌面top从.725提高至.757、前沿从.20移至.23；方块初始高度保持.7745，落盘XML/零步进预检保留。物体始终有自由关节、真实碰撞，无weld/adhesion/位置更新/外力；仅机器人pelvis可显式固定于世界。这种夹具结果不代表全身平衡通过。

## 三、实测证据

{table}

原NPZ4帧×7关节的冻结观察扰动：0.001rad的28次探测有27次编码完全不变，.03rad有3次不变；实测输出值落在1/16网格。quantization-scan.json中的quarter-grid residual=.5表示四分之一网格假设不成立；此前两帧最大token差=.25不是量化步长。官方架构FSQ出处：[NVIDIA训练架构](https://github.com/NVlabs/GR00T-WholeBodyControl/blob/main/docs/source/references/training_code.md)。这证明本版小扰动存在编码死区，不证明所有抖动都来自量化；离散搜索本轮未取得抓取成功。
新零步进检查：原NPZ/CSV时钟与负样本17项、表面接触Jacobian40项（最大差1.626e-8）、重力执行器6项、原NPZ三点VR映射6项、离散参考4项、direct-table模型6项、独立手指4项均通过。初次面中心手指约束扫描最佳13.2mm，改相对面可接触区域后最佳2.066mm；这些不是物理抓取成绩。
w3_adaptive_live首次进入全阶段，实测拇指+中指闭合持续约.2s，LIFT最长连续双指约.784s，总2.134s，峰值66.756mm后掉落，HOLD接触0。w3_grip_frame峰值74.992mm仍掉落；w3_lock_grip在相同捕获过程后保持手指指令，HOLD双指/无支撑/3.08mm滑移/释放通过，但高度不够。
后三项确实消费generated_phases2的lift_s42/hold_s42/release_s42，前17项无消费；loaded与consumed分开。ARDY文本段原始Z幅度、10cm单调归一化、几何零空间先验等任务适配均显式记录，不冒充未经适配的原生生成成功。

## 四、失败与限制

全部本波物理结果仅3.2.7，尚无同组3.14因果对照。固定pelvis、仿真真值物体定位、预设环境/约束不是完整实机与视觉流程；无交互式用户纠正不等于零人工设置。
两次teleop-FK在12.64s轨迹可行性停止，保留失败；延长对准在53.62s可行性停止。C2参考门不回退为强行裁剪。
计算时延中policy_median/p95仅常规encoder+decoder调用，不含候选搜索、物理步进与其他处理，不能据此宣称浏览器/机器人实时闭环。总wall与模拟时长逐条保留。
source_snapshot_missing共有{len(source_missing)}项（详见wave3-summary.json），不得未经核对宣称全部源可重建。执行前源快照与运行指纹均保留。
初次表面Jacobian符号在盒面非光滑点失败，修正使用对称零次梯度后通过；旧失败日志保留。CLI后来改具名传参避免长位置参数错位，语法预检通过。纯零步进scan/test不计物理20次额度；初始模型prepare仅用于读取旧校准几何，不算本组物理episode。

## 五、下一步

双端SHA归档后登记第四波≤20次CPU试验；优先抑制持续抓取后的手臂高度波动，独立增加KD而不先抬KP，检查机器人惯量/阻尼与官方动力学配置的一致性。保持标准不降级，成功后重复、关手/关触垫、3.2.7与3.14双版本，再检查自由底座。第二生成方法、Archon观摩、公开发布仍由人类/团队配合，不介入KIMODO。

## 六、复现

```bash
D=/data/group4/{T}
bash "$D/run.sh" "$D/sonic_grasp.py" NEW_NAME --lock-grip --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --fixed-base --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5
```

当前源码就是w3_lock_grip版本；旧变体以runtime_stamp SHA选不可变源，不能拿最新脚本冒充旧版本。wave3 bundle包含本波20组场景/轨迹/数字、源码快照、零步进检查、日志/报告；原资产/原NPZ见wave1，新文本生成NPZ见wave2。权重不打包、不公开重分发。
'''
rp=B/'reports'/f'{T}-wave3-report.md';assert not rp.exists();rp.write_text(report)
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE3 CHECKPOINT]\n-20/20 physical launches exited, strict successes0; lock-grip HOLD42.941mm,2 fingers,no support,slip3.080mm; NOT complete.\n-CLI long positional arguments converted to named options, ast syntax passed; temporary dead conditional was removed before any remote execution.\n-Snapshot missing items='+json.dumps(source_missing)+'\n')
for p in D.iterdir():
 if p.is_file() and p.suffix in ['.py','.sh']:shutil.copy2(p,W/p.name)
shutil.copy2(D/'wave3-summary.json',W/'wave3-summary.json')
included=[p for p in D.iterdir() if p.is_file() and p.suffix in ['.py','.sh']]+[D/'source-snapshots',D/'wave3-summary.json']+[D/'out'/n for n in names]+list((D/'out').glob('*.json'))+[D/'out/direct-table-preflight',rp,L/'steps.md']
def total(paths):return sum(p.stat().st_size for path in paths for p in ([path] if path.is_file() else path.rglob('*')) if p.is_file())
current=total([D]);upper=total(included)
assert current+upper+16*1024**2<1024**3,('Conservative archive peak exceeds scope',current,upper)
with tarfile.open(bundle,'w:gz') as tar:
 for p in included:
  tar.add(p,arcname=str(p.relative_to(D)) if p.is_relative_to(D) else 'checkpoint-steps.md' if p==L/'steps.md' else p.name)
manifest={str(rp):sha(rp),str(bundle):sha(bundle)}
(W/'wave3-archive.sha256').write_text(''.join(v+'  '+p+'\n' for p,v in manifest.items()))
print(json.dumps(dict(manifest=manifest,summary=summary,estimated_prearchive_bytes=current,conservative_bundle_upper_bytes=upper),indent=2))
