#!/usr/bin/env python3
"""W4b: two-run comparison (bitwise arrays + result fields + gates). Usage: traj_cmp.py DIR_A DIR_B"""
import json,sys
import numpy as np
A,B=sys.argv[1],sys.argv[2]
sa=np.load(A+'/trajectory.npz',allow_pickle=True);sb=np.load(B+'/trajectory.npz',allow_pickle=True)
for k in ['qpos','qvel','body_reference','hand_reference','wrist_target','decoded_motor_target','raw_decoded_motor_target','applied_motor_target','actuator_ctrl','phase','time','fps']:
 x,y=sa[k],sb[k]
 if x.shape!=y.shape:print('%-28s SHAPE %s vs %s'%(k,x.shape,y.shape));continue
 if x.dtype.kind=='f':
  eq=bool(np.array_equal(x,y,equal_nan=True));d=float(np.nanmax(np.abs(x-y.astype(float)))) if x.size else 0.
 else:
  eq=bool(np.array_equal(x,y));d=0.
 print('%-28s %-12s bitwise_equal=%-5s max_abs_diff=%.3e'%(k,str(tuple(x.shape)),eq,d))
ra=json.loads(open(A+'/result.json').read());rb=json.loads(open(B+'/result.json').read())
print('--- result fields')
for k in ['success','fail_reason','hold_min_lift_m','hold_slip_m','max_lift_m','duration_s']:
 va,vb=ra.get(k),rb.get(k)
 print('%-22s A=%s B=%s %s'%(k,va,vb,'SAME' if va==vb else 'DIFF'))
print('gates_A_false=',sorted(k for k,v in ra['gates'].items() if not v))
print('gates_B_false=',sorted(k for k,v in rb['gates'].items() if not v))
print('adaptive_calls A=%s B=%s'%((ra.get('adaptive_hand') or {}).get('calls'),(rb.get('adaptive_hand') or {}).get('calls')))
for tag,r in (('A',ra),('B',rb)):
 g=r.get('grip_target_json') or {}
 print('grip_target_json[%s]: applied=%s bypassed=%s identity_noop=%s rad=%s'%(tag,g.get('applied'),g.get('adaptive_ik_bypassed'),g.get('identity_noop'),g.get('rad')))
