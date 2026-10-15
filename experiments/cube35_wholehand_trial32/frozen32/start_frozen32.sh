set -euo pipefail
T=20261008-202654-codex-182c4568
D=/data/group4/$T
cd "$D/frozen32"
NAME="${1:-repro32_$(date +%Y%m%d_%H%M%S)}"
[[ "$NAME" =~ ^[A-Za-z0-9_-]+$ ]] || { printf 'Invalid run name\n' >&2; exit 2; }
[ ! -e "out/$NAME" ] || { printf 'Output exists, choose another run name\n' >&2; exit 2; }
python3 - <<'PY'
from pathlib import Path
import hashlib,json
r=Path.cwd();m=json.loads((r/'FROZEN-MANIFEST.json').read_text());assert m['complete']
for n,h in m['manifest_files'].items():
 p=(r/n).resolve();assert p.is_relative_to(r.resolve());assert hashlib.sha256(p.read_bytes()).hexdigest()==h,n
print('Frozen controller, reference, model and weights fingerprints verified.')
PY
printf '\n## Manual frozen32 reproduction %s\nCurrent frozenfilehashes verified; fixed35mm/base-.06; body29 actualofficialSONIC; hand7 originalgeometry; ownCPU122,123 nice19 hard480s; nohupPID below. Newrun output never replaces positive/negative evidence.\n' "$NAME" >> /home/group4/group4_dasc7606c/logs/$T/steps.md
nohup timeout --signal=TERM --kill-after=5s 480 taskset -c 122,123 nice -n19 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MUJOCO_GL=disable PYTHONPATH="$D/pydeps" /data/group4/20261004-205550-qoder-1280b420/env/bin/python -B normal_runner32.py "$NAME" > "$D/runlogs/$NAME.log" 2>&1 < /dev/null &
pid=$!;printf '%s\n' "$pid" > "$D/runlogs/$NAME.pid"
printf 'Run=%s PID=%s\nLog=%s/runlogs/%s.log\nResult=%s/frozen32/out/%s/result.json\n' "$NAME" "$pid" "$D" "$NAME" "$D" "$NAME"
