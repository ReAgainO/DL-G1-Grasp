#!/usr/bin/env python3
"""Lane A2 predicate extractor. Read-only over result.json / telemetry.csv.gz.

Usage:
  a2_metrics.py <COPY_ROOT> <name> [<name> ...]        # per-run predicate row
  a2_metrics.py <COPY_ROOT> --divergence A B           # block-side divergence

Predicate (frozen before any run, see FINDING.md):
  success arm  : result.success == true  AND |hold_min_lift_m*1000 - 125.7953698876788| <= 1.0 mm
  control arm  : result.success == false
  divergence   : the two arms' block-side readings must NOT be byte-identical
`rc` is never used as a success bit.
"""
import gzip
import json
import os
import sys

ANCHOR_HOLD_MM = 125.7953698876788
ANCHOR = '/data/group4/20261006-093203-codex-6385a841/out/w7_repeat327/result.json'
CUBE_FIELDS = ['hold_min_lift_m', 'hold_slip_m', 'max_lift_m', 'max_drift_m',
               'final_table_min_force_last100ms_N', 'hold_min_contact_bodies']
CONFIG_FIELDS = ['no_grip', 'strict_execution_gate_enabled', 'independent_finger_kp_gain',
                 'grip_preload_mm', 'table_front_x_m', 'requested_postcapture_lift_height_m',
                 'opposing_pad', 'close_command_duration_s', 'preclosure_contact_dwell_s',
                 'right_arm_gravity_feedforward_scale', 'neutral_shoulder_offset_rad',
                 'preclosure_capture_radius_m', 'c2_reference', 'flat_pinch', 'surface_capture',
                 'phase_clips_loaded', 'direct_table', 'grip_frame_lift', 'adaptive_hand',
                 'clearance_approach', 'post_clearance_native_branch_enabled',
                 'post_clearance_branch_servo_enabled', 'kinematic_outer_servo',
                 'base_fixture', 'free_base_exercised', 'body_action_override',
                 'peak_external_force', 'fixture_constraint', 'sonic_armature',
                 'passive_free_diagnostic', 'setdown_enabled', 'finger_table_clearance_mm']


def load(root, name):
    p = os.path.join(root, 'out', name, 'result.json')
    with open(p) as f:
        return json.load(f), p


def brief(v):
    if isinstance(v, dict):
        return ('dict(enabled=%s)' % v.get('enabled', v.get('kind', '?')))[:60]
    return json.dumps(v)


def row(root, name):
    d, p = load(root, name)
    hold = d.get('hold_min_lift_m')
    hold_mm = None if not isinstance(hold, (int, float)) else hold * 1000.0
    delta = None if hold_mm is None else abs(hold_mm - ANCHOR_HOLD_MM)
    red = [k for k, v in (d.get('gates') or {}).items() if v is not True]
    ls = d['runtime_stamp']['library_sha']
    print('== %s' % name)
    print('   result_json           = %s' % p)
    print('   success               = %s' % json.dumps(d.get('success')))
    print('   hold_min_lift_mm      = %s' % ('%.10f' % hold_mm if hold_mm is not None else 'None'))
    print('   |delta| vs anchor mm  = %s   (anchor %.10f, predicate <= 1.0)'
          % ('%.10f' % delta if delta is not None else 'None', ANCHOR_HOLD_MM))
    print('   PRED_success_arm      = %s' % (d.get('success') is True and delta is not None and delta <= 1.0))
    print('   PRED_control_arm      = %s' % (d.get('success') is False))
    print('   fail_reason           = %s' % json.dumps(d.get('fail_reason'))[:200])
    print('   red_gates(%d)          = %s' % (len(red), json.dumps(red)))
    print('   mujoco                = %s' % d['runtime_stamp']['mujoco_version'])
    print('   scene_generator_sha   = %s' % d['runtime_stamp'].get('scene_generator_sha'))
    print('   sonic_v11_sha         = %s' % ls.get('sonic_v11'))
    print('   native_npz_sha        = %s' % ls.get('native_npz'))
    print('   input_profile_sha     = %s' % ls.get('input_profile', '<ABSENT>'))
    print('   motion_profile        = %s' % brief(d.get('motion_profile')))
    print('   duration_s / wall_s   = %s / %s' % (d.get('duration_s'), d.get('wall_s')))
    for k in CUBE_FIELDS:
        print('   %-22s= %s' % (k, json.dumps(d.get(k, '<MISSING>'))))
    for k in CONFIG_FIELDS:
        print('   cfg %-19s= %s' % (k, brief(d.get(k, '<MISSING>'))))
    rf = d.get('reference_filter') or {}
    print('   cfg reference_fallback  = continue_certified_enabled=%s certified_continuation_steps=%s'
          % (rf.get('continue_certified_enabled'), rf.get('certified_continuation_steps')))
    return d


def telemetry(root, name):
    p = os.path.join(root, 'out', name, 'telemetry.csv.gz')
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    hdr = [c for c in lines[0].lstrip('# ').split(',') if c]
    # header may be on the second line if line0 is a runtime_stamp comment
    start = 1
    if not any(c.startswith('time') for c in hdr):
        hdr = [c for c in lines[1].lstrip('# ').split(',') if c]
        start = 2
    body = '\n'.join(lines[start:])
    idx = {c: i for i, c in enumerate(hdr)}
    cols = {}
    for c in ('cube_x_m', 'cube_y_m', 'cube_z_m'):
        if c in idx:
            cols[c] = [ln.split(',')[idx[c]] for ln in body.splitlines() if ln.strip()]
    return hdr, cols, body, p


def divergence(root, a, b):
    print('== divergence %s vs %s' % (a, b))
    ha, ca, ba, pa = telemetry(root, a)
    hb, cb, bb, pb = telemetry(root, b)
    print('   telemetry: %s' % pa)
    print('              %s' % pb)
    print('   rows_a=%d rows_b=%d header_identical=%s'
          % (len(ba.splitlines()), len(bb.splitlines()), ha == hb))
    all_identical = True
    for c in ('cube_x_m', 'cube_y_m', 'cube_z_m'):
        if c not in ca or c not in cb:
            print('   %s MISSING' % c)
            all_identical = False
            continue
        sa, sb = ','.join(ca[c]), ','.join(cb[c])
        ident = sa == sb
        all_identical = all_identical and ident
        n = min(len(ca[c]), len(cb[c]))
        maxd = 0.0
        first = None
        for i in range(n):
            try:
                va, vb = float(ca[c][i]), float(cb[c][i])
            except ValueError:
                continue
            dd = abs(va - vb)
            if dd > maxd:
                maxd = dd
            if dd > 0 and first is None:
                first = i
        print('   %-9s byte_identical=%-5s len_a=%d len_b=%d max_abs_diff_m=%.9g first_diff_row=%s'
              % (c, ident, len(ca[c]), len(cb[c]), maxd, first))
    da, _ = load(root, a)
    db, _ = load(root, b)
    same = {k: (da.get(k) == db.get(k)) for k in CUBE_FIELDS}
    print('   cube-side result scalars equal: %s' % json.dumps(same))
    all_identical = all_identical and all(same.values())
    print('   ALL block-side readings byte-identical = %s' % all_identical)
    print('   PRED_divergence_ok (must be True) = %s' % (not all_identical))
    if all_identical:
        print('   *** CONTROL INVALID (defect): the two arms did not diverge ***')


def main():
    root = sys.argv[1]
    if sys.argv[2] == '--divergence':
        divergence(root, sys.argv[3], sys.argv[4])
        return 0
    if sys.argv[2] == '--anchor-diff':
        with open(ANCHOR) as f:
            anc = json.load(f)
        mine, _ = load(root, sys.argv[3])
        keys = ['success', 'hold_min_lift_m', 'hold_slip_m', 'max_lift_m', 'duration_s',
                'gates', 'final_table_min_force_last100ms_N', 'max_drift_m',
                'final_pad_vertical_spread_m', 'right_arm_tracking_rms_rad']
        for k in keys:
            va, vb = anc.get(k, '<MISSING>'), mine.get(k, '<MISSING>')
            print('%-34s anchor=%s | a2=%s | equal=%s'
                  % (k, json.dumps(va)[:110], json.dumps(vb)[:110], va == vb))
        return 0
    for name in sys.argv[2:]:
        row(root, name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
