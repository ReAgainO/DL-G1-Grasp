#!/usr/bin/env python3
"""W4c metrics: contact-loss / penetration proxies for one cell directory.
Read-only over out/<cell>/{result.json,trajectory.npz,telemetry.csv.gz,cube_contacts.csv.gz}.

Calibers (also documented in W4c_PHYS.md):
  frame            = one 500 Hz control tick (one telemetry row / one contact_log.begin-end block)
  LOADED pad       = pad-cube normal force > 0.01 N (identical to the run's own gate rule) ; 0.1 N also reported
  pad_pen          = -min(contact.dist) over pad-category contact rows (contact.dist<0 means penetration)
  support_pen      = -min(contact.dist) over support-category rows (table/pedestal/floor)
  loss event       = maximal run of >=25 consecutive frames (50 ms) with <2 loaded pads, counted after the
                     first >=25-frame two-pad stretch; "in air" = cube_z > initial_z + 20 mm in that frame
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

CAT = ('pad', 'wrist', 'other_robot', 'support', 'other')

def load_telemetry(p):
    with gzip.open(p, 'rt') as f:
        f.readline()
        cols = f.readline().lstrip('# ').strip().split(',')
        arr = np.loadtxt(f, delimiter=',')
    return {c: arr[:, i] for i, c in enumerate(cols)}, cols

def load_contacts(p):
    with gzip.open(p, 'rt') as f:
        cols = None
        for line in f:
            stripped = line.lstrip('# ').strip()
            if stripped.startswith('time_s,'):  # the stamp line also contains the substring 'time_s'
                cols = stripped.split(',')
                break
            if not line.startswith('#'):
                break
        idx = {k: cols.index(k) for k in ('time_s', 'step', 'category', 'distance_m', 'contact_fn_N')}
        arr = np.loadtxt(f, delimiter=',', usecols=tuple(idx.values()))
    return {k: arr[:, i] for i, k in enumerate(idx)}, cols

def runs(mask):
    """return list of (start, length) of True runs"""
    out = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out

def summarize(cell):
    d = Path(cell)
    r = json.loads((d / 'result.json').read_text())
    tel, tcols = load_telemetry(d / 'telemetry.csv.gz')
    con, ccols = load_contacts(d / 'cube_contacts.csv.gz')
    z0 = r['cube_geometry_entry']['initial_body_xyz_m'][2]
    f = np.vstack([tel['thumb_force_N'], tel['index_force_N'], tel['middle_force_N']]).T
    loaded01 = (f > .01).sum(axis=1)
    loaded10 = (f > .10).sum(axis=1)
    two01 = runs(loaded01 >= 2)
    two10 = runs(loaded10 >= 2)
    # hold window from the 25 Hz phase record
    # our own freshly written npz (numeric + unicode arrays only, no pickle needed)
    tp = np.load(d / 'trajectory.npz', allow_pickle=False)
    ph = [str(x) for x in tp['phase']]
    tt = tp['time']
    hold_idx = [i for i, p in enumerate(ph) if p == 'HOLD']
    hold_win = (float(tt[hold_idx[0]]), float(tt[hold_idx[-1]])) if hold_idx else None
    in_hold = np.zeros(len(tel['time_s']), bool)
    if hold_win:
        in_hold = (tel['time_s'] >= hold_win[0]) & (tel['time_s'] <= hold_win[1])
    # after the first sustained two-pad stretch, count loss events
    first = next((s for s, L in two01 if L >= 25), None)
    loss = []
    if first is not None:
        m = np.zeros(len(tel['time_s']), bool)
        m[first:] = (loaded01[first:] < 2)
        for s, L in runs(m):
            if L >= 25:
                loss.append((s, L))
    # penetration
    pad = con['category'] == 0
    sup = con['category'] == 3
    pen_pad = -float(con['distance_m'][pad].min()) if pad.any() else None
    pen_sup = -float(con['distance_m'][sup].min()) if sup.any() else None
    def worst_where(mask):
        if not mask.any():
            return None
        i = int(np.argmin(con['distance_m'][mask]))
        return dict(t_s=round(float(con['time_s'][mask][i]), 3),
                    dist_mm=round(float(con['distance_m'][mask][i]) * 1000, 3),
                    fn_N=round(float(con['contact_fn_N'][mask][i]), 4))
    # per-frame pad min distance -> frames with penetration > 0.5 mm
    fr_pad_pen = None
    if pad.any():
        steps = con['step'][pad]
        dist = con['distance_m'][pad]
        order = np.argsort(steps, kind='stable')
        steps, dist = steps[order], dist[order]
        uniq, start = np.unique(steps, return_index=True)
        mn = np.minimum.reduceat(dist, start)
        fr_pad_pen = dict(frames=len(uniq), worst_mm=-float(mn.min()) * 1000,
                          frames_gt_0p5mm=int((mn < -0.0005).sum()),
                          frames_gt_0p2mm=int((mn < -0.0002).sum()))
    z = tel['cube_z_m']
    lifted = z > z0 + .02
    in_air_no_pad = int((lifted & (loaded01 == 0)).sum())
    # contact quality inside HOLD: the 2nd-largest pad normal force per frame
    f_sorted = np.sort(f, axis=1)
    second = f_sorted[:, -2]
    hold_second_min = float(second[in_hold].min()) if in_hold.any() else None
    hold_note = dict(
        second_pad_min_N=round(hold_second_min, 4) if hold_second_min is not None else None,
        frames_second_below_0p1N=int((in_hold & (second < .1)).sum()),
        frames_second_below_1N=int((in_hold & (second < 1.)).sum()),
        sum_pad_min_N=round(float(f[in_hold].sum(axis=1).min()), 4) if in_hold.any() else None,
        min_pad_min_N=round(float(f[in_hold].min()), 4) if in_hold.any() else None)
    return dict(
        cell=d.name, arm=('phys' if r.get('physics_recipe_w4c') is not None else 'base'),
        success=bool(r['success']), fail=r.get('fail_reason') or '',
        red=[k for k, v in r['gates'].items() if not v], red_n=sum(1 for v in r['gates'].values() if not v),
        lift_mm=round((r.get('hold_min_lift_m') or -1) * 1000, 1),
        max_lift_mm=round((r.get('max_lift_m') or 0) * 1000, 1),
        slip_mm=round((r.get('hold_slip_m') or -1) * 1000, 2),
        duration_s=round(float(r.get('duration_s') or 0), 2),
        phys_recipe=r.get('physics_recipe_w4c', {}).get('applied') or r.get('physics_recipe_w4c'),
        frames=len(tel['time_s']),
        two_pad_frames_0p01N=int((loaded01 >= 2).sum()),
        two_pad_frames_0p1N=int((loaded10 >= 2).sum()),
        two_pad_run_max_0p01N=int(max([L for _, L in two01], default=0)),
        two_pad_run_max_0p1N=int(max([L for _, L in two10], default=0)),
        first_two_pad_s=float(tel['time_s'][two01[0][0]]) if two01 else None,
        last_two_pad_s=float(tel['time_s'][two01[-1][0] + two01[-1][1] - 1]) if two01 else None,
        loss_events=len(loss), loss_frames=sum(L for _, L in loss),
        loss_events_in_hold=sum(1 for s, L in loss if in_hold[s]),
        loss_first_s=float(tel['time_s'][loss[0][0]]) if loss else None,
        air_no_pad_frames=in_air_no_pad,
        hold_window_s=hold_win,
        two_pad_frames_in_hold=int((in_hold & (loaded01 >= 2)).sum()),
        two_pad_frames_in_hold_0p1N=int((in_hold & (loaded10 >= 2)).sum()),
        hold_contact_quality=hold_note,
        hold_frames=int(in_hold.sum()),
        pad_pen_worst_mm=round(pen_pad * 1000, 3) if pen_pad is not None else None,
        support_pen_worst_mm=round(pen_sup * 1000, 3) if pen_sup is not None else None,
        pad_pen_worst_at=worst_where(pad),
        support_pen_worst_at=worst_where(sup),
        pad_pen_frame_stats=({k: (round(v, 3) if isinstance(v, float) else v) for k, v in fr_pad_pen.items()}
                             if fr_pad_pen else None),
        contact_rows=int(len(con['time_s'])),
        cube_z_final_mm=round(float(z[-1] - z0) * 1000, 1),
    )

if __name__ == '__main__':
    out = {}
    for cell in sys.argv[1:]:
        try:
            out[Path(cell).name] = summarize(cell)
        except Exception as e:  # keep the sweep going, report the failure
            out[Path(cell).name] = dict(error=f'{type(e).__name__}: {e}')
    print(json.dumps(out, indent=1, default=str))
