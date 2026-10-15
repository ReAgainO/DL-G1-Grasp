#!/usr/bin/env python3
"""Patch ws4i_lid.py -> ws4i_clamp.py: criterion becomes a VERTICAL CROSS-CLAMP
(>=1 pad pressing down on the top face AND >=1 pad pressing up on the bottom face,
the CoM close to the clamp axis so the couple does not tip the cube) instead of the
W4h lid (>=2 top pads). Rationale: a lid can only carry by friction; a cross-clamp
carries the weight on the lower pad's normal force. Measured d60i_00 (clamp family,
60mm) reached full phases with only 1.5mm lift, so the axis/CoM term is added here.
"""
from pathlib import Path
p = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ws4i/ws4i_clamp.py')
s = p.read_text()
old = """        lid = [pc for pc in r['pad_contacts'] if pc['n'][2] <= -0.35]
        nl = len(lid)
        if nl < 2: c += 5000. * (2 - nl)
        else: c -= 1000. * min(nl, 3)
        if len(lid) >= 2:
            pts = np.array([pc['pos'][:2] for pc in lid])
            mm = hull_margin(pts, r['cpos'][:2]) * 1e3
            c += 300. * max(0., 5. - mm) ** 2
"""
new = """        sup = [pc for pc in r['pad_contacts'] if pc['n'][2] >= 0.35]
        lid = [pc for pc in r['pad_contacts'] if pc['n'][2] <= -0.35]
        miss = (0 if sup else 1) + (0 if lid else 1)
        if miss: c += 5000. * miss
        else:
            c -= 1500.
            off = np.array(sup[0]['pos'][:2]) - r['cpos'][:2]
            ax = np.array(lid[0]['pos'][:2]) - np.array(sup[0]['pos'][:2])
            L = np.linalg.norm(ax)
            perp = abs(float(ax[0] * off[1] - ax[1] * off[0])) / (L + 1e-9)
            c += 200. * max(0., perp * 1e3 - 8.) ** 2
"""
assert s.count(old) == 1, 'clamp anchor count=%d' % s.count(old)
s = s.replace(old, new)
s = s.replace("W4i lid edge=%gmm (W4h top-press family, corrected normal, settle_s=0.05)", "W4i clamp edge=%gmm (vertical cross-clamp: top press + bottom support, CoM near axis, settle_s=0.05)")
s = s.replace("('preset_w1s_%g_lid.json' % EDGE)", "('preset_w1s_%g_clamp.json' % EDGE)")
s = s.replace("('grip_w1s_%g_lid.json' % EDGE)", "('grip_w1s_%g_clamp.json' % EDGE)")
s = s.replace("('audit_lid_%g.json' % EDGE)", "('audit_clamp_%g.json' % EDGE)")
s = s.replace("log('WROTE preset/grip/audit (lid) for edge=%g' % EDGE)", "log('WROTE preset/grip/audit (clamp) for edge=%g' % EDGE)")
s = s.replace('"""W4i lid: the W4h-validated', '"""W4i clamp (patched from lid): the W4h-validated')
p.write_text(s)
print('CLAMP PATCH OK bytes=%d' % len(s.encode()))
