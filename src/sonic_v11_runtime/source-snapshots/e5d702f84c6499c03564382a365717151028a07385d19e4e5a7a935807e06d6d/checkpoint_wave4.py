"""Immutable fourth-wave archive. A checkpoint is NOT task completion."""
import datetime
import json
import shutil
import tarfile
from pathlib import Path
from wave4_records import NAMES, collect, sha

B = Path('/home/group4/group4_dasc7606c')
T = '20261006-093203-codex-6385a841'
D = Path('/data/group4') / T
W = B / 'work' / T
L = B / 'logs' / T
assert sha(B/'AGENTS.md') == '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
bundle = D/'wave4.tar.gz'
report_path = B/'reports'/f'{T}-wave4-report.md'
summary_path = D/'wave4-summary.json'
assert not any(p.exists() for p in [bundle, report_path, summary_path])
summary = collect(D)
assert summary['recorded_episodes'] == 20 and not summary['missing_results']
assert not summary['source_snapshot_missing']
summary.update(task=T, wave=4, task_active=True, physical_script_launches=20,
               mixed_search_trials_are_not_a_success_rate_estimate=True,
               canonical_fixed_base_327_repetitions={'passes':2,'trials':2,'same_configuration_not_generalization':True})
replay = json.loads((D/'out/w4-lift15-replay-v3/replay.json').read_text())
assert replay['physical_steps'] == 0 and replay['success']
records = {r['name']:r for r in summary['results']}
rows = ['| 测试 | MuJoCo | 峰值抬升 mm | 判定HOLD最低 mm | 成功 | 停止原因 / 未通过门 |',
        '|---|---|---:|---:|---|---|']
for name in NAMES:
    r = records[name]
    hold = f"{1000*r['hold_min_lift_m']:.3f}" if r['hold_min_lift_m'] != -1. else '未进入HOLD'
    why = r['fail_reason'] or ', '.join(k for k,v in r['gates'].items() if not v) or '全部门通过'
    rows.append(f"| {name} | {r['runtime_stamp']['mujoco_version']} | {1000*r['max_lift_m']:.3f} | {hold} | {r['success']} | {why} |")
table = '\n'.join(rows)
failure_rows = '\n'.join(f"- `{name}`：`{records[name]['fail_reason']}`" for name in NAMES if records[name]['fail_reason'])
now = datetime.datetime.now().astimezone().isoformat()
report = f'''# ARDY→官方SONIC：第四波检查点
- 执行方：codex(hp<745a0dbc-a26f-4c01-add8-7577fca612de>)；task={T}；截止{now}。任务与目标仍ACTIVE。

## 一、结论

有条件能：MuJoCo3.2.7、固定pelvis、宽桌面、仿真真值定位、15cm任务适配下，同一抓取配置2次通过；判定HOLD最低95.519mm、至少2指、腕/其他机器人对方块载荷0、方块桌面支撑0、相对腕滑移3.567mm，随后释放落桌通过。
本波20种启动有2次成功，不将2/20当成某一方法的成功率；2/2只表示同配置复测，不代表跨物体/随机种子泛化。
不能声明完整Track4或实机可用：3.14.0抓取仍失败；两版本自由底座均未完成抓取；生成、轨迹、真实视觉定位、交互纠正和实机流程尚未全部打通。

## 二、操作步骤

1. 既有near_s42 NPZ及新增lift/hold/release NPZ→几何和零空间姿态适配→解析限速/限加速度/限jerk的C2参考→官方1751/994 SONIC v1.1 ONNX→身体原始力矩上限的PD。另有显式右臂模型重力前馈和独立手指控制；身体电机位置目标没有被IK脚本覆盖。
2. 增加全部方块接触审计，区分指垫、腕、其他机器人、桌面/地面；保留6维接触力、接触坐标系、对方块的世界力和力矩。增加身体环境支撑审计，区分两脚、非脚地面与桌面，观察器不改状态。
3. 尝试独立KD、官方armature映射、清零身体被动阻尼的诊断、解码目标平滑、只在抬升/保持增大KP、减少/冻结外环更新。均未改善严格成绩，因此不启用为新默认。
4. 保持原接近/捕获过程，将捕获后的腕姿态垂直任务目标从10cm改为15cm，获得2次固定底座成功。这是任务目标重定向，不是原生ARDY生成15cm，也不表示抖动已解决。
5. 新候选C2段不可行时，可继续上一条已认证多项式的剩余段，零速/零加速度终点保持；无旧证书仍停止。在3.14.0实际命中30次续接，从原14.14s的停止点推进至39.908s双指接触超时。
6. 关碰撞、不开手、关闭ARDY内容及自由底座对照；另用保存的qpos零步进分析和双视角回放。每项启动的命令、资源、退出状态见`logs/{T}/steps.md`和run日志。

## 三、实测证据

{table}

严格门沿用HOLD≥70mm、方块底离桌≥40mm、≥2指、无方块外部支撑、滑移<10mm、释放下落≥60mm并最终落桌离指、无外力/警告、直立；这是本任务工程门，不是PDF指定的数值。判定保持窗排除开始20ms，成功例993个500Hz样本约1.986s，阶段保持约2.004s。
接触审计门v2新增HOLD非指垫机器人法向总载荷<.001N；自由底座v3再检查HOLD脚支撑>1N、桌面/非脚地面总载荷<.001N。legacy_gates另存，不覆盖旧判据。没有HOLD的结果这些门为false，不能据此宣称已经测得HOLD不平衡。

成功例w4_lift15_327：峰值166.700mm、最低HOLD95.519mm、滑移3.567mm，wall={records['w4_lift15_327']['wall_s']:.3f}s、模拟47.272s、策略p95={records['w4_lift15_327']['policy_p95_ms']:.3f}ms；复测wall={records['w4_lift15_repeat327']['wall_s']:.3f}s。推理p95不含整个闭环，不能由此宣称50Hz实时。
成功例实际身体仍有约6.185rad/s关节峰速、PREGRASP腕yaw约.001910rad软限位超量；HOLD 25Hz诊断实际→解码RMS=.083380rad、腕位置RMS=45.834mm。目标提高带来高度余量，并未消除动态偏差，不能据此上实机。

原10cm基线在3.2.7复现HOLD42.941mm/双指/无桌面与非指垫载荷，首次排除了这一复现中的“靠腕托方块”；但其他失败样本确有腕载荷，例如pad-off最大31.502N，不能推广为所有变体没有旁路支撑。
no-grip在3.2.7无双指承重且方块留桌，末段触发参考停止；pad-off在ALIGN超时。它们与正样本分岔，但不等于已在3.14.0证明阴性对照有效。
ARDY综合消融在3.2.7的CLOSE阶段失败：关闭native形状残差、全部姿态先验及生成段时序，保持几何、SONIC和手指；仍保留native-derived端点种子，不能称为完全独立ARDY基线。与成功例尚非最终同源码配对，且只一版本一次，贡献因果结论待第五波。

自由底座3.2.7最大底座XY漂移{records['w4_lift15_free327']['max_drift_m']*1000:.3f}mm、最低up_z={records['w4_lift15_free327']['min_up_z']:.6f}、未倒但CLOSE超时；3.14.0在ALIGN超时。身体接触桌面全段最大法向力分别48.499/58.837N。保存姿态的25Hz零步进重建定位到SETTLE/APPROACH腕与桌子前侧接触，以及CLOSE中指垫触桌；此几何重建不是原500Hz接触力证据。

零物理步进验证：contact-audit21项、decoded-arm-filter10项、reference-fallback9项、balance-audit9项通过；动力学场景12项与KD接口6项见各自结果。fallback3000次对抗性重规划命中199次续接，C2边界差3.55e-15，认证v/a/j仍≤.6/1.5/12；它只保证SONIC输入参考，不保证解码或实际关节速度。
两段目标滤波改变了执行器目标并引入滞后，虽追踪修改后目标RMS降低，却增加任务偏差并掉物，因此保持关闭，原官方action/history不变。

## 四、失败项与限制

物理停止原文：

{failure_rows}

初次本地fallback单测因输出父目录未创建失败（FileNotFoundError），补父目录后本地与远端9项通过；失败不计物理episode，但保留事实。
检查点脚本首次本地语法读取因Windows默认gbk解码失败：`UnicodeDecodeError: 'gbk' codec can't decode byte 0x80`；改为显式UTF-8读取后复查，不涉及远端运行。
首次回放渲染失败：`ModuleNotFoundError: No module named 'PIL'`。改用现有ffmpeg字幕滤镜后失败：`No such filter: 'drawtext'`、`BrokenPipeError: [Errno 32] Broken pipe`。第三次640x480双视角/25fps在300s上限退出124，保留不完整v2，不当成功回放引用。未改共享环境、未增加时限；最终降为320x240双视角、12.5fps/跳取原25fps的隔帧、关闭渲染阴影，MP4加独立captions.vtt，输出到新目录`w4-lift15-replay-v3`，不覆盖失败目录。
早期control-analysis和初版lift-height-preflight曾继承旧episode运行指纹，不是分析自身依赖指纹；旧文件保留并仅作有条件诊断。`lift-height-preflight-v2`与后来control-analysis改为自身源/场景/依赖指纹，并另列source_episode_runtime_stamp；不能用旧数字证明当前源码版本。
初版reference_margin=.05只是缩小许可域，不是真正制动距离，3.14.0反而更早13.04s停止。当前续接不降级为裁剪或越界执行。
不同版本接触和控制结果不一致，应锁定3.2.7仅复现当前固定底座演示，同时并列保留3.14.0失败，不能称为跨版本成立。当前也未证明完整官方动力学一致性。
仿真真值定位、15cm重定向和预设场景属人工/模型设置；user_corrections=0只表示运行中没有交互纠正，不表示无人工设置。机器人预约/现场授权、组内第二方法和公开发布仍需人类协调，不介入KIMODO。

## 五、下一步建议

归档核SHA后登记第五波≤20次4CPU/AS16GiB/300s/90s测试：先最终同源码的ARDY ON/OFF配对和正例复测；加入逐body的桌面接触审计，优先消除中性起始姿态与桌子前侧的干扰，再处理接近/闭合阶段碰桌和自由底座补偿。
可以显式比较桌子前沿.23→.245m（方块初始位置、高度、质量、摩擦、桌后沿与碰撞均保持；完整方块仍有4.5mm边缘余量），这属于环境放置对照，不冒充算法提升。每个改动先零步进结构/初始支撑/碰撞检查，再物理测试，不移除不利碰撞。
单一高度/姿态重复不够：成功后做位移、不同seed文本段、关闭抓取与触垫、两版本、保持时长及用户纠正回归；不将关节参考C2当作实际身体无抖动。

## 六、复现方法

以下需在新登记的有界任务/波次内用新的输出名，不能继续占用已满20次的第四波额度：

```bash
D=/data/group4/{T}
bash "$D/run.sh" "$D/sonic_grasp.py" NEW_NAME --lift-height .15 --reference-fallback --lock-grip --grip-frame-lift --direct-table --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture --phase-clips --capture-radius .007 --c2-reference --endpoint-seed --endpoint-seed-native --fixed-base --contact-close --contact-entry-dwell .04 --gravity-arm 1 --opponent middle --close-seconds .5
# 去掉--fixed-base检验自由底座；--ardy-off作综合消融；--no-grip或--pad-off作阴性流程。
# 3.14.0须STAGE_PY=/home/group4/group4_dasc7606c/envs/render/bin/python，并如实保留失败。
```

当前源码与两次成功的历史源码不同（新增续接/环境审计/消融），历史精确复现以result.runtime_stamp选择`source-snapshots/<sha>/<file>`整套依赖；不要拿最新文件冒充旧版本。
波4包包含20组原始结果、场景、NPZ/CSV500Hz力、源快照、测试、日志、视频和本报告；原G1资产与near NPZ见wave1包，生成段NPZ见wave2包。官方权重只列来源与SHA，不重新分发；公共仓发布尚未获授权。
回放来自w4_lift15_327保存qpos，MuJoCo3.2.7，零物理步进，左右为全机器人/近景。MP4没有烧录标记，展示时必须同时展示captions.vtt或明确的固定底座/非实时说明，不能与旧手工混合视频混用。
服务器报告与wave4.tar.gz下载到本地server_reports/{T}/，独立比较SHA；归档结果与Git仅自有路径提交另记流水。检查点不创建done.txt、不关闭总体目标。
'''
summary_path.write_text(json.dumps(summary, indent=2)+'\n')
report_path.write_text(report)
with (L/'steps.md').open('a') as f:
    f.write(f'\n## [WAVE4 CHECKPOINT] {now}\n-20/20 bounded physical launches exited;2 fixed-base3.2.7 passes, no general success rate or full Track4 claim; current sources all covered by exact snapshot hashes.\n-FileNotFoundError local fallback parent path fixed; PIL missing, ffmpeg drawtext absent and300s timeout caused3 replay failures, preserved; v3 reduced-resolution replay uses external VTT and no physics integration.\n-Metadata erratum: early analysis inherited source-episode stamp, corrected in newly named preflight-v2 and later analyses without rewriting history.\n-Renewed run wrapper records CPU PSI and stops on AGENTS hash changes.\n')
for p in D.iterdir():
    if p.is_file() and p.suffix in {'.py','.sh'}:
        shutil.copy2(p, W/p.name)
shutil.copy2(summary_path, W/summary_path.name)
tests = ['contact-audit-tests','decoded-arm-filter-tests','reference-fallback-tests',
         'balance-audit-tests','dynamics-scene-tests','lift-height-preflight','lift-height-preflight-v2',
         'w4-lift15-replay','w4-lift15-replay-v2','w4-lift15-replay-v3']
included = [p for p in D.iterdir() if p.is_file() and p.suffix in {'.py','.sh'}]
included += [D/'source-snapshots', summary_path] + [D/'out'/n for n in NAMES]
included += list((D/'out').glob('*.json'))
included += [D/'out'/n for n in tests if (D/'out'/n).exists()] + [report_path, L]
def total(paths):
    return sum(p.stat().st_size for path in paths for p in ([path] if path.is_file() else path.rglob('*')) if p.is_file())
current, upper = total([D]), total(included)
assert current+upper+16*1024**2 < 2*1024**3, ('archive peak exceeds2GiB scope',current,upper)
assert shutil.disk_usage(D).free > upper+30*1024**3
with tarfile.open(bundle, 'w:gz') as tar:
    for p in included:
        arc = str(p.relative_to(D)) if p.is_relative_to(D) else 'checkpoint-logs' if p == L else p.name
        tar.add(p, arcname=arc)
manifest = {str(report_path):sha(report_path), str(bundle):sha(bundle)}
(W/'wave4-archive.sha256').write_text(''.join(v+'  '+p+'\n' for p,v in manifest.items()))
print(json.dumps(dict(manifest=manifest,episodes=20,successes=2,source_snapshot_missing=0,
                     estimated_prearchive_bytes=current, conservative_bundle_upper_bytes=upper), indent=2))
