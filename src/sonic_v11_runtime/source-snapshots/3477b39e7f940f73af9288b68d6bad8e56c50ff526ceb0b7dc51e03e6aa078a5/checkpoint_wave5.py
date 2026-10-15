"""Seal all 20 wave-5 trials; never turn a checkpoint into task completion."""
import datetime
import json
import shutil
import tarfile
from pathlib import Path
from wave4_records import sha
from wave5_records import collect

B = Path('/home/group4/group4_dasc7606c')
T = '20261006-093203-codex-6385a841'
D = Path('/data/group4') / T
W = B / 'work' / T
L = B / 'logs' / T
RULES = '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert sha(B / 'AGENTS.md') == RULES
bundle = D / 'wave5.tar.gz'
report_path = B / 'reports' / f'{T}-wave5-report.md'
summary_path = D / 'wave5-summary.json'
assert not any(p.exists() for p in [bundle, report_path, summary_path])
summary = collect(D)
assert summary['recorded_episodes'] == 20
assert not summary['missing_results'] and not summary['source_snapshot_missing']
assert summary['legacy_successes'] == 7
assert summary['audited_table_return_successes'] == 5
assert summary['controlled_placing_successes'] == 0
summary.update(task=T, wave=5, task_active=True,
               canonical_free_base_327_repetitions={'passes': 2, 'trials': 2,
                   'same_configuration_not_generalization': True},
               full_track4_complete=False, real_robot_ready=False)
records = {r['name']: r for r in summary['results']}
replay = json.loads((D / 'out/w5-free-grasp-replay/replay.json').read_text())
assert replay['physical_steps'] == 0
assert replay['source_episode'] == 'w5_fingergain3_free327'
canonical = records['w5_fingergain3_free327']
assert canonical['audited_table_return_success'] and not canonical['base_fixture']
assert not canonical['controlled_placing_validated']
rows = ['| 启动/测试 | MuJoCo | HOLD最低mm | 滑移mm | 旧成功 | 实际落桌成功 | 受控放置 | 原始停止原因 |',
        '|---|---|---:|---:|---|---|---|---|']
for r in summary['results']:
    hold = f"{1000*r['hold_min_lift_m']:.3f}" if r['hold_min_lift_m'] >= 0 else '未完成有效HOLD'
    slip = f"{1000*r['hold_slip_m']:.3f}" if r['hold_slip_m'] < 1 else '无有效保持窗'
    rows.append(f"| {r['launch']} / {r['name']} | {r['runtime_stamp']['mujoco_version']} | {hold} | {slip} | {r['success']} | {r['audited_table_return_success']} | {r['controlled_placing_validated']} | {r['fail_reason'] or '无；仍须读取边界'} |")
table = '\n'.join(rows)
failures = '\n'.join(f"- `{r['name']}`：`{r['fail_reason']}`"
                     for r in summary['results'] if r['fail_reason'])
now = datetime.datetime.now().astimezone().isoformat()
report = f'''# ARDY→官方SONIC：第五波完整检查点
- 执行方：codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；task={T}；截止{now}。总体任务仍ACTIVE，不生成done标记。

## 一、结论

有条件能：自由底座、MuJoCo3.2.7、35mm/20g方块、宽桌面、仿真状态定位和显式轨迹/手指适配下，同配置2次通过夹持、抬升、约2s保持和松手落桌；HOLD最低126.430mm、滑移3.807mm，HOLD无靠桌或非脚地面支撑。
20次混合搜索中，原门7次通过，审计最终确实落桌后5次通过，受控放置0次；这些异构试验不能组成方法成功率。2/2只表示同配置复测，不代表随机seed或跨物体泛化。
不能宣称完整Track4或实机就绪：全程腕桌干扰、快速关节运动、跨版本差异、受控放下、视觉定位、在线生成/纠正和ARDY独立贡献尚未解决。

## 二、操作步骤

1. 全部20次启动使用自有原子launch账本，含启动失败也计数；4CPU、AS16GiB、timeout300s、最多90s模拟，不占GPU。
2. ARDY near_s42及lift/hold/release_s42→G1关节参考/任务空间重定向→C2参考→官方SONIC v1.1 ONNX身体电机目标→原力矩上限PD，附显式右臂模型重力补偿；手指独立控制，物体无weld/瞬移/外力。
3. 桌前沿.23→.24m保持方块和桌后沿/高度不变，是环境放置对照；指KP×3/KD×sqrt(3)是独立手指适配，不是提高SONIC身体KP。增加两版本同源码KP对照、no-grip阴性、ARDY综合消融。
4. 用同Python/NumPy/ORT的MuJoCo-only包覆盖复查3.14.0，保持共享环境只读；保留全库来源hash，避免把NumPy/解释器改变冒充仿真器版本效应。
5. 原solver接触另做最终落点审计，严格区分table_top与floor；旧result不重写。加入SETDOWN并测试，两个版本都在接触合格落桌条件前失去夹持/超时。
6. 保存qpos、500Hz遥测/接触、源快照；自由底座双视角视频来自原qpos、零物理积分。浏览器切换固定/自由记录，并列展示边界，不公开上传实验资料。
完整命令、资源/报错见`logs/{T}/steps.md`及run日志。

## 三、实测证据

{table}

自由正例3.2.7：峰值144.337mm，HOLD最低126.430mm，滑移3.807mm，至少2指；HOLD脚接触法向合力最低348.956N，HOLD机器人桌面/非脚地面接触0，方块非指垫机器人载荷0；最大机器人桌面接触44.275N发生在其他阶段，不能由HOLD门推广为全过程无碰撞。
最终方块位置[.271581388,-.098810315,.774407879]m，原solver接触证明table_top承重、非floor。重复例物理轨迹同配置一致，wall分别85.362/88.355s；确定性同配置重放不代表独立随机样本。
3.14.0正例HOLD136.712mm、滑移4.113mm，但释放时与髋接触后落地；历史final_supported混合桌/地，旧成功应限定为旧门。MuJoCo-only覆层重现相同落点差异；不得挑选好看的版本作为普遍结论。
两版本no-grip都失败，且与同版本正例保存姿态分岔；同源码gain1/gain3配对指令有效，不能拿只有打印参数不同作因果证据。
ARDY综合OFF在3.2.7失败，在3.14.0仍抬起并落桌；它保留native-derived端点种子，只关闭形状残差、姿态先验和阶段时序，不能称ARDY完全独立对照，更不能宣称ARDY必要或优于几何基线。
SETDOWN两版本保持阶段有抬升，但下降时失去夹持，最后落桌也未通过受控返回；face-half10mm在3.14.0最大抬升仅24.976mm，因此不作为默认。默认仍15mm面域/0.5mm几何preload。
参考解析最大速度.598971rad/s、加速度1.308246rad/s2、jerk10.813552rad/s3，C2边界跳变0；实际右臂峰速最高6.684367rad/s，实际→解码电机目标RMS.076437rad，虚拟输入参考误差RMS.254111rad，二者不可混称。右臂7关节本例超限0，但未验证全程实际速度/加速度安全门。
模拟48.166s耗时85.362s，策略中位13.557ms/p95 15.873ms只是推理，不含闭环/生成，不能宣称实时。user_corrections=0仅无交互输入，人工场景/真值定位/目标适配仍存在。
本波记录/依赖/model hash全部核验，missing_results=0、source_snapshot_missing=0。源版本由每条runtime_stamp决定，最新源码不冒充历史执行源。独立手指、table、preload、face、setdown等测试的实际JSON/命令保留在包中；单测不证明物理成功。

## 四、失败项与原因

物理停止原文：

{failures}

晚间本地回放启动曾受审批/网络权限限制，后经正常审批恢复；最终自由底座原始记录和视频已SCP并独立SHA核验，限制不是远端文件缺失。此前固定底座旧视频仍保留，不代替自由底座验证。
23:04复查/home仅8.6G可用、/data约11T、CPU/内存/IO PSI avg均0；自有D为1477548987字节。无删除/移动他人或旧证据，归档前再检查当前空间和2GiB预算。
23:05只读ls曾显示canonical/control-analysis.json不存在；不推断整个记录缺失、不补造分析，canonical原始result/trajectory/接触存在且已核SHA。读取命令后续ls返回0不能抹掉前一条No such file or directory。
旧whole_body_balance_validated字段只由直立+HOLD支撑门产生，名称过强；其含义仅HOLD支撑检查，com/cOP稳定裕度、全过程平衡未验证。新界面已显式说明，旧结果不回改。
旧final_supported不足以证明落桌；两个3.14.0legacy正例实际落地，本文及summary追加审计纠正，不覆盖原门/原result。当前SETDOWN到桌后200ms门仍不足单独证明全程夹持连续性，后续应加下降失握和冲击约束。
右指尖10mm球形pad/摩擦2.0/独立增益为仿真适配，未标定真实G1手部；尚未做真实视觉、扰动、seed/文本泛化。原生ARDY抓取成立=false，完整Track4=false，real_robot_ready=false。
本检查点不改变共享ARDY/SONIC源码；用户23点后另授权可直接服务器部署改进，后续先查归属/备份，保留不干预KIMODO/共享配置/他人任务的边界。

## 五、下一步建议

先密封本波和双端SHA，再登记新的有界波次；用原500Hz身体环境接触定位碰桌body/阶段和初始几何，新增初始可行姿态/路径碰撞约束与实际关节运动审计，不移除不利碰撞、不固定底座。
新试验仍只让IK修改SONIC输入参考；实际电机速度/限位需要用真实反馈门和显式力矩适配评估，任何改变原SONIC目标的安全适配单独标签/消融，不冒充原厂执行。
随后完善接触连续的SETDOWN，再输入用户文本/seed生成的实际NPZ，测试位置/质量变化、计端到端延迟与真正用户纠正；未真实发生的纠正不计成功。
服务器可用入口可发布为本任务命名的根目录启动器，依赖与原始资产继续在/data，避免改写共享vendor源码和/home大文件。已有源模块如需变更须核在制任务/备份/hash，不能只因同属group4就覆盖。

## 六、复现方法

新登记的未满波次内，使用全新输出名（wave5已20/20，不可继续占用）：

```bash
D=/data/group4/{T}
bash "$D/run.sh" "$D/sonic_grasp.py" NEW_NAME --finger-gain 3 --table-front .24 --lift-height .15 --reference-fallback --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5
# --no-grip 阴性；--ardy-off 综合消融但保留native端点种子；--setdown 受控下降未通过。
# STAGE_PY=.../envs/render/bin/python 选择3.14.0全环境；PYTHONPATH="$D/mujoco314-only" 选择同base环境仅改变MuJoCo包。
```

历史精确复现按result.runtime_stamp取`source-snapshots/<sha>/<模块>`，G1原资产/原near NPZ见wave1，生成lift/hold/release见wave2；本包不重新分发共享权重/环境。官方SONIC权重只登记SHA和本服务器来源，不公开分发。
自由视频`out/w5-free-grasp-replay/grasp.mp4` SHA={sha(D/'out/w5-free-grasp-replay/grasp.mp4')}；199帧、12.5fps、15.92s，来源sim48.166s，不是实时/实机录像，必须同时展示VTT和实验边界。
归档包/report独立SCP到本机server_reports并比SHA；Git只提交本会话路径并验证其他暂存blob，另外记归档回执。检查点本身不宣称总体完成。
'''
summary_path.write_text(json.dumps(summary, indent=2) + '\n')
report_path.write_text(report)
with (L / 'steps.md').open('a') as f:
    f.write(f'\n## [WAVE5 CHECKPOINT] {now}\n-20 launches exited; all runtime/model/source snapshots verified. legacy7, actual-table5, controlled-place0; mixed search not a success-rate estimate.\n-Free3.2.7 repeated2/2 only same configuration; initial44.275N robot-table contact and actual wrist speed6.684rad/s remain.\n-Current goal ACTIVE, no done. New deployment permission does not authorize overwrite of teammates or KIMODO.\n-Read-only diagnostic ls for canonical/control-analysis.json failed; no file fabricated. Local replay permission failure later recovered via approved tools; canonical raw data/video SHA verified.\n')
for p in D.iterdir():
    if p.is_file() and p.suffix in {'.py', '.sh'}:
        shutil.copy2(p, W / p.name)
shutil.copy2(summary_path, W / summary_path.name)
included = [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py', '.sh'}]
included += [D / 'source-snapshots', summary_path, D / 'wave5-launches.jsonl']
included += [D / 'out' / r['name'] for r in summary['results']]
included += sorted(p for p in (D / 'out').glob('w5-*') if p.is_dir())
included += sorted((D / 'out').glob('*tests*.json'))
included += sorted(p for p in (D / 'out').iterdir()
                   if p.is_dir() and ('tests' in p.name or p.name == 'mujoco-overlay'))
included += [report_path, L]
included = list(dict.fromkeys(included))
def total(paths):
    return sum(p.stat().st_size for path in paths
               for p in ([path] if path.is_file() else path.rglob('*'))
               if p.is_file() and not p.is_symlink())
current, upper = total([D]), total(included)
assert current + upper + 16*1024**2 < 2*1024**3, ('archive peak exceeds2GiB', current, upper)
assert shutil.disk_usage(D).free > upper + 30*1024**3
with tarfile.open(bundle, 'w:gz', dereference=False) as tar:
    for p in included:
        arc = str(p.relative_to(D)) if p.is_relative_to(D) else 'checkpoint-logs' if p == L else p.name
        tar.add(p, arcname=arc)
manifest = {str(report_path): sha(report_path), str(bundle): sha(bundle)}
(W / 'wave5-archive.sha256').write_text(''.join(v+'  '+p+'\n' for p, v in manifest.items()))
print(json.dumps(dict(manifest=manifest, episodes=20, legacy_successes=7,
                     audited_table_return_successes=5, controlled_placing_successes=0,
                     source_snapshot_missing=0, estimated_prearchive_bytes=current,
                     conservative_bundle_upper_bytes=upper), indent=2))
