"""Archive a completed bounded wave; keep the broader task ACTIVE."""
import datetime, hashlib, json, os, shutil, subprocess, tarfile
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T
W=B/'work'/T;L=B/'logs'/T
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (D/'wave1.tar.gz').exists()
records=[]
for p in sorted((D/'out').glob('*/result.json')):
 r=json.loads(p.read_text());st=r.get('runtime_stamp',{})
 records.append(dict(name=p.parent.name,sha256=sha(p),version=st.get('mujoco_version'),
                     kind=r.get('kind',r.get('method',r.get('attribution',''))),success=r.get('success'),
                     tracking_stage_pass=r.get('tracking_stage_pass'),physical_grasp_established=r.get('physical_grasp_established'),
                     right_arm_tracking_rms_rad=r.get('right_arm_tracking_rms_rad'),max_drift_m=r.get('max_drift_m'),
                     hold_min_lift_m=r.get('hold_min_lift_m'),max_lift_m=r.get('max_lift_m'),fail_reason=r.get('fail_reason')))
(D/'wave1-summary.json').write_text(json.dumps(dict(task=T,task_active=True,physical_episodes_launched=20,
        original_static_episode_json_serialization_failed=True,records=records),indent=2)+'\n')
report='''# ARDY 原始动作与官方 SONIC 执行接口：第一波检查点

## 一、结论

本波20次有界CPU物理试验已退出；总体任务仍ACTIVE，Track4抓取目标未完成。
接通官方SONIC v1.1：1751维编码输入→64维token→994维解码输入→29个身体关节动作；无手臂直接目标覆盖。另行控制手指符合课题允许的分离控制，但本波SONIC动态测试保持张手。
原始 control/near/far_s42 NPZ按25fps直接转换，和原vendor CSV最大关节差≤1.79e-7 rad。未重生成或替换用户原始动作。

## 二、步骤与改动

私有复制官方ONNX与配置；仅自有pydeps增加onnxruntime1.23.2/flatbuffers和现有PyYAML副本，不升级共享环境。新增 sonic_v11.py、sonic_probe.py、test_sonic_v11.py、motion_input.py、ardy_sonic.py；每次运行4核、AS16GiB、300秒超时。各物理产物有runtime_stamp；原始输入来源与SHA另存input-npz-provenance.json。
先测试冷启动、字段布局、负输入及参考开关，再测试自由底座站立与小幅手臂动态，最后接回原始NPZ并比较参考OFF、全身参考、速度和两个MuJoCo版本。

## 三、数字与证据

- 15个SONIC接口测试通过；同输入冷启动逐字节相同；参考变化使token与动作变化。
- 小幅脚本动态参考（不是ARDY）：MuJoCo3.2.7 ON/OFF右臂RMS=0.0373709/0.0492076 rad；3.14.0=0.0402706/0.0480088 rad。两版本未跌倒。
- 原始near_s42、上身投影、速度0.5：3.2.7 RMS0.1099513 rad、漂移0.302359m；参考OFF RMS0.4243703 rad。3.14.0 ON RMS0.1439796rad、漂移0.160944m；本波未做原始动作3.14的OFF，原始动作因果结论仅限定3.2.7。
- 原始near_s42全身参考、速度0.5、3.2.7：RMS0.1041213rad，漂移0.139854m。
- 原始near_s42上身投影、速度0.25、3.2.7：RMS0.0753595rad、漂移0.223092m；接触726 ticks、峰值3.859mm，不构成抓取。跟踪阶段门槛通过不等于物体接近/抓取门槛通过。
- 同最终固定底座人工几何路线的ARDY零空间权重.08与0消融，两版本都抬升成功：3.2.7保持最低84.0118/83.7957mm；3.14.0=83.6345/83.3019mm。因此既有成功不能归因ARDY必要贡献。no-grip/pads-off两版峰值0，表明该固定底座方案依赖真实手指接触。

逐次证据见 /data/group4/20261006-093203-codex-6385a841/out/*/result.json、trajectory.npz、telemetry.csv 与 wave1-summary.json。官方ONNX摘要见out/sonic-setup.json；源SHA不随本报告文字变化。

## 四、失败与限制

首个6秒站立试验仅JSON序列化因numpy.bool_失败，CSV/NPZ保留；修成bool后新目录复跑，不覆盖旧证据。服务器无rg，相关只读搜索改用grep。共享render环境缺yaml，复制已有包到私有pydeps解决。
原始4秒NPZ包含 reaching，而非完整抓取/抬升步骤；SONIC G1输入不消费根平移，因此原生成器世界坐标手约束不能直接当作物体目标。投影固定腿/腰改变了全身语义，已显式记录。直接轨迹跟踪仍有约4–8度量级RMS误差和底座漂移；张手偶然触碰/几毫米抬动不算抓住。
固定底座路线仍是人工校准几何＋ARDY冗余偏好，非原生ARDY必要成功。尚无SONIC全身体控制下的稳定抓取抬升，无新增文本生成→任务完成的重复评测；第二生成方法、Archon预约和公开发布由人类/组内负责，未冒充完成。

## 五、下一步

继续在同一ACTIVE任务自有目录进行第二波≤20次CPU仿真，保持4核/16GiB/300秒命令/90秒仿真/1GiB数据预算。先做中立站姿→物体的任务空间适配与SONIC参考闭环补偿，身体29通道只能来自SONIC；手指接触门控分开。明确标注人为几何约束，补ARDY输入影响与OFF对照；成功后跨版本、重复试验、no-grip与失败演示。原始模型追踪问题仍OPEN。

## 六、复现方法

```bash
D=/data/group4/20261006-093203-codex-6385a841
bash "$D/run.sh" test_sonic_v11.py
# 新名称避免覆盖既有输出；仅在登记的新波资源限额内复跑
bash "$D/run.sh" ardy_sonic.py near_s42 NEW_NAME --speed .25
STAGE_PY=/home/group4/group4_dasc7606c/envs/render/bin/python bash "$D/run.sh" ardy_sonic.py near_s42 NEW_314
```

wave1.tar.gz包含本任务代码、复制输入/资产及物理结果，但不含191MiB的SONIC权重或私有运行库。setup_sonic.py和out/sonic-setup.json记录服务器来源、许可证与SHA，不能当作可公开再分发授权。当前服务器路径之外复建需调整路径并保持同模型/运行时指纹。
'''
rp=B/'reports'/f'{T}-wave1-report.md';assert not rp.exists();rp.write_text(report)
for p in D.glob('*.py'):shutil.copy2(p,W/p.name)
for p in D.glob('*.sh'):shutil.copy2(p,W/p.name)
for name in ['wave1-summary.json','input-provenance.json','input-npz-provenance.json']:
 shutil.copy2(D/name,W/name)
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE1 CHECKPOINT]\n- 20 physical episodes launched, all exited; first stand JSON serialization failed, preserved.\n- No SONIC grasp claim. Scope remains ACTIVE; next wave <=20 episodes after dual archive verification.\n- Remote rg unavailable; next read-only search uses grep.\n')
with tarfile.open(D/'wave1.tar.gz','w:gz') as tar:
 for p in sorted(D.iterdir()):
  if p.name in ['src','out','official_refs','input-provenance.json','input-npz-provenance.json','wave1-summary.json'] or p.suffix in ['.py','.sh']:
   tar.add(p,arcname=p.name,recursive=True)
 tar.add(rp,arcname=rp.name)
 tar.add(L/'steps.md',arcname='checkpoint-steps.md')
manifest={str(rp):sha(rp),str(D/'wave1.tar.gz'):sha(D/'wave1.tar.gz')}
(W/'wave1-archive.sha256').write_text(''.join(v+'  '+p+'\n' for p,v in manifest.items()))
print(json.dumps(manifest,indent=2))
