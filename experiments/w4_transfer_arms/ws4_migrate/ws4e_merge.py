#!/usr/bin/env python3
"""W4e merge: rep_ext_pd (position-servo arm) x rep_ext_phys (contact-recipe arm)
-> rep_ext_comb.  The two arms' diffs against rep_base overlap on exactly one
line (the run() signature tail); everything else is disjoint.

Method (fully programmatic, nothing hand-transcribed except the two kwarg tails):
  * The phys arm's edits are re-derived live as difflib opcodes rep_base->rep_ext_phys.
  * The PD   arm's edits are re-derived live as difflib opcodes rep_base->rep_ext_pd.
  * route1 = PD content  + phys opcodes ; route2 = phys content + PD opcodes.
    Both routes must come out BYTE-IDENTICAL; that is the containment proof that
    the combined file is exactly base + pd-edits + phys-edits and nothing else.
  * Every opcode is applied by exact old-block search with a count==1 anchor;
    any failed search aborts without writing.  The single overlapping line
    (branch_coverage=False): tail) is merged by the canonical rule
    base + ',' + PD_KW + ',' + PH_KW.
  * rep/finger_control.py changed only in the PD arm -> copied verbatim.
  * run_fixE.sh: route1 only (the BASE= path line is excluded; a final
    rep_ext_pd->rep_ext_comb sed replaces it), plus containment diffs.

Reads: rep_base, rep_ext_pd, rep_ext_phys (all read-only).
Writes: rep_ext_comb/rep/{sonic_grasp.py,finger_control.py}, rep_ext_comb/run_fixE.sh,
        logs/ws4e_merge_*.diff
"""
import difflib, hashlib, sys
from pathlib import Path

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
B, PD, PH, CB = (M / x for x in ('rep_base', 'rep_ext_pd', 'rep_ext_phys', 'rep_ext_comb'))
LOGS = M / 'logs'
LOGS.mkdir(exist_ok=True)

PD_KW = 'finger_pd=None,finger_armature=0.'
PH_KW = 'substep=1,contact_margin=0.,solref=None,impratio=0.'
SIG_SEARCH = 'branch_coverage=False):'
SIG_REPL_PD = f'branch_coverage=False,{PD_KW}):'
SIG_REPL_PH = f'branch_coverage=False,{PH_KW}):'
SIG_MERGED = f'branch_coverage=False,{PD_KW},{PH_KW}):'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rd(p):
    return Path(p).read_text()

def opcodes(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']

def dump_ops(tag, base, other, ops, fh):
    print(f'--- {tag}: {len(ops)} non-equal opcodes', file=fh)
    for t, i1, i2, j1, j2 in ops:
        o, n = base[i1:i2], other[j1:j2]
        print(f'  {t} base[{i1}:{i2}] ({len(o)}L) -> other[{j1}:{j2}] ({len(n)}L)', file=fh)
        print(f'    old[:90]: {o[0].strip()[:90] if o else "<none>"}', file=fh)
        print(f'    new[:90]: {n[0].strip()[:90] if n else "<none>"}', file=fh)

def apply_arm(carrier, base_lines, src_lines, src_name, carrier_kw, fh, skip=None):
    """carrier: full text of the carrier copy; base_lines/src_lines: line lists of the
    base file and of the source arm's file.  Returns merged text."""
    ops = opcodes(base_lines, src_lines)
    dump_ops(f'{src_name} opcodes (applied onto carrier)', base_lines, src_lines, ops, fh)
    out = carrier
    for k, (t, i1, i2, j1, j2) in enumerate(ops):
        old = ''.join(base_lines[i1:i2])
        new = ''.join(src_lines[j1:j2])
        if skip and skip(old, new):
            print(f'  [skip] op{k} {t} old[:60]={old[:60]!r}', file=fh)
            continue
        if old == '':
            # pure insert: anchor on the base line before the insertion point
            anchor = ''.join(base_lines[i1 - 1:i1]) if i1 > 0 else ''
            if not anchor or out.count(anchor) != 1:
                a2 = ''.join(base_lines[i1:i1 + 1]) if i1 < len(base_lines) else ''
                if a2 and out.count(a2) == 1:
                    out = out.replace(a2, new + a2, 1)   # insert before following line
                    print(f'  [insert-before] op{k} anchor={a2.strip()[:60]!r}', file=fh)
                    continue
                print(f'FATAL insert anchor not unique for op{k}: {anchor!r}', file=fh)
                sys.exit(2)
            out = out.replace(anchor, anchor + new, 1)
            print(f'  [insert-after] op{k} anchor={anchor.strip()[:60]!r} (+{new.count(chr(10))}L)', file=fh)
        elif old.endswith(SIG_SEARCH + '\n') and old.count('\n') == 1:
            # the single overlapping edit: run() signature tail
            exp_new = old.replace(SIG_SEARCH, SIG_REPL_PH if src_name == 'phys' else SIG_REPL_PD)
            if new != exp_new:
                print(f'FATAL sig op new_block != expected arm sig. got {new[:120]!r}', file=fh)
                sys.exit(2)
            carrier_sig = old.replace(SIG_SEARCH, 'branch_coverage=False,' + carrier_kw + '):')
            merged = old.replace(SIG_SEARCH, SIG_MERGED)
            if out.count(carrier_sig) != 1:
                print(f'FATAL sig carrier line not found once: {carrier_sig[-80:]!r}', file=fh)
                sys.exit(2)
            out = out.replace(carrier_sig, merged, 1)
            print(f'  [sig-merge] op{k}: tail -> {SIG_MERGED}', file=fh)
        else:
            c = out.count(old)
            if c != 1:
                print(f'FATAL op{k} ({t}) old-block count={c} expected 1.\n--- old[:300]={old[:300]!r}', file=fh)
                sys.exit(2)
            out = out.replace(old, new, 1)
            print(f'  [replace]     op{k} ({t}) {len(old)}L -> {len(new)}L', file=fh)
    return out

def main():
    fh = open(LOGS / 'ws4e_merge.out', 'w')
    def emit(*a):
        print(*a); print(*a, file=fh)

    emit('== W4e merge run ==')
    emit('input shas:')
    for tag, p in [('base', B / 'rep/sonic_grasp.py'), ('pd', PD / 'rep/sonic_grasp.py'), ('phys', PH / 'rep/sonic_grasp.py')]:
        emit(f'  sonic_grasp.py[{tag}] {sha(p)}')
    for tag, p in [('base', B / 'run_fixE.sh'), ('pd', PD / 'run_fixE.sh'), ('phys', PH / 'run_fixE.sh')]:
        emit(f'  run_fixE.sh[{tag}] {sha(p)}')

    # ---------- rep/sonic_grasp.py ----------
    sg_base = rd(B / 'rep/sonic_grasp.py')
    sg_pd = rd(PD / 'rep/sonic_grasp.py')
    sg_ph = rd(PH / 'rep/sonic_grasp.py')
    assert sg_pd != sg_base and sg_ph != sg_base
    bL, pdL, phL = (x.splitlines(keepends=True) for x in (sg_base, sg_pd, sg_ph))
    assert SIG_REPL_PD in sg_pd and SIG_SEARCH in sg_base and SIG_REPL_PH in sg_ph

    emit('\n== route1: pd content + phys opcodes ==')
    r1 = apply_arm(sg_pd, bL, phL, 'phys', PD_KW, fh)
    emit('\n== route2: phys content + pd opcodes ==')
    r2 = apply_arm(sg_ph, bL, pdL, 'pd', PH_KW, fh)

    emit(f'\nroute1 sha256 = {hashlib.sha256(r1.encode()).hexdigest()}')
    emit(f'route2 sha256 = {hashlib.sha256(r2.encode()).hexdigest()}')
    if r1 != r2:
        emit('FATAL routes differ -> abort, no write')
        fh.close(); sys.exit(2)
    emit('ROUTES BYTE-IDENTICAL -> combined rep/sonic_grasp.py = base + pd-edits + phys-edits')
    compile(r1, 'sonic_grasp.py', 'exec')
    emit('py-compile OK')
    for marker in ('finger_position_torques', 'FINGER_CONTROL mode=', 'FINGER_MODEL right_hand_armature=',
                   "--finger-pd", 'W4C_PHYSICS ', 'phys_recipe', 'substep==1:mujoco.mj_step',
                   'if finger_pd is None:d.ctrl[hands]=finger_torques', "'physics_recipe_w4c'", "'finger_control'"):
        assert marker in r1, 'missing marker ' + marker
    emit('both feature marker sets present')
    (CB / 'rep/sonic_grasp.py').write_text(r1)

    # ---------- rep/finger_control.py (pd-only change) ----------
    fc_base = rd(B / 'rep/finger_control.py')
    fc_pd = rd(PD / 'rep/finger_control.py')
    fc_ph = rd(PH / 'rep/finger_control.py')
    assert fc_ph == fc_base, 'phys arm unexpectedly changed finger_control.py'
    assert fc_pd.startswith(fc_base) and len(fc_pd) > len(fc_base), 'pd finger_control not a pure append'
    (CB / 'rep/finger_control.py').write_text(fc_pd)
    emit(f'\nfinger_control.py: pd == base + {len(fc_pd)-len(fc_base)} appended bytes (pure addition); copied')
    emit(f'  comb sha {sha(CB / "rep/finger_control.py")} == pd sha {sha(PD / "rep/finger_control.py")}')

    # ---------- run_fixE.sh ----------
    rn_base = rd(B / 'run_fixE.sh')
    rn_pd = rd(PD / 'run_fixE.sh')
    rn_ph = rd(PH / 'run_fixE.sh')
    bL, pdL, phL = (x.splitlines(keepends=True) for x in (rn_base, rn_pd, rn_ph))
    emit('\n== run_fixE.sh route1: pd content + phys opcodes (BASE= line excluded) ==')
    skip = lambda old, new: old.startswith('BASE=')
    r3 = apply_arm(rn_pd, bL, phL, 'phys', PD_KW, fh, skip=skip)
    assert r3.count('rep_ext_pd') == 1, 'expected exactly the BASE line carrying rep_ext_pd'
    r3 = r3.replace('rep_ext_pd', 'rep_ext_comb')
    (CB / 'run_fixE.sh').write_text(r3)
    emit(f'run_fixE.sh comb sha = {hashlib.sha256(r3.encode()).hexdigest()}')

    # ---------- containment diffs ----------
    pairs = [
        ('sg_base_comb', sg_base, r1), ('sg_pd_comb', sg_pd, r1), ('sg_phys_comb', sg_ph, r1),
        ('run_base_comb', rn_base, r3), ('run_pd_comb', rn_pd, r3), ('run_phys_comb', rn_ph, r3),
    ]
    for tag, a, b in pairs:
        d = ''.join(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True),
                                         fromfile=tag + '_A', tofile=tag + '_B'))
        (LOGS / f'ws4e_merge_{tag}.diff').write_text(d)
        emit(f'diff {tag}: {sum(1 for l in d.splitlines() if l.startswith("@@"))} hunks -> logs/ws4e_merge_{tag}.diff')

    fh.close()

main()
