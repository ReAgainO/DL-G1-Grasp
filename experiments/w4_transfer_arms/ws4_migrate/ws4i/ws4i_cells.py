#!/usr/bin/env python3
"""W4i cell summarizer: lift / slip / gates / phase trace / pad-contact audit / FK check.
Usage: ws4i_cells.py CELL [CELL ...]
"""
import json, sys, gzip, csv, io, collections
from pathlib import Path
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
for name in sys.argv[1:]:
    rp = M / 'rep_ext_w1' / 'raw' / (name + '.result.json')
    if not rp.exists():
        print('%-10s MISSING %s' % (name, rp)); continue
    r = json.loads(rp.read_text())
    g = r['gates']; nred = sum(1 for v in g.values() if not v)
    lift = r.get('max_lift_m') * 1e3 if r.get('max_lift_m') is not None else None
    slip = r.get('hold_slip_m')
    slip = ('%.1f' % (slip * 1e3)) if (slip is not None and slip < 1e8) else 'NA'
    ev = [(e['phase'], round(e['time_s'], 3)) for e in r.get('events', [])]
    ws = r.get('w4h_preset_seat') or {}
    fk = ws.get('fk_check', {})
    print('%-9s fail=%-28s dur=%.1fs lift=%.1fmm slip=%smm red=%d' % (name, r.get('fail_reason'), r.get('duration_s', 0), lift if lift is not None else -1, slip, nred))
    print('   phases: %s' % ev)
    print('   gates_false: %s' % [k for k, v in g.items() if not v])
    print('   fk: %s dev=%s gaps=%s released_at=%s weld_active_steps=%s' % (
        fk.get('mode'), round(fk.get('dev_mm', -1), 4) if 'dev_mm' in fk else fk.get('drift_mm'),
        [round(x, 2) for x in fk.get('gaps_mm', [])], ws.get('released_at_s'), ws.get('weld_active_steps_lift_hold')))
    ca = r.get('contact_audit_summary', {})
    allst = ca.get('all_steps', {})
    for k in ('pad', 'wrist', 'other_robot', 'support', 'table'):
        if k in allst:
            v = allst[k]
            print('   contact[%s] loaded_steps=%s maxN=%.2f maxUp=%.2f minVert=%.2f' % (
                k, v.get('loaded_steps'), v.get('max_normal_N', 0), v.get('max_upward_force_N', 0), v.get('min_vertical_force_N', 0)))
    hold = ca.get('hold', {})
    if hold:
        for k, v in hold.items():
            if isinstance(v, dict): print('   hold[%s] %s' % (k, v))
    cp = M / 'rep_ext_w1' / 'rep' / 'out' / name / 'cube_contacts.csv.gz'
    if cp.exists():
        txt = gzip.open(cp, 'rt').read().split('\n')
        hdrs = [l for l in txt if l.startswith('# time_s')]
        if hdrs:
            rows = list(csv.DictReader(io.StringIO('\n'.join([hdrs[0][2:]] + [l for l in txt if l and not l.startswith('#')]))))
            agg = collections.defaultdict(lambda: [0, 0.])
            for x in rows:
                agg[(x['other_body'], x['category'])][0] += 1
                agg[(x['other_body'], x['category'])][1] = max(agg[(x['other_body'], x['category'])][1], abs(float(x['contact_fn_N'])))
            print('   contacts: %s' % {('%s|cat%s' % k): (v[0], round(v[1], 2)) for k, v in sorted(agg.items(), key=lambda kv: -kv[1][1])})
