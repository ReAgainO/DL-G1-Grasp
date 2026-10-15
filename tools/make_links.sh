#!/usr/bin/env bash
# make_links.sh — recreate the in-lane symlinks that existed on the source node but cannot be carried by git.
#
# Why this is needed: three runs import the shared runtime with
#     sys.path.insert(0, str(ROOT/'lib'))          # src/sonic_v11_runtime
# so without lib/ the very first import fails. Run this from the repo root:
#     bash tools/make_links.sh            # Linux/macOS
#     bash tools/make_links.sh --copy     # if symlinks are not permitted (copies instead)
set -uo pipefail
cd "$(dirname "$0")/.."
SRC=src/sonic_v11_runtime
MODE=${1:-link}

mk() {  # mk <link-path> <relative-target>
  local lp=$1 tg=$2 dir
  dir=$(dirname "$lp")
  [ -d "$dir" ] || { printf 'SKIPDIR %s\n' "$dir"; return; }
  case "$MODE" in
    --copy) rm -rf "$lp"; [ -e "$dir/$tg" ] && { cp -rL "$dir/$tg" "$lp"; printf 'COPY %s\n' "$lp"; } ;;
    *) rm -rf "$lp"; ln -s "$tg" "$lp" && printf 'LINK %-58s -> %s\n' "$lp" "$tg" ;;
  esac
}

for R in experiments/cube80_sideways_wholehand experiments/batch_wholehand_360 experiments/hand_jitter_analysis; do
  mkdir -p "$R/lib"
  for m in sonic_v11 src official_refs pydeps; do
    mk "$R/lib/$m" "../../../$SRC/$m"
  done
done
# vendored scipy for Python 3.10 lived in the batch run and was symlinked by the jitter run
mk "experiments/hand_jitter_analysis/plandeps310" "../batch_wholehand_360/plandeps310"

cat <<'TXT'

Notes
1) lib/pydeps points at third-party packages (onnxruntime / PyYAML / flatbuffers) that are deliberately
   not in this repo, so that link has no target here. Use requirements.txt instead.
2) experiments/cube35_wholehand_trial32/rep/src never existed on the node either; this script does not
   invent it. That run is documented as "results verifiable, not re-runnable".
3) Links into the node's shared virtualenv (/data/group4/<taskid>/env) are not recreated: that
   interpreter belongs to another task. See docs/REPRODUCTION.md for the portable equivalent.
TXT
