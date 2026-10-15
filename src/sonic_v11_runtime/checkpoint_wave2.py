"""Immutable second-wave evidence checkpoint; broader claim stays ACTIVE."""
import datetime,hashlib,json,shutil,tarfile
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (D/'wave2.tar.gz').exists()
names=['hybrid_sonic01','hybrid_teleop01','native_geometry_g101','native_pinch01','native_pinch_comp01','native_capture22_on','native_capture22_cart','native_flat_current01','native_c2_flat01','native_policy_aware01','native_branch_seed01','native_gain2','native_gain4','native_anchor_free','native_anchor_fixture','native_anchor_fixture2','native_incremental_anchor','native_incremental_accum','native_fk_servo1','native_fk_servo2']
records=[]
for name in names:
 p=D/'out'/name/'result.json'
 if not p.exists():
  assert name=='native_anchor_fixture';records.append(dict(name=name,scene_setup_failed=True,physical_steps=0,reason='XML free joint uses <joint type=free>, not <freejoint>; failed assertion before stepping; retained'))
  continue
 r=json.loads(p.read_text());st=r['runtime_stamp'];records.append(dict(name=name,sha256=sha(p),version=st['mujoco_version'],success=r['success'],fixture=r.get('base_fixture',False),fail_reason=r['fail_reason'],duration_s=r['duration_s'],max_lift_m=r['max_lift_m'],hold_min_lift_m=r['hold_min_lift_m'],max_drift_m=r['max_drift_m'],position_error_m=r['final_wrist_position_error_m'],pad_vertical_spread_m=r.get('final_pad_vertical_spread_m'),virtual_reference_rms_rad=r['right_arm_tracking_rms_rad'],motor_target_rms_rad=r.get('actual_to_decoded_motor_target_rms_rad'),phases_consumed=r.get('phase_clips_consumed',[]),kind=r['kind']))
summary=dict(task=T,task_active=True,wave=2,physical_script_launches=20,physics_episodes=19,scene_setup_failures=1,permission_denied_before_script_launches=2,results=records)
(D/'wave2-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
table='| 测试 | 底座夹具 | 成功 | 手位置误差m | 峰值抬升m | 失败原因 |\n|---|---|---|---:|---:|---|\n'
for r in records:
 table+='| '+r['name']+' | '+str(r.get('fixture','未启动'))+' | '+str(r.get('success',False))+' | '+(f"{r['position_error_m']:.6f}" if 'position_error_m' in r else '-')+' | '+(f"{r['max_lift_m']:.6f}" if 'max_lift_m' in r else '-')+' | '+str(r.get('fail_reason',r.get('reason')))+' |\n'
report=f'''# ARDY→官方SONIC参考适配：第二波检查点
- task={T}；{datetime.datetime.now().astimezone().isoformat()}；任务仍ACTIVE。

## 一、结论

本波20次物理脚本启动，其中19次进入物理步进、1次场景断言失败；不超过登记的20次上限。Track4抓取目标尚不因本报告而完成，成功与失败逐条保留。
文本生成了4条新ARDY动作，但“生成/加载”不代表已进入抓取抬升阶段；实际消费阶段列在JSON中。
全部正常身体通道来自官方SONIC1751/994；手指单独控制。固定底座分支仅把pelvis固定到世界，不约束物体，不代替自由底座稳定性评估。

## 二、操作步骤

保留原near_s42 NPZ与vendor CSV对拍，加入几何夹持点适配、仿真状态物体定位（非视觉）、新生成lift/hold/release分阶段输入、关节C2滤波、冻结观察的SONIC输入探测、参考反积分风up对照、实际姿态增量线性化与几何外环；右臂增益1/2/4对照保持解码目标和原始力矩上限。后续每次执行前保存脚本SHA命名的不可变副本，详见source-snapshots与logs/{T}/steps.md。
资源：物理4核/AS16GiB/每命令300s/每集90s；文本生成独立登记40GiB虚拟地址、24GiB RSS监控、4核、285s硬上限，无GPU/训练/下载/共享环境写入。

## 三、实测证据

以下所有物理读数均为MuJoCo3.2.7，不能外推到3.14。逐条JSON/CSV/NPZ均有版本、解释器、场景/源/权重SHA。

{table}

文本生成4条4秒/100帧/25fps NPZ：reach_s43、lift_s42、hold_s42、release_s42；关节CSV对拍≤1.192e-7rad，无原始关节超限。冷载文本编码68.8s，整体85.62s、峰值RSS14894.7MiB，各条生成约2.8–3.2s。lift原生成手的Z净变化22.67mm，不直接等同抓取抬升；后续10cm抬升时间归一化是明确的任务适配。
C2解析极值门控8项/150次重规划通过，v≤.6rad/s、a≤1.5rad/s²、jerk≤12rad/s³，边界跳变0；冻结观察探测5项、PD接口5项、实际姿态增量探测5项通过。单测不证明抓取成功。
已保存状态的离线检查（零物理步进）发现：关闭前方块会被碰离小支撑柱，原固定坐标已不适用；默认手腕还会接触桌边。原absolute motor-target FK线性化与实际手的位置明显不同；新增motor-target与raw motor-target记录后可区分参考误差和实际执行误差。

## 四、失败项与限制

早期不带不可变执行副本的wave2前四条仍有结果指纹与原始日志，但不宣称能仅凭现行源文件复跑；当时源版本未全部保存。后续执行有source-snapshots。
native_flat_current01中的final_wrist_rotation_error_rad实际记录的是pad高度差（米），orientation_error_metric已说明单位；后来字段改成final_pad_vertical_spread_m。旧结果不回改、不与弧度混比。
首次文本生成子进程preexec尝试提升父进程已有16GiB硬地址限制失败；未开始生成。登记生成例外后重新运行新目录成功。
本轮两次直接运行run.sh报Permission denied（未设执行权限，未进入脚本），改用bash解释器启动；不改变共享或源文件权限。固定底座首个场景断言AssertionError，因为原XML自由关节是joint type=free而不是freejoint；原失败目录保留，新名称重试。
未使用物体焊接/瞬移、外部施力或手臂目标覆盖；机器人底座夹具是显式场景约束，不能把它算作SONIC平衡成绩。用户纠正次数0仅指没有交互式文本纠正，不代表没有人为预设几何/阈值/任务适配。
第二方法、Archon预约/监督实机观摩、报告/演示公开发布仍需小组与人类配合，不介入KIMODO，不上传权重/凭据。

## 五、下一步建议

保持任务ACTIVE，双端SHA归档和仅自有路径Git检查点后另登记下一波≤20次CPU试验。围绕真实两指接触继续诊断，先保证路径不穿桌、实际姿态闭环和预夹持姿态，再测试闭手、保持和释放。成功后重复/关闭夹持/关闭触垫/两个版本对照；没有成功就保留可复现失败和Track4规定的针对性比较，而不作完成断言。

## 六、复现方法

```bash
D=/data/group4/{T}
# 使用登记的资源限制，并换新输出名，避免覆盖证据
bash "$D/run.sh" "$D/sonic_grasp.py" NEW_NAME --pinch-geometry --flat-pinch --phase-clips --capture-radius .022 --c2-reference --kinematic-servo --endpoint-seed --endpoint-seed-native --fixed-base
```

wave2.tar.gz包含源代码历史副本、新生成NPZ、本波场景/轨迹/数字及报告；基础机器人网格/原NPZ/官方配置见已双端验证的wave1.tar.gz。SONIC权重和运行库不打包，来源/许可/SHA见sonic-setup.json；不得据此公开分发限制权重。缺新目录或解释器依赖时遵循setup_sonic.py/原有环境只读约定，不改共享环境。
'''
rp=B/'reports'/f'{T}-wave2-report.md';assert not rp.exists();rp.write_text(report)
for p in D.iterdir():
 if p.is_file() and p.suffix in ['.py','.sh']:shutil.copy2(p,W/p.name)
shutil.copy2(D/'wave2-summary.json',W/'wave2-summary.json')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE2 CHECKPOINT]\n- 20 script launches (19 physics episodes, one scene setup assertion failure); all exited.\n- Two direct run.sh invocations failed Permission denied before launching; retried via bash, permissions unchanged.\n- Source snapshots begin after the first four wave2 hypotheses. Early source-reconstruction limitation and flat-pinch units erratum declared in report.\n- Goal remains ACTIVE; no success inferred from clip generation/loading or fixed-base fixture.\n')
with tarfile.open(D/'wave2.tar.gz','w:gz') as tar:
 for p in sorted(D.iterdir()):
  if (p.is_file() and p.suffix in ['.py','.sh']) or p.name in ['source-snapshots','wave2-summary.json']:tar.add(p,arcname=p.name)
 for name in names+['generated_phases2']:
  tar.add(D/'out'/name,arcname='out/'+name)
 for p in sorted((D/'out').glob('*.json')):tar.add(p,arcname='out/'+p.name)
 tar.add(rp,arcname=rp.name);tar.add(L/'steps.md',arcname='checkpoint-steps.md')
manifest={str(rp):sha(rp),str(D/'wave2.tar.gz'):sha(D/'wave2.tar.gz')}
(W/'wave2-archive.sha256').write_text(''.join(v+'  '+p+'\n' for p,v in manifest.items()))
print(json.dumps(dict(manifest=manifest,summary=summary),indent=2))
