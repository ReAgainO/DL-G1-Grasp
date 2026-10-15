#!/usr/bin/env python3
"""W4h W1S patch: apply the MARKED preset-seat variant to the rep_ext_w1 copy only.

Touches: rep_ext_w1/rep/sonic_grasp.py (9 anchors) + rep_ext_w1/run_fixE.sh (BASE + meta).
Every change is env-gated by W4H_PRESET_JSON except the run_fixE.sh BASE redirect (copy-only).
Prints the anchors applied or exits nonzero without writing on any mismatch.
"""
import hashlib, sys
from pathlib import Path

ROOT = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1')
SG = ROOT / 'rep/sonic_grasp.py'
SH = ROOT / 'run_fixE.sh'
src = SG.read_text()
n_applied = 0

def rep(old, new, tag, count=1):
    global src, n_applied
    c = src.count(old)
    assert c == count, 'ANCHOR[%s] count %d != %d' % (tag, c, count)
    src = src.replace(old, new)
    n_applied += 1
    print('anchor %-3s OK (x%d): %s' % (tag, count, old.strip().splitlines()[0][:72]))

# --- 1) env loader after ENV_L1_BODIES ---
rep(
"ENV_L1_BODIES={'right_hand_thumb_2_link','right_hand_index_1_link','right_hand_middle_1_link'}\n",
"ENV_L1_BODIES={'right_hand_thumb_2_link','right_hand_index_1_link','right_hand_middle_1_link'}\n"
"# W4h W1S variant (MARKED, env-gated): W1-style 'cube pre-seated in the palm' protocol.\n"
"# W4H_PRESET_JSON names a JSON with keys cube_pos [x,y,z] (world = the FK contact_frame seat\n"
"# of the injected closed-hand config at the live init pose), weld (temporary world-cube\n"
"# fixture), freeze_hand, skip_to_close. Absent => every path below is inert and the run is\n"
"# the untouched W4g envelope arm. Audit lands in result['w4h_preset_seat'] and the hold is\n"
"# carried by pads only (envelope-collision level 0).\n"
"def _w4h_preset():\n"
" _p=os.environ.get('W4H_PRESET_JSON','')\n"
" if not _p:return None\n"
" _c=json.loads(Path(_p).read_text());_c['path']=_p;return _c\n"
"W4H_PRESET=_w4h_preset()\n", 'A1')

# --- 2) cube seat override + weld fixture in scene_and_cal ---
rep(
" pos_text='%.10g %.10g %.10g'%(cube_x,cube_y,support_top+cube_half)\n"
" if cube_body.get('pos')!=pos_text:cube_body.set('pos',pos_text)\n",
" pos_text='%.10g %.10g %.10g'%(cube_x,cube_y,support_top+cube_half)\n"
" if W4H_PRESET is not None and W4H_PRESET.get('cube_pos') is not None:pos_text='%.10g %.10g %.10g'%tuple(float(v) for v in W4H_PRESET['cube_pos']) # W4h W1S (marked): preset palm seat overrides the support-top seat\n"
" if cube_body.get('pos')!=pos_text:cube_body.set('pos',pos_text)\n"
" if W4H_PRESET is not None and W4H_PRESET.get('weld',True): # W4h W1S (marked): temporary world-cube fixture (W1 protocol), released at LIFT entry\n"
"  equality=scene.find('equality')\n"
"  if equality is None:equality=ET.SubElement(scene.getroot(),'equality')\n"
"  ET.SubElement(equality,'weld',name='w4h_cube_fixture',body1='red_cube',solref='.002 1')\n"
"  print('W4H_PRESET_XML '+json.dumps(dict(cube_pos=[float(v) for v in W4H_PRESET['cube_pos']],weld=True,freeze_hand=bool(W4H_PRESET.get('freeze_hand',True)),skip_to_close=bool(W4H_PRESET.get('skip_to_close',True)))),flush=True)\n", 'A2')

# --- 3) neq assert ---
rep(
" assert m.nu==43 and m.nq==57 and m.neq==int(fixed_base) and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==2\n",
" assert m.nu==43 and m.nq==57 and m.neq==int(fixed_base)+(1 if W4H_PRESET is not None and W4H_PRESET.get('weld',True) else 0) and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==2 # W4h W1S: +1 temporary cube fixture\n", 'A3')

# --- 4) seat block in pinch init (before the geo/lR init) ---
rep(
"  else:grip_active=False\n"
"  geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)\n"
"  # These are physical pad-frame coordinates, no human calibration endpoints.\n"
"  lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()\n",
"  else:grip_active=False\n"
"  w4h_state=None\n"
"  if W4H_PRESET is not None: # W4h W1S (marked): seat the cube at contact_frame(cfg) of the LIVE init pose; verify against the JSON value\n"
"   assert grip_target is not None and grip_active,'W4h preset seat requires an injected grip target'\n"
"   assert not fixed_base,'W4h preset seat certified on the free base only'\n"
"   _w4h_weld=[int(i) for i in range(m.neq) if mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_EQUALITY,i)=='w4h_cube_fixture']\n"
"   assert len(_w4h_weld)==1,'W4h preset fixture missing at scene build'\n"
"   d.qpos[hq]=close_hand.copy();mujoco.mj_forward(m,d)\n"
"   geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)\n"
"   _w4h_seat=contact_frame(m,geo,d.xmat[cube].reshape(3,3),opponent=opponent).copy()\n"
"   _w4h_cq=int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])\n"
"   d.qpos[_w4h_cq:_w4h_cq+3]=_w4h_seat;d.qpos[_w4h_cq+3:_w4h_cq+7]=[1.,0.,0.,0.];mujoco.mj_forward(m,d)\n"
"   initial_cube=d.xpos[cube].copy() # W4h W1S: lift is measured from the preset seat, not the template seat\n"
"   _w4h_req=np.asarray([float(v) for v in W4H_PRESET['cube_pos']])\n"
"   _w4h_drift=float(np.linalg.norm(_w4h_seat-_w4h_req)*1e3)\n"
"   assert _w4h_drift<=.5,'W4h seat FK check failed: runtime %.3fmm vs JSON'%_w4h_drift\n"
"   w4h_state=dict(path=str(W4H_PRESET.get('path')),cube_pos_seat_m=_w4h_seat.tolist(),cube_pos_json_m=_w4h_req.tolist(),fk_check_drift_mm=_w4h_drift,weld_equality=_w4h_weld[0],freeze_hand=bool(W4H_PRESET.get('freeze_hand',True)),skip_to_close=bool(W4H_PRESET.get('skip_to_close',True)),released_at_s=None,weld_active_steps_lift_hold=0)\n"
"   print('W4H_PRESET_SEAT',json.dumps(w4h_state),flush=True)\n"
"  geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)\n"
"  # These are physical pad-frame coordinates, no human calibration endpoints.\n"
"  lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()\n", 'A4')

# --- 5) weld release at LIFT entry (inside change()) ---
rep(
"  if p=='LIFT':\n"
"   lift_wrist_origin=d.xpos[wrist].copy();lift_cube_origin=d.xpos[cube].copy();lift_wrist_R=d.xmat[wrist].reshape(3,3).copy()\n"
"   if lock_grip:hand_goal=hand_command.copy()\n",
"  if p=='LIFT':\n"
"   lift_wrist_origin=d.xpos[wrist].copy();lift_cube_origin=d.xpos[cube].copy();lift_wrist_R=d.xmat[wrist].reshape(3,3).copy()\n"
"   if lock_grip:hand_goal=hand_command.copy()\n"
"   if w4h_state is not None and w4h_state['released_at_s'] is None:d.eq_active[w4h_state['weld_equality']]=0;w4h_state['released_at_s']=float(t) # W4h W1S (marked): release the temporary fixture at LIFT entry\n", 'A5')

# --- 6) hand freeze override in all phases ---
rep(
"   elif phase=='RELEASE':hand=core.blend(release_hand,core.OPEN,e)\n"
"  kp,kd=core.gains()\n",
"   elif phase=='RELEASE':hand=core.blend(release_hand,core.OPEN,e)\n"
"  if w4h_state is not None and w4h_state['freeze_hand']:hand=close_hand.copy() # W4h W1S (marked): hand frozen at the injected envelope config in ALL phases\n"
"  kp,kd=core.gains()\n", 'A6')

# --- 7) SETTLE -> CLOSE jump ---
rep(
"  if phase=='SETTLE' and e>=2:change('APPROACH',d.time)\n",
"  if phase=='SETTLE' and e>=2:change('CLOSE' if (w4h_state is not None and w4h_state['skip_to_close']) else 'APPROACH',d.time) # W4h W1S (marked): jump straight to CLOSE\n", 'A7')

# --- 8) weld-active audit counter ---
rep(
"  contact_log.end()\n"
"  balance_log.step(d,phase)\n",
"  contact_log.end()\n"
"  if w4h_state is not None and phase in ['LIFT','HOLD']:w4h_state['weld_active_steps_lift_hold']+=int(d.eq_active[w4h_state['weld_equality']]) # W4h W1S audit: must stay 0\n"
"  balance_log.step(d,phase)\n", 'A8')

# --- 9) result record ---
rep(
" with gzip.open(out/'cycle-latency.csv.gz','wt') as f:\n",
" if w4h_state is not None: # W4h W1S (marked)\n"
"  w4h_state['definition']='W1-style pre-seated cube: cube body preset to the FK contact_frame seat of the injected envelope closed-hand config at the live init pose, temporary world-cube weld fixture, hand frozen (freeze_hand=false => open->close), SETTLE->CLOSE jump, fixture released at LIFT entry; hold carried by pads only (level-0 mask)'\n"
"  w4h_state['release_rule']='dedicated weld inactive for every LIFT/HOLD solver step (weld_active_steps_lift_hold==0)'\n"
"  result['w4h_preset_seat']=w4h_state\n"
" with gzip.open(out/'cycle-latency.csv.gz','wt') as f:\n", 'A9')

SG.write_text(src)
new_sha = hashlib.sha256(src.encode()).hexdigest()
print('sonic_grasp.py patched: anchors=%d new_sha256=%s' % (n_applied, new_sha))

# --- run_fixE.sh: BASE redirect + meta line ---
sh = SH.read_text()
assert sh.count('BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_env') == 1
sh = sh.replace('BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_env',
                'BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1')
old_meta = "  printf 'envelope_collision=%s grip_target_json=%s w4g_env_guards=%s finger_pd=%s\\n' \"${ENVELOPE_COLLISION:-<none>}\" \"${GRIP_TARGET_JSON:-<none>}\" \"${W4G_ENV_GUARDS:-1}\" \"${FINGER_PD:-<none>}\"\n"
assert sh.count(old_meta) == 1, 'meta anchor'
sh = sh.replace(old_meta, old_meta + "  printf 'w4h_preset_json=%s\\n' \"${W4H_PRESET_JSON:-<none>}\"\n")
SH.write_text(sh)
print('run_fixE.sh patched: BASE->rep_ext_w1 sha256=%s' % hashlib.sha256(sh.encode()).hexdigest())
