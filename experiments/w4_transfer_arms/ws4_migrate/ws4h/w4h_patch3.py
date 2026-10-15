#!/usr/bin/env python3
"""W4h W1S patch 3 (rep_ext_w1 only): preset fields settle_s (default 2.) and
weld_release ('LIFT' default | 'CLOSE'). Absent => inert."""
from pathlib import Path
import hashlib
SG = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1/rep/sonic_grasp.py')
src = SG.read_text()

# 1) w4h_state gains settle_s + weld_release
old = "released_at_s=None,weld_active_steps_lift_hold=0)\n   print('W4H_PRESET_SEAT'"
assert src.count(old) == 1, 'anchor state'
src = src.replace(old, "released_at_s=None,weld_active_steps_lift_hold=0,settle_s=float(W4H_PRESET.get('settle_s',2.)),weld_release=str(W4H_PRESET.get('weld_release','LIFT')).upper())\n   print('W4H_PRESET_SEAT'")

# 2) CLOSE-entry release option inside change()
old = ("  if p=='CLOSE':\n"
       "   close_reference=reference[arm].copy();hand_command=d.qpos[hq].copy();hand_goal=close_hand.copy()\n"
       "   closure_normal=geo.geom_xpos[pads[opponent]]-geo.geom_xpos[pads[0]]\n")
assert src.count(old) == 1, 'anchor close'
src = src.replace(old, old +
  "   if w4h_state is not None and w4h_state['weld_release']=='CLOSE' and w4h_state['released_at_s'] is None:d.eq_active[w4h_state['weld_equality']]=0;w4h_state['released_at_s']=float(t) # W4h W1S (marked): optional early fixture release at CLOSE entry\n")

# 3) SETTLE duration knob
old = "  if phase=='SETTLE' and e>=2:change('CLOSE' if (w4h_state is not None and w4h_state['skip_to_close']) else 'APPROACH',d.time) # W4h W1S (marked): jump straight to CLOSE\n"
assert src.count(old) == 1, 'anchor settle'
src = src.replace(old,
  "  if phase=='SETTLE' and e>=(w4h_state['settle_s'] if w4h_state is not None else 2):change('CLOSE' if (w4h_state is not None and w4h_state['skip_to_close']) else 'APPROACH',d.time) # W4h W1S (marked): jump straight to CLOSE; preset may shorten SETTLE\n")

SG.write_text(src)
print('patch3 OK sha256=%s' % hashlib.sha256(src.encode()).hexdigest())
