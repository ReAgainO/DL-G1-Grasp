"""Archive only this finite batch claim, preserving all unrelated Git index blobs.

This file is intentionally not run by its author. Expected input artifacts are
prepared by the task owner after the full batch and independent audit finish.
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import resource

resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
for thread_option in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[thread_option]='1'

T = "20261009-021611-codex-415484ce"
B = Path("/home/group4/group4_dasc7606c")
D = Path("/data/group4") / T
W = B / "work" / T
REPORT = B / "reports" / f"{T}-report.md"
SID = "01a0e195-925b-7fa1-b43f-e6f9391253df"
PLANNED = {"A": 100, "B": 100, "C": 50, "D": 50,
           "NGR": 20, "NWS": 20, "NGF": 20}
TOTAL_PLANNED = sum(PLANNED.values())
ISSUES = B / "work" / "20260930-0310-qoder-issuereg"
ISSUE_IDS = {
    "physics": "ISS-H1-WHOLEHAND-PHYSICS-ARMED-KILLS-R3-SUCCESSES",
    "ardy": "ISS-GRASP-ARDY-ATTRIBUTION-BLOCKED",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now().astimezone().isoformat()


env = os.environ.copy()
for key in ("JOURNAL", "ANCHOR"):
    env.pop(key, None)
env.update({"JOURNAL_BASE": str(B), "GPU_BASE": str(B),
            "ISSUES_BASE": str(B), "PYTHONDONTWRITEBYTECODE": "1"})


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def command(args, label, timeout=120):
    proc = subprocess.run(args, cwd=B, env=env, capture_output=True,
                          timeout=timeout)
    log = D / "logs" / f"archive-{label}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("xb") as stream:
        stream.write(proc.stdout + b"\nSTDERR\n" + proc.stderr)
    if proc.returncode:
        raise RuntimeError(f"{label} rc={proc.returncode}: " +
                           (proc.stdout + proc.stderr).decode(errors="replace")[-3000:])
    return proc.stdout.decode(errors="replace")


def git(*args):
    proc = subprocess.run(["git", "-C", str(B), *args], capture_output=True,
                          timeout=120)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    return proc.stdout


def own_ledger_snapshot(label):
    journal_lines = (B / "claims" / "journal.log").read_text(encoding="utf-8").splitlines()
    own_events = []
    for number, line in enumerate(journal_lines, 1):
        event = json.loads(line)
        if event.get("task") == T:
            own_events.append({"journal_line": number, "raw_json": line})
    own_index_rows = [line for line in (B / "claims" / "INDEX.md").read_text(encoding="utf-8").splitlines()
                      if line.startswith(f"| {T} |")]
    snapshot = {
        "captured": now(),
        "master_journal_total_lines_at_read": len(journal_lines),
        "own_events": own_events,
        "index_own_rows": own_index_rows,
        "scope": "own-row evidence only; shared journal tail is not swept into this task commit",
    }
    write_new(W / f"own-ledger-{label}.json", snapshot)
    return snapshot


def mapping(index_dump):
    result = {}
    for entry in index_dump.split(b"\0"):
        if entry:
            metadata, path = entry.split(b"\t", 1)
            result[path.decode()] = metadata.decode()
    return result


def commit_own(label):
    targets = [B / "claims" / T / "card.txt",
               B / "claims" / T / "rules_seen",
               B / "claims" / T / "rules_seen_after",
               B / "logs" / T / "steps.md", REPORT]
    targets.extend(W.rglob("*"))
    done = B / "claims" / T / "done.txt"
    if done.exists():
        targets.append(done)
    paths = sorted({str(path.relative_to(B)) for path in targets if path.is_file()})
    allowed = (f"claims/{T}/", f"logs/{T}/", f"work/{T}/")
    assert all(path.startswith(allowed) or path == f"reports/{T}-report.md" for path in paths), paths
    assert not git("ls-files", "--unmerged").strip(), "unmerged index entries; stop without committing"

    previous_head = git("rev-parse", "HEAD").decode().strip()
    staged_before = git("ls-files", "--stage", "-z")
    git_index = git("rev-parse", "--git-path", "index").decode().strip()
    index_path = Path(git_index)
    if not index_path.is_absolute():
        index_path = B / index_path
    backup_dir = D / "git"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(index_path, backup_dir / f"index-{label}.backup")
    (backup_dir / f"staged-{label}-before.bin").write_bytes(staged_before)

    before_map = mapping(staged_before)
    overlaps = [path for path in paths if path in before_map and
                git("diff", "--cached", "--name-only", "--", path).strip()]
    if overlaps:
        raise RuntimeError("own paths already have staged edits; preserve and inspect before commit: " + repr(overlaps))

    git("add", "-f", "--", *paths)
    identity = ["-c", f"user.name=Codex hp {SID}",
                "-c", f"user.email=codex-{SID}@worker00039.invalid"]
    commit_env = env.copy()
    for role in ("AUTHOR", "COMMITTER"):
        commit_env[f"GIT_{role}_NAME"] = f"Codex hp {SID}"
        commit_env[f"GIT_{role}_EMAIL"] = f"codex-{SID}@worker00039.invalid"
    proc = subprocess.run(["git", "-C", str(B), *identity, "commit", "--only",
                           "-m", f"Archive audited finite batch {T} {label}", "--", *paths],
                         env=commit_env, capture_output=True, timeout=120)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace") + proc.stdout.decode(errors="replace"))

    commit_hash = git("rev-parse", "HEAD").decode().strip()
    after_map = mapping(git("ls-files", "--stage", "-z"))
    unrelated_before = {path: blob for path, blob in before_map.items() if path not in paths}
    unrelated_after = {path: blob for path, blob in after_map.items() if path not in paths}
    assert unrelated_before == unrelated_after, "unrelated staged blobs changed; do not reset the index"
    changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash).decode().splitlines()
    assert changed and set(changed) <= set(paths), changed
    report_blob = git("show", f"{commit_hash}:reports/{T}-report.md")
    assert hashlib.sha256(report_blob).hexdigest() == sha(REPORT)
    receipt = {"timestamp": now(), "previous_head": previous_head,
               "commit": commit_hash, "explicit_paths": paths,
               "changed_paths": changed, "unrelated_staged_blobs_preserved": True,
               "report_blob_sha": sha(REPORT), "no_push": True}
    write_new(D / f"git-{label}.json", receipt)
    return receipt


def read_groups(summary):
    """Normalize actual per-group counts; never infer success from a target total."""
    groups = summary.get("groups", summary.get("by_group", summary.get("group_counts")))
    if isinstance(groups, list):
        groups = {row.get("group", row.get("name")): row for row in groups}
    if not isinstance(groups, dict):
        raise ValueError("summary.json must contain per-group data under groups/by_group/group_counts")

    normalized = {}
    for group, planned in PLANNED.items():
        row = groups.get(group)
        if not isinstance(row, dict):
            raise ValueError(f"summary.json missing group row {group}")
        actual_planned = row.get("planned_denominator",row.get("planned", row.get("expected")))
        statuses = row.get("counts",row.get("terminal_status_counts", row.get("outcomes", row.get("status_counts"))))
        terminal = row.get("terminal", row.get("terminal_count", row.get("finished")))
        success = row.get("success", row.get("success_count"))
        if isinstance(statuses, dict):
            terminal = sum(int(value) for key,value in statuses.items() if key!='not_started')
            success = statuses.get("success", success)
        if actual_planned is None or terminal is None or success is None:
            raise ValueError(f"summary group {group} needs actual planned, terminal/outcome, and success counts")
        video_valid = row.get("valid_video_count",row.get("video_valid", row.get("valid_videos", row.get("videos_valid"))))
        if video_valid is None:
            videos = row.get("videos")
            if isinstance(videos, dict):
                video_valid = videos.get("valid")
        if video_valid is None:
            raise ValueError(f"summary group {group} missing actual valid-video count")
        normalized[group] = {"planned": int(actual_planned), "terminal": int(terminal),
                             "success": int(success), "video_valid": int(video_valid),
                             "raw": row}
        if normalized[group]["planned"] != planned:
            raise AssertionError(f"planned count mismatch for {group}: {normalized[group]['planned']}")
        if not 0 <= normalized[group]["success"] <= normalized[group]["terminal"] <= planned:
            raise AssertionError(f"invalid actual counts for {group}: {normalized[group]}")
        if not 0 <= normalized[group]["video_valid"] <= planned:
            raise AssertionError(f"invalid video count for {group}: {normalized[group]}")
    return normalized


def audit_passes(audit):
    failures = audit.get("failures", audit.get("audit_failures"))
    if isinstance(failures, list):
        has_failures = len(failures) > 0
    elif isinstance(failures, dict):
        has_failures = any(int(value) > 0 for value in failures.values()
                           if isinstance(value, (int, float)))
    elif failures is None:
        has_failures = False
    else:
        has_failures = int(failures) > 0
    for key in ("fail_count", "failed", "audit_fail_count"):
        if key in audit and int(audit[key]) > 0:
            has_failures = True
    explicit_pass = audit.get("passed") is True or str(audit.get("status", "")).lower() in {"pass", "passed", "ok"}
    explicit_zero = failures in (0, "0") or isinstance(failures, list) and len(failures) == 0
    return not has_failures and (explicit_pass or explicit_zero)


def load_evidence():
    summary_path = D / "summary.json"
    audit_path = D / "audit-final.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    videos=json.loads((D/'video-verification.json').read_text())
    assert videos['checked_videos']==360 and not videos['failures'] and len({row['id'] for row in videos['videos']})==360,'independent video verification incomplete'
    groups = read_groups(summary)
    manifest = json.loads((D / "manifest.json").read_text(encoding="utf-8"))
    assert videos['manifest_sha']==sha(D/'manifest.json') and videos['source_sha']==sha(D/'verify_videos.py'),'video evidence belongs to another manifest/verifier'
    assert audit['manifest_sha']==sha(D/'manifest.json') and audit['audit_source_sha']==sha(D/'audit_batch.py'),'audit evidence belongs to another manifest/auditor'
    assert len(videos['videos'])==360 and {row['id'] for row in videos['videos']}=={row['id'] for row in manifest['trials']},'video ID set differs from manifest'
    for row in videos['videos']:
        out=D/'out'/row['id']
        assert row['video_sha']==sha(out/'replay/grasp.mp4'),'video changed after independent verification'
        assert row['source_result_sha']==sha(out/'result.json'),'result changed after independent verification'
        assert row['source_trajectory_sha']==sha(out/'trajectory.npz'),'trajectory changed after independent verification'
    actual_manifest_counts = {}
    for trial in manifest.get("trials", []):
        actual_manifest_counts[trial["group"]] = actual_manifest_counts.get(trial["group"], 0) + 1
    assert actual_manifest_counts == PLANNED, "frozen manifest groups do not match the registered finite design"
    terminal_total = sum(row["terminal"] for row in groups.values())
    video_total = sum(row["video_valid"] for row in groups.values())
    assert terminal_total == TOTAL_PLANNED, f"not all planned rows have terminal states: {terminal_total}/{TOTAL_PLANNED}"
    assert video_total == TOTAL_PLANNED, f"not all planned rows have valid real-state videos: {video_total}/{TOTAL_PLANNED}"
    assert audit_passes(audit), "audit-final.json does not certify a passing audit with zero failures"
    audit_total = audit.get("checked",audit.get("terminal_total", audit.get("rows_audited", audit.get("total"))))
    if audit_total is not None:
        assert int(audit_total) == TOTAL_PLANNED, "audit count differs from the finite design"
    audit_video = audit.get("video_valid_total", audit.get("valid_videos"))
    if audit_video is not None:
        assert int(audit_video) == TOTAL_PLANNED, "audit video count differs from the finite design"
    return summary, audit, manifest, groups, terminal_total, video_total


def process_check():
    text = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                          text=True, check=True).stdout
    active = []
    for line in text.splitlines():
        if T not in line or "archive_batch.py" in line or "status_batch.py" in line:
            continue
        if any(name in line for name in ("batch_runner.py", "execute_batch.py", "render_batch.py")):
            active.append(line)
    if active:
        raise RuntimeError("task batch/render process remains active: " + repr(active))
    return text


def git_preflight():
    assert not git('ls-files','--unmerged').strip(),'unmerged index; stop before ledger closure'
    own=[f'claims/{T}/',f'logs/{T}/',f'work/{T}/',f'reports/{T}-report.md']
    assert not git('diff','--cached','--name-only','--',*own).strip(),'own paths have preexisting staged edits; preserve before closure'
    return {'head':git('rev-parse','HEAD').decode().strip(),
            'index_stage_sha':hashlib.sha256(git('ls-files','--stage','-z')).hexdigest()}


def own_rules_after():
    claim = B / "claims" / T
    rules_hash = sha(B / "AGENTS.md")
    seen = (claim / "rules_seen").read_text(encoding="utf-8").split()[0]
    assert rules_hash == seen, "current AGENTS.md differs from the task's rules_seen; stop and read changes"
    after = claim / "rules_seen_after"
    with after.open("x", encoding="utf-8") as stream:
        stream.write(f"{rules_hash}  AGENTS.md\n")
    return rules_hash


def verify_expectations():
    expectation = json.loads((W / "archive-expectations.json").read_text(encoding="utf-8"))
    checked = {"mirror": {}, "data": {}, "local_artifacts": {}}
    for section in checked:
        for path, expected in expectation.get(section, {}).items():
            actual_path = Path(path)
            if not actual_path.is_absolute():
                actual_path = B / actual_path
            actual = sha(actual_path)
            assert actual == expected, f"{section} SHA mismatch: {path}"
            checked[section][path] = actual
    assert checked["mirror"], "archive expectations must include mirrored B-side artifacts"
    assert checked["data"], "archive expectations must include /data artifacts"
    return checked


def append_steps(body):
    with (B / "logs" / T / "steps.md").open("a", encoding="utf-8") as stream:
        stream.write("\n" + body.rstrip() + "\n")


def group_counts_text(groups):
    return "; ".join(f"{name}: success={row['success']}/{row['planned']}, "
                      f"terminal={row['terminal']}/{row['planned']}, "
                      f"valid_video={row['video_valid']}/{row['planned']}"
                      for name, row in groups.items())


def issue_note(issue_id, title, body, label):
    raw=(B/'claims/issues.jsonl').read_text()
    history=[json.loads(line) for line in raw.splitlines() if json.loads(line).get('issue')==issue_id]
    if not history:
        raise RuntimeError(f"existing issue not found; will not create or guess one: {issue_id}")
    state=history[-1]['state']
    if state=='CLOSED':
        append_steps(f'Existing issue {issue_id} is CLOSED; left untouched, finite evidence remains in own report.')
        return
    assert state in ('OPEN','BLOCKED','WATCH'),('unexpected issue state',issue_id,state)
    append = ISSUES / "issue_append.sh"
    command(["bash", str(append), issue_id, "note", state, title, body,
             "--field", f"reporter_task={T}", "--field", f"evidence={REPORT}"],
            f"issue-note-{label}")


def prepare():
    checked_hashes = verify_expectations()
    current_rules = own_rules_after()
    summary, audit, manifest, groups, terminal_total, video_total = load_evidence()
    process_check()
    git_preflight()
    issue_rows=[json.loads(line) for line in (B/'claims/issues.jsonl').read_text().splitlines()]
    assert all(any(row.get('issue')==issue_id for row in issue_rows) for issue_id in ISSUE_IDS.values()),'precheck both existing issues before any note'

    # Concise experiment summary for existing issues. It uses observed summaries,
    # and states limits explicitly; no issue is closed or created here.
    counts = group_counts_text(groups)
    limits = ("Finite batch only; fixed A is deterministic repeat stability, not a generalization rate. "
              "B/C/D are limited to the registered sampling domains and this MuJoCo 3.2.7 build. "
              "v2 gates only; this does not complete full Track 4 or establish real-robot performance.")
    issue_note(ISSUE_IDS["physics"], "Finite native whole-hand batch results",
               f"Observed groups: {counts}. Terminal rows and valid real-state videos were read from summary.json and audit-final.json ({terminal_total}/{TOTAL_PLANNED}; {video_total}/{TOTAL_PLANNED}). {limits} Evidence: {REPORT}; {D / 'audit-final.json'}.", "physics")
    issue_note(ISSUE_IDS["ardy"], "Batch evidence and ARDY attribution limits",
               f"Observed groups: {counts}. This finite batch measures the registered SONIC/MuJoCo configuration; it does not by itself attribute causal contribution to ARDY or demonstrate full Track 4. {limits} Evidence: {REPORT}; {D / 'summary.json'}; {D / 'audit-final.json'}.", "ardy")
    issue_verify = command(["bash", str(ISSUES / "issue_verify.sh")], "issue-verify")

    # Preserve recorded execution mistakes and evidence by linking to the task's
    # real audit and steps files; never invent a failure or claim every run passed.
    audit_notes = {}
    for key in ("failures", "warnings", "errors", "findings", "issues"):
        value = audit.get(key)
        if value:
            audit_notes[key] = value if isinstance(value, (str, int, float, bool)) else value[:20] if isinstance(value, list) else value
    steps_evidence = {
        "recorded_group_counts": groups,
        "audit_findings_or_errors_excerpt": audit_notes,
        "manifest_sha": sha(D / "manifest.json"),
        "audit_sha": sha(D / "audit-final.json"),
        "summary_sha": sha(D / "summary.json"),
        "evidence_note": "See per-attempt steps, results ledger, audit findings, and retained error logs; this archive note does not replace them.",
    }
    append_steps("## Archive preparation evidence\n" + json.dumps(steps_evidence, indent=2, ensure_ascii=False) +
                 "\nNo server-wide journal tail is appended or committed by this task. Any execution errors remain in their original rows/logs.\n")
    ledger = own_ledger_snapshot("preclose")
    precheck = {"timestamp": now(), "rules_sha": current_rules,
                "runtime_stamp":summary['runtime_stamp'],
                "checked_hashes": checked_hashes,
                "summary_sha": sha(D / "summary.json"),
                "audit_sha": sha(D / "audit-final.json"),
                "manifest_sha": sha(D / "manifest.json"),
                "groups_actual": groups,
                "terminal_total_actual": terminal_total,
                "valid_video_total_actual": video_total,
                "audit_pass": True, "task_heavy_processes_absent": True,
                "issue_verify_tail": issue_verify[-1800:],
                "own_ledger_cutoff": ledger["master_journal_total_lines_at_read"],
                "scope": "finite 300+60 batch only; not full Track 4"}
    write_new(W / "archive-precheck.json", precheck)
    initial_git = commit_own("initial")
    receipt = {**precheck, "initial_git": initial_git, "no_push": True}
    write_new(D / "archive-receipt.json", receipt)
    shutil.copy2(D / "archive-receipt.json", W / "archive-receipt.json")
    assert sha(D/'archive-receipt.json')==sha(W/'archive-receipt.json')
    append_steps("Initial explicit-path archive verified: " + json.dumps(initial_git, ensure_ascii=False) +
                 "\nNo push; unrelated staged blobs preserved. Finite batch is not full Track 4.\n")
    print(json.dumps({"phase": "prepared", "commit": initial_git["commit"],
                      "evidence": "archived; see task receipts"}, ensure_ascii=False))


def close():
    assert (D / "archive-receipt.json").is_file(), "prepare must complete first"
    verify_expectations()
    rules_after = (B / "claims" / T / "rules_seen_after").read_text(encoding="utf-8").split()[0]
    assert sha(B / "AGENTS.md") == rules_after, "AGENTS.md changed after rules_seen_after; stop and review the diff"
    summary, audit, manifest, groups, terminal_total, video_total = load_evidence()
    process_check()
    preflight=git_preflight()
    for target in [D/'close-receipt.json',W/'close-receipt.json',W/'own-ledger-postclose.json',D/'git-final.json']:
        assert not target.exists(),('close output already exists; inspect without repeating ledger close',str(target))
    assert shutil.disk_usage('/home').free>256*1024**2
    assert shutil.disk_usage(D).free>1024**3
    command(['bash',str(B/'work/journal/tools2/journal_verify.sh'),'--base',str(B)],'journal-preclose-verify')
    own = [json.loads(line) for line in (B / "claims" / "journal.log").read_text(encoding="utf-8").splitlines()
           if json.loads(line).get("task") == T]
    assert not any(row.get("event") == "done" for row in own), "already done; do not append a duplicate done event"

    # Refuse closure unless all planned rows reached a terminal state, every one
    # has an audited valid state video, and the audit reports no failures.
    assert terminal_total == TOTAL_PLANNED
    assert video_total == TOTAL_PLANNED
    assert audit_passes(audit)
    assert all(groups[name]["terminal"] == planned and groups[name]["video_valid"] == planned
               for name, planned in PLANNED.items())
    detail = group_counts_text(groups)
    close_summary = (f"Finite 300+60 batch finished and audited under MuJoCo 3.2.7; observed group counts: {detail}. "
                     "All planned rows have terminal states and valid real-state videos, and audit_batch reports no failures. "
                     "A is deterministic repeat stability, not generalization; v2 gates only. This closes only this finite batch milestone, not full Track 4, ARDY attribution, or real-robot validation.")
    close_output = command(["bash", str(B / "work" / "p0lock" / "close_ledger.sh"),
                            T, "-", close_summary, "done"], "close-ledger")
    journal_verify = command(["bash", str(B / "work" / "journal" / "tools2" / "journal_verify.sh"),
                              "--base", str(B)], "journal-verify")
    ledger = own_ledger_snapshot("postclose")
    assert len(ledger["index_own_rows"]) == 1 and "| done |" in ledger["index_own_rows"][0]
    done = B / "claims" / T / "done.txt"
    assert done.is_file() and done.stat().st_size > 0
    close_receipt = {
        "timestamp": now(), "close_output": close_output,
        "runtime_stamp":summary['runtime_stamp'],
        "journal_verify_tail": journal_verify[-3000:],
        "done_sha": sha(done), "own_index_row": ledger["index_own_rows"][0],
        "journal_cutoff": ledger["master_journal_total_lines_at_read"],
        "groups_actual": groups, "terminal_total_actual": terminal_total,
        "valid_video_total_actual": video_total, "audit_sha": sha(D / "audit-final.json"),
        "summary_sha": sha(D / "summary.json"),
        "scope": "finite 300+60 batch only; not full Track 4",
        "no_push": True,
        "git_preclose_preflight":preflight,
    }
    write_new(D / "close-receipt.json", close_receipt)
    shutil.copy2(D / "close-receipt.json", W / "close-receipt.json")
    assert sha(D/'close-receipt.json')==sha(W/'close-receipt.json')
    append_steps("## Finite batch closed\n" + json.dumps(close_receipt, indent=2, ensure_ascii=False) +
                 "\nShared journal tails are not committed under this task author. No global close mechanism invoked.\n")
    final_git = commit_own("final")
    print(json.dumps({"phase": "closed", "commit": final_git["commit"],
                      "evidence": "finite milestone archived; no push"}, ensure_ascii=False))


if __name__ == "__main__":
    assert Path(__file__).resolve().parent == D, "run this script only from the task-specific server work directory"
    modes = {"prepare": prepare, "close": close}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("usage: archive_batch.py {prepare|close}")
    modes[sys.argv[1]]()
