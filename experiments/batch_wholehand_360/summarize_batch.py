#!/usr/bin/env python3
"""Summarize a completed batch without inferring missing outcomes."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

GROUPS = {"A": 100, "B": 100, "C": 50, "D": 50, "NGR": 20, "NWS": 20, "NGF": 20}
OUTCOMES = ("success", "planning_refused", "physics_failure", "infrastructure_error", "not_started")
HEADINGS = tuple("## " + h for h in ("一、结论", "二、操作步骤", "三、实测证据", "四、失败项与原因", "五、下一步建议", "六、复现方法"))


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, "unreadable: " + repr(exc)


def digest(path):
    h = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def id_key(value):
    match = re.search(r"(\d+)$", str(value))
    return (int(match.group(1)) if match else 10**18, str(value))


def stages_from(state):
    stages = state.get("stages", []) if isinstance(state, dict) else []
    return list(stages.items()) if isinstance(stages, dict) else [(str(i), x) for i, x in enumerate(stages)]


def classify(result, result_error, state):
    if result:
        label = str(result.get("classification", "")).lower()
        if label == "planning_refused" or result.get("physics_run_kind") == "safe_standing_after_planning_refusal":
            return "planning_refused"
        if result.get("success") is True or label in ("success", "physics_success"):
            return "success"
        if result.get("grasp_path_executed") is True or label == "physics_failure":
            return "physics_failure"
        if label in ("infrastructure_error", "error", "failed"):
            return "infrastructure_error"
    if result_error not in (None, "missing"):
        return "infrastructure_error"
    for _, stage in stages_from(state or {}):
        if not isinstance(stage, dict):
            continue
        status = str(stage.get("status", "")).lower()
        rc = stage.get("rc", stage.get("returncode", stage.get("exit_code")))
        if status in ("failed", "error", "timeout", "timed_out") or (rc is not None and rc != 0):
            return "infrastructure_error"
    return "not_started"


def failed_gates(result):
    if not result or result.get('grasp_path_executed') is not True:
        return []
    gates=[]
    if result.get('reason')!='complete':gates.append('未完整运行：'+str(result.get('reason')))
    support=result.get('hold_support_steps',0);safe=result.get('hold_safe_steps',0)
    if support<2000:gates.append(f'保持步数不足：{support}<2000')
    if safe!=support:gates.append(f'保持阶段有不安全步：{safe}/{support}安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败')
    slip=result.get('max_wristlocal_slip_alllift_m')
    if slip is None or slip>.01:gates.append(f'腕局部滑移：{slip}m，门≤.01m')
    joint=result.get('max_joint_limit_violation_rad')
    if joint is None or joint>=.002:gates.append(f'关节超限：{joint}rad，门<.002rad')
    return gates


def safe_log(root, reference, limit=1200):
    if not reference:
        return None
    p = Path(str(reference))
    if not p.is_absolute():
        p = root / p
    try:
        resolved = p.resolve()
        resolved.relative_to(root.resolve())
        data = resolved.read_text(encoding="utf-8", errors="replace")
        return data[-limit:]
    except Exception:
        return "log unavailable or outside task data directory: " + str(reference)


def inspect_trial(root, config):
    tid = str(config["id"])
    result_path = root / "out" / tid / "result.json"
    replay_path = root / "out" / tid / "replay" / "replay.json"
    state_path = root / "state" / (tid + ".json")
    result, result_error = read_json(result_path)
    replay, replay_error = read_json(replay_path)
    state, state_error = read_json(state_path)
    outcome = classify(result, result_error, state)
    video_path = root / "out" / tid / "replay" / "grasp.mp4"
    video_sha = digest(video_path)
    result_sha = digest(result_path)
    trajectory_sha = digest(root / "out" / tid / "trajectory.npz")
    replay_ok = bool(replay and replay.get("id") == config["id"] and replay.get("decode_verified") is True
                     and replay.get("video_sha") and replay.get("video_sha") == video_sha
                     and replay.get("source_result_sha") == result_sha
                     and replay.get("source_trajectory_sha") == trajectory_sha)
    actual_grasp = bool(result and result.get("grasp_path_executed") is True)
    valid_grasp_video = replay_ok and actual_grasp and replay.get("starts_with_reach") is True
    stages = []
    for name, stage in stages_from(state or {}):
        if isinstance(stage, dict):
            log_ref = stage.get("log") or stage.get("log_path")
            stages.append({"stage": name, "status": stage.get("status"),
                           "rc": stage.get("rc", stage.get("returncode", stage.get("exit_code"))),
                           "command": stage.get("command"), "log": log_ref,
                           "log_tail": safe_log(root, log_ref)})
    return {"id": config["id"], "group": config["group"], "config": config,
            "infrastructure_subtype":(state or {}).get('infrastructure_subtype'),
            "outcome": outcome, "result": result, "result_error": result_error,
            "state_error": state_error, "stages": stages,
            "actual_grasp_executed": actual_grasp, "valid_video": replay_ok,
            "valid_grasp_video": valid_grasp_video,
            "video": str(video_path), "video_sha256": video_sha,
            "result_sha256": result_sha, "trajectory_sha256": trajectory_sha,
            "replay": replay, "replay_error": replay_error}


def pair_analysis(rows, target_group, baseline_group):
    by_id = {str(r["id"]): r for r in rows}
    pairs = []
    for target in rows:
        if target["group"] != target_group:
            continue
        source = target["config"].get("source_baseline_trial")
        baseline = by_id.get(str(source)) if source is not None else None
        if not baseline or baseline["group"] != baseline_group:
            continue
        a, b = baseline["outcome"], target["outcome"]
        pipeline_complete = a in ("success", "planning_refused", "physics_failure") and b in ("success", "planning_refused", "physics_failure")
        physics_complete = a in ("success", "physics_failure") and b in ("success", "physics_failure")
        pipeline_cell = ("both_success" if a == b == "success" else
                         "baseline_only_success" if a == "success" and b in ("planning_refused", "physics_failure") else
                         "target_only_success" if b == "success" and a in ("planning_refused", "physics_failure") else
                         "neither_success" if pipeline_complete else "error_or_incomplete_separate")
        physics_cell = ("both_success" if a == b == "success" else
                        "baseline_only_success" if a == "success" and b == "physics_failure" else
                        "target_only_success" if a == "physics_failure" and b == "success" else
                        "neither_success" if physics_complete else "not_physics_comparable")
        pairs.append({"baseline_id": baseline["id"], "target_id": target["id"],
                      "baseline": a, "target": b, "pipeline_cell": pipeline_cell,
                      "physics_cell": physics_cell, "pipeline_complete": pipeline_complete,
                      "physics_complete": physics_complete})
    pipeline_cells = Counter(p["pipeline_cell"] for p in pairs)
    physics_cells = Counter(p["physics_cell"] for p in pairs)
    n = sum(p["physics_complete"] for p in pairs)
    delta = ((physics_cells["target_only_success"] - physics_cells["baseline_only_success"]) / n) if n else None
    return {"baseline_group": baseline_group, "target_group": target_group,
            "pairs": pairs, "pipeline_four_cells": dict(pipeline_cells),
            "excluded_pair_statuses": {status:sum(status in (p['baseline'],p['target']) for p in pairs)
                                      for status in ('infrastructure_error','not_started')},
            "valid_physics_four_cells": dict(physics_cells), "complete_physics_pairs": n,
            "success_difference_target_minus_baseline": delta,
            "interpretation": "有限样本描述，不作总体泛化"}


def summarize_total(groups, names):
    total = Counter()
    denom = 0
    videos = missing = executed = success = 0
    for name in names:
        data = groups[name]
        denom += data["planned_denominator"]
        total.update(data["counts"])
        videos += data["valid_video_count"]
        missing += data["missing_video_count"]
        executed += data["actual_grasp_execution_count"]
        success += data["counts"]["success"]
    return {"groups": list(names), "planned_denominator": denom,
            "counts": {k: total[k] for k in OUTCOMES}, "success": success,
            "actual_grasp_execution_count": executed, "valid_video_count": videos,
            "missing_video_count": missing,
            "success_per_planned": success / denom if denom else None,
            "success_per_grasp_execution": success / executed if executed else None}


def ratio(value):
    return "NA" if value is None else f"{value:.4f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--executed-steps", type=Path, help="optional verified operation log; no claims inferred")
    parser.add_argument("--executed-command", action="append", default=[], help="command actually run, supplied by operator")
    args = parser.parse_args()
    root = args.data_dir.resolve()
    manifest, err = read_json(root / "manifest.json")
    if err or not isinstance(manifest, dict) or not isinstance(manifest.get("trials"), list):
        raise SystemExit("manifest.json missing, unreadable, or lacks trials")
    configs = manifest["trials"]
    rows = [inspect_trial(root, c) for c in configs]
    groups = {}
    for group, expected in GROUPS.items():
        members = [r for r in rows if r["group"] == group]
        counts = Counter(r["outcome"] for r in members)
        counts["not_started"] += max(0, expected - len(members))
        examples = {}
        for outcome in ("success", "physics_failure"):
            candidates = sorted((r for r in members if r["outcome"] == outcome), key=lambda x: id_key(x["id"]))
            examples[outcome] = candidates[0]["id"] if candidates else None
        groups[group] = {"planned_denominator": expected, "manifest_rows": len(members),
                         "counts": {k: counts[k] for k in OUTCOMES},
                         "valid_video_count": sum(r["valid_video"] for r in members),
                         "valid_grasp_execution_video_count": sum(r["valid_grasp_video"] for r in members),
                         "actual_grasp_execution_count": sum(r["actual_grasp_executed"] for r in members),
                         "missing_video_count": max(0, expected - sum(r["valid_video"] for r in members)),
                         "success_per_planned": counts["success"] / expected if expected else None,
                         "success_per_grasp_execution": counts["success"] / sum(r["actual_grasp_executed"] for r in members) if sum(r["actual_grasp_executed"] for r in members) else None,
                         "examples_lowest_id": examples,
                         "planning_refused_ids": [r["id"] for r in sorted(members, key=lambda x: id_key(x["id"])) if r["outcome"] == "planning_refused"]}
    pairings = {"D_vs_C": pair_analysis(rows, "D", "C")}
    for group in ("NGR", "NWS", "NGF"):
        pairings[group + "_vs_B"] = pair_analysis(rows, group, "B")
    summary = {"source_root": str(root), "manifest_sha256": digest(root / "manifest.json"),
               'infrastructure_subtypes':dict(Counter(r['infrastructure_subtype'] for r in rows if r['infrastructure_subtype'])),
               "planned_trial_count": len(configs), "group_plan": GROUPS,
               "groups": groups, "paired_comparisons": pairings,
               "main_300_total": summarize_total(groups, ("A", "B", "C", "D")),
               "ablation_60_total": summarize_total(groups, ("NGR", "NWS", "NGF")),
               "gate_version": "wholehand-v2-wristlocal-support; verify each result field",
               "notes": ["A 为确定性复现，不能据此声称泛化。", "ARDY 是姿态先验，不是完整生成动作闭环。", "未启动按计划分母显式计入。", "物理成功与视频交付独立计数。"]}
    stamped=[r for r in rows if r['result'] and r['result'].get('runtime_stamp')]
    summary['trials']=[{'id':r['id'],'group':r['group'],'config':r['config'],'outcome':r['outcome'],
                       'reason':(r['result'] or {}).get('reason'),'actual_grasp_executed':r['actual_grasp_executed'],
                       'failed_runtime_gates':failed_gates(r['result']),
                       'valid_video':r['valid_video'],'infrastructure_subtype':r['infrastructure_subtype'],
                       'valid_grasp_video':r['valid_grasp_video'],'video_path':r['video'],
                       'trajectory_sha':r['trajectory_sha256'],'result_sha':r['result_sha256'],
                       'stages':[{key:value for key,value in stage.items() if key!='log_tail'} for stage in r['stages']],
                       'video_sha':r['video_sha256'],'result_path':str(root/'out'/r['id']/'result.json'),
                       'metrics':{key:(r['result'] or {}).get(key) for key in ['max_lift_m','max_wristlocal_slip_alllift_m',
                              'hold_safe_steps','hold_support_steps','max_joint_limit_violation_rad','max_servo_offset_rad']}} for r in rows]
    if stamped:
        first=stamped[0]['result']['runtime_stamp']
        summary['runtime_stamp']={key:first[key] for key in ['mujoco_version','sys_executable','python_version','scene_generator_sha','library_sha','dt']}
        summary['runtime_stamp']['model_sha']={r['id']:r['result']['runtime_stamp']['model_sha'] for r in stamped}
        summary['runtime_stamp']['library_sha']={'common':{key:value for key,value in first['library_sha'].items() if key!='plan'},
            'per_trial_plan':{r['id']:r['result']['runtime_stamp']['library_sha']['plan'] for r in stamped}}
        summary['runtime_stamp']['coverage_count']=len(stamped)
        summary['runtime_stamp']['note']='Aggregate of original per-trial stamps; unsealed contact_frames/planning_refusal diagnostics excluded from numeric citation chain'
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    video_lines = ["# 视频索引", "", "有效视频只说明视频及其result/trajectory源哈希校验通过；抓取执行视频另要求真实抓取执行且从伸臂开始。", "",
                   "| ID | 组 | 终态 | 真实抓取执行 | 有效视频 | 抓取执行视频 | 视频路径 | SHA-256 |", "|---|---|---|---:|---:|---:|---|---|"]
    for r in sorted(rows, key=lambda x: id_key(x["id"])):
        video_lines.append(f"| {r['id']} | {r['group']} | {r['outcome']} | {r['actual_grasp_executed']} | {r['valid_video']} | {r['valid_grasp_video']} | {r['video']} | {r['video_sha256'] or '无'} |")
    (root / "video-index.md").write_text("\n".join(video_lines) + "\n", encoding="utf-8")
    executed = []
    if args.executed_steps and args.executed_steps.exists():
        executed = args.executed_steps.read_text(encoding="utf-8", errors="replace").splitlines()
    actual_commands = args.executed_command or []
    report = ["# 批次总结报告（由真实记录生成）", "", HEADINGS[0], "",
              '主实验成功数：'+ '；'.join(f"{g} {groups[g]['counts']['success']}/{groups[g]['planned_denominator']}" for g in ('A','B','C','D'))+'。物理成功与视频交付分别统计。',
              "A是确定性复现；ARDY仅为姿态先验。MuJoCo3.2.7下的v2基本抓举门，不代表完整Track4或实机。"]
    report += ["", HEADINGS[1], "", "数据目录绝对路径：" + str(root),
               "输入：manifest.json；out/<id>/result.json；out/<id>/replay/replay.json 与 grasp.mp4；state/<id>.json。",
               "建议完整保留各 ID 的配置、执行状态、所有阶段返回码及日志；不要只保留成功项。",
               "步骤记录摘要（最多前80行；完整记录另存并链接）：", '```text'] + (executed[:80] or ["尚未提供已执行步骤记录；不可由脚本推断。"])+['```']
    if args.executed_steps:
        report.append("完整步骤记录：" + str(args.executed_steps.resolve()))
    report += ["", "明确提供的已执行命令："] + (actual_commands or ["尚未提供；命令仅可标为计划，不能冒充已运行。"])
    report += ["", "计划资源边界：bounded、noGPU；须以任务日志/资源记录核实。服务器与本地 Markdown 双端 SHA 核对须附两端路径及摘要，不得由本脚本虚构。",
               "", HEADINGS[2], "", "manifest SHA-256：" + str(summary["manifest_sha256"]),
               '实验定义与资源协议见同目录PROTOCOL.md：A固定(.35,-.18)m/80mm；B x[.33,.37]、y[-.20,-.16]m/80mm；C同位置池、均匀70–90mm；D精确配对C且机器人初始后撤2cm，物体/桌世界坐标不变；均120g。',
               '控制链为ARDY near_s42第99帧姿态先验→几何/参考轨迹规划→SONIC v1.1身体控制＋腕参考辅助修正→独立右手7关节PD；不是完整ARDY时变生成动作驱动。C/D终端按同一世界物体重新规划。',
               '左右整手各7原生碰撞几何及掌/腕碰撞启用，原合成球垫碰撞关闭。自由基座/自由物体、无weld/mocap/物体执行器；仅控制执行器。手指armature=.1、PD40/2；右臂身体PD增益为基准×3、阻尼×sqrt(3)*2，并有重力前馈。模型/增益已调参，不代表实机参数验证。',
               "所有试验 ID 与结果字段见同目录 summary.json；视频逐项核验状态见 video-index.md。",
               "主300与消融60独立汇总：" + json.dumps({"main_300": summary["main_300_total"], "ablation_60": summary["ablation_60_total"]}, ensure_ascii=False),
               "MuJoCo3.2.7；环境、模型/库/权重SHA和dt见summary.json/runtime_stamp。无戳contact_frames及planning_refusal原始诊断不进入数值引用链；门结果以已盖章result.json和trajectory.npz为准。",
               "| 组 | 计划分母 | 终态计数 | success/planned | success/实际抓取 | 有效视频 | 视频缺失/无效 |", "|---|---:|---|---:|---:|---:|---:|"]
    for group, data in groups.items():
        report.append(f"| {group} | {data['planned_denominator']} | {json.dumps(data['counts'], ensure_ascii=False)} | {ratio(data['success_per_planned'])} | {ratio(data['success_per_grasp_execution'])} | {data['valid_video_count']} | {data['missing_video_count']} |")
    report += [
               "成功样例与真实 physics_failure 样例仅从各自组内选最低数值 ID；未找到的类别明确为无样例："]
    report += ['| 组 | 类别 | ID | 抓取执行视频有效 | 服务器视频路径 |','|---|---|---|---|---|']
    for group, data in groups.items():
        for outcome,tid in data['examples_lowest_id'].items():
            example=next((r for r in rows if r['id']==tid),None)
            report.append(f"| {group} | {outcome} | {tid or '无样例'} | {example['valid_grasp_video'] if example else '不适用'} | {example['video'] if example else '无；不借用其他组或消融替代'} |")
    report += ["", "planning_refused 样例 ID："]
    for group, data in groups.items():
        report.append(f"{group}: " + (", ".join(map(str, data["planning_refused_ids"])) or "无") )
    report += ["", "", HEADINGS[3], "", "以下列阶段rc、错误/日志路径及physics reason；基础设施错误附日志尾部，常规physics_failure仅附各组最低ID样例原文；全部阶段记录见summary.json。"]
    report.append('超时/基础设施子类计数：'+json.dumps(summary['infrastructure_subtypes'],ensure_ascii=False))
    initial_audit,initial_audit_error=read_json(root/'audit_batch.json')
    if initial_audit and initial_audit.get('failures'):
        report.append('首次独立审计保留在audit_batch.json/final-audit.log：checked='+str(initial_audit.get('checked'))+'，断言失败数='+str(len(initial_audit['failures']))+'。A沿用旧自有任务meshdir，硬编码新路径XML哈希误报；只读诊断见audit-first-diagnostic.json与robot-identity-diagnostic.json。修正后的audit-final.json逐项检查A旧XML固定SHA、仅meshdir路径替换后精确匹配新XML、且两路径解析到同一只读网格资产。没有重写物理源码、XML、轨迹或成功门；原始失败及audit-v1-source.py均保留。')
    failure_examples = {g: groups[g]["examples_lowest_id"]["physics_failure"] for g in GROUPS}
    for r in rows:
        if r["outcome"] in ("physics_failure", "infrastructure_error", "planning_refused"):
            report.append(f"\nID {r['id']} [{r['group']}] {r['outcome']}: {((r['result'] or {}).get('reason') or (r['result'] or {}).get('error') or '无 result 错误文本')}")
            if r['outcome']=='physics_failure':report.append('未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：'+json.dumps(failed_gates(r['result']),ensure_ascii=False))
            for stage in r["stages"]:
                report.append(f"  stage={stage['stage']} rc={stage['rc']} log={stage['log'] or '无'}")
                tail = safe_log(root, stage["log"], 12000 if r["outcome"] == "infrastructure_error" else 1200)
                if tail and (r["outcome"] == "infrastructure_error" or failure_examples.get(r["group"]) == r["id"]):
                    report += ['```text',tail,'```']
    report += ["", "未完成项目按 not_started 统计；规划拒绝不是物理失败，safe-standing 回放不是抓取执行证据。视频索引有效不等于物理成功。",
               "", HEADINGS[4], "", "逐ID核验planning refusal是否由规划门产生、path阶段是否真的运行、hold/servo退出原因与rc；将gate误差和物理reason关联至同ID配置及轨迹。",
               "成功项复核执行门、hold_pass_steps/hold_safe_steps及关键gate误差；失败项检查首次接触顺序、超时阶段和是否进入真实grasp路径。视频交付单独核对源result与trajectory哈希。",
               "C/D与消融/B按source_baseline_trial配对。pipeline四格比较success与非success，error/not_started另格；valid-physics四格仅含success/physics_failure："]
    for name, pair in pairings.items():
        report.append(f"{name}: pipeline四格={json.dumps(pair['pipeline_four_cells'], ensure_ascii=False)}; 被排除配对的infra/not_started分别计数={json.dumps(pair['excluded_pair_statuses'],ensure_ascii=False)}（两种状态可同时出现，勿相加作分母）；valid-physics四格={json.dumps(pair['valid_physics_four_cells'], ensure_ascii=False)}; 完整物理配对={pair['complete_physics_pairs']}; success差值(target-baseline)={pair['success_difference_target_minus_baseline']}")
    audit_path = root / "audit_batch.py"
    report.append("物理arrays及消融beforeclose独立审计：" + str(root/'audit-final.json'))
    report.append('审计边界：NPZ为每20ms抽样状态；成功门核对使用仿真器每1ms评估后记录的汇总值。核对值与success的一致性，不宣称独立重算全部1ms接触/成功门。视频另经全片解码及逐片身份/源哈希核验。')
    audited,audit_error=read_json(root/'audit-final.json')
    if audited:
        report.append('独立核验格数='+str(audited.get('checked'))+'，致命证据错误='+str(len(audited.get('failures',[])))+'，对拍限制警告='+str(len(audited.get('warnings',[]))))
        if audited.get('warnings'):
            report.append('警告：部分独立重规划输入在控制开关生效前不逐字节相同。最大绝对差及各pair详见audit-final.json；对应消融只能作为同场景描述对照，不能标为严格同输入因果消融。没有事后放宽v2成功门，也没有删除这些样本。')
            warning_groups=Counter(tid[:-3] for tid in {str(w.get('ablation','')) for w in audited['warnings']})
            report.append('实际非同输入配对按组计数：'+json.dumps(dict(warning_groups),ensure_ascii=False)+'；包含NWS时，其独立规划产生的生效前差异亦保留，不以差异小为由改标严格因果。')
        report.append('另逐对核验完整预计算body/hand/wrist参考是否逐字节相同。NGF从t=0生效，没有开关前时间段，不能以空前缀或初始状态相同冒充严格前处理证明；最终只作本版本同场景对照解释。')
    report += ['后续优先级（建议，尚未实施，不改变本批结果）：',
               '1. 新批次将B对照的完整规划/参考固定复制给消融，逐数组核验开关生效前状态与输入，解决非严格同输入问题。',
               '2. 将接近阶段的真实物体接触纳入门，先消除提前碰撞，再改为接触反馈触发闭手/试抬；现有参考几何无穿透不等于动力学无碰撞。',
               '3. 将保持阶段从当前约2.5秒延长至10秒，保留现有高度、对向接触、双足、局部滑移和关节门，记录长时间掉落。',
               '4. 分批拓宽当前±2cm位置、70–90mm边长和120g固定质量的场景；目前不能外推到任意桌面位置/质量。',
               '5. 独立接入完整ARDY时变动作，对照常量/无ARDY先验；并在第二MuJoCo版本同样本复验，之后再谈ARDY贡献与跨版本稳健性。']
    report += ["如需复用姿态先验，应另验证完整动作闭环；本批次 success gate 是 v2 wrist-local-support，不代表 v5/v6。",
               "", HEADINGS[5], "", "仅列操作者传入并标记为已执行的命令："] + (actual_commands or ["无已核实命令记录。"])
    report += ["从全新目录复现前，先按完整路径复制源代码、配置和依赖清单并核验SHA；随后运行已记录的实际命令。计划或帮助命令不得表述为已执行。",
               "逐项复核 summary.json、video-index.md、state 阶段日志；对本地/服务器 Markdown 分别计算 SHA-256 并记录完整路径。",
               "重要：本脚本只汇总现存记录，不启动仿真，不补跑，也不把计划命令写成实测。"]
    (root / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
