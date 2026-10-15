#!/usr/bin/env python3
"""W4h patch 6: preset-seat runtime check becomes a pad-gap FK check and the cube is placed
at the JSON cube_pos (allowing a designed offset from contact_frame; freeze_close makes the
CLOSE phase passive so the offset is safe). rep_ext_w1 only."""
from pathlib import Path
import hashlib
SG = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1/rep/sonic_grasp.py')
src = SG.read_text()
old = """   _w4h_cq=int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
   d.qpos[_w4h_cq:_w4h_cq+3]=_w4h_seat;d.qpos[_w4h_cq+3:_w4h_cq+7]=[1.,0.,0.,0.];mujoco.mj_forward(m,d)
   initial_cube=d.xpos[cube].copy() # W4h W1S: lift is measured from the preset seat, not the template seat
   _w4h_req=np.asarray([float(v) for v in W4H_PRESET['cube_pos']])
   _w4h_drift=float(np.linalg.norm(_w4h_seat-_w4h_req)*1e3)
   assert _w4h_drift<=.5,'W4h seat FK check failed: runtime %.3fmm vs JSON'%_w4h_drift
"""
new = """   _w4h_cq=int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
   _w4h_req=np.asarray([float(v) for v in W4H_PRESET['cube_pos']])
   _w4h_drift=float(np.linalg.norm(_w4h_seat-_w4h_req)*1e3)
   if W4H_PRESET.get('design_gaps_mm') is not None: # W4h W1S: designed seat offset from cf; FK check = pad-cube gaps
    d.qpos[_w4h_cq:_w4h_cq+3]=_w4h_req;d.qpos[_w4h_cq+3:_w4h_cq+7]=[1.,0.,0.,0.];mujoco.mj_forward(m,d)
    _w4h_gaps=[float(mujoco.mj_geomDistance(m,d,pads[i],cg,.05,None))*1e3 for i in range(3)]
    _w4h_dev=max(abs(_w4h_gaps[i]-float(W4H_PRESET['design_gaps_mm'][i])) for i in range(3))
    assert _w4h_dev<=.4,'W4h preset geometry FK check failed: pad-gap deviation %.3fmm'%_w4h_dev
    _w4h_fk=dict(mode='design pad-cube gaps',gaps_mm=_w4h_gaps,dev_mm=_w4h_dev,cf_seat_m=_w4h_seat.tolist(),cf_offset_mm=float(np.linalg.norm(_w4h_req-_w4h_seat)*1e3))
   else:
    d.qpos[_w4h_cq:_w4h_cq+3]=_w4h_seat;d.qpos[_w4h_cq+3:_w4h_cq+7]=[1.,0.,0.,0.];mujoco.mj_forward(m,d)
    assert _w4h_drift<=.5,'W4h seat FK check failed: runtime %.3fmm vs JSON'%_w4h_drift
    _w4h_fk=dict(mode='cf seat vs JSON',drift_mm=_w4h_drift)
   initial_cube=d.xpos[cube].copy() # W4h W1S: lift is measured from the preset seat, not the template seat
"""
assert src.count(old) == 1, 'anchor A'
src = src.replace(old, new)
old2 = "w4h_state=dict(path=str(W4H_PRESET.get('path')),cube_pos_seat_m=_w4h_seat.tolist(),cube_pos_json_m=_w4h_req.tolist(),fk_check_drift_mm=_w4h_drift,weld_equality="
new2 = "w4h_state=dict(path=str(W4H_PRESET.get('path')),cube_pos_seat_m=_w4h_seat.tolist(),cube_pos_json_m=_w4h_req.tolist(),fk_check=_w4h_fk,weld_equality="
assert src.count(old2) == 1, 'anchor B'
src = src.replace(old2, new2)
SG.write_text(src)
print('patch6 OK sha256=%s' % hashlib.sha256(src.encode()).hexdigest())
