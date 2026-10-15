"""Independent contract checks, including measurable reference consumption."""
import json,time
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
ROOT=Path(__file__).resolve().parent
m=mujoco.MjModel.from_xml_path(str(ROOT/'src/g1/scene_grasp_hand.xml'))
d=mujoco.MjData(m);d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0]
q=np.tile(s.DEFAULT_ANGLES,(10,1));v=np.zeros_like(q);r=np.tile([1.,0.,0.,0.],(10,1))
passed=[]
def check(name,condition):
 assert bool(condition),name
 passed.append(name)
def reject(name,fn):
 try:fn()
 except (ValueError,AssertionError):passed.append(name)
 else:raise AssertionError('Expected rejection '+name)
controllers=[s.SonicV11(m) for _ in range(3)]
for c in controllers:d.qpos[c.aq]=s.DEFAULT_ANGLES
mujoco.mj_forward(m,d)
a=controllers[0].step_policy(d,q,v,r)
b=controllers[1].step_policy(d,q,v,r)
changed=q.copy();changed[:,22]+=.1
c=controllers[2].step_policy(d,changed,v,r)
check('cpu_cold_start_repeat_bitwise',np.array_equal(a,b))
check('encoder_shape1751_decoder994',controllers[0].last_encoder.shape==(1,1751) and controllers[0].last_decoder.shape==(1,994))
check('encoder_mode_id0_not_onehot',np.array_equal(controllers[0].last_encoder[0,:4],np.zeros(4)))
check('known_position_offset_isaac_order',np.array_equal(controllers[0].last_encoder[0,4:294].reshape(10,29),q[:,s.I2M].astype(np.float32)))
check('unused_mode_slots_zero',np.max(abs(controllers[0].last_encoder[0,644:]))==0)
check('root_6d_row_major_identity',np.array_equal(controllers[0].last_encoder[0,584:644].reshape(10,6),np.tile([1,0,0,1,0,0],(10,1))))
check('reference_changes_encoder',np.max(abs(controllers[2].last_encoder-controllers[0].last_encoder))>.09)
check('reference_changes_token',np.max(abs(controllers[2].last_token-controllers[0].last_token))>1e-6)
check('reference_changes_physical_action',np.max(abs(c-a))>1e-6)
reject('wrong_future_shape',lambda:controllers[0].step_policy(d,q[:9],v,r))
bad=q.copy();bad[0,0]=np.nan
reject('nan_reference',lambda:controllers[0].step_policy(d,bad,v,r))
reject('nonunit_quaternion',lambda:controllers[0].step_policy(d,q,v,r*2))
reject('unknown_slot',lambda:s.pack({'x':np.zeros(1)},['x'],s.ENC_WIDTHS))
badparts={n:np.zeros(w) for n,w in s.ENC_WIDTHS.items()};badparts['encoder_mode_4']=np.zeros(3)
reject('per_slot_width_drift',lambda:s.pack(badparts,list(s.ENC_WIDTHS),s.ENC_WIDTHS))
# Heading-normalization invariance: rotate robot/ref together by same yaw.
d.qpos[3:7]=[np.cos(.2),0,0,np.sin(.2)];r2=np.tile(d.qpos[3:7],(10,1))
controllers[1].step_policy(d,q,v,r2)
check('heading_only_common_yaw_invariance',np.max(abs(controllers[1].last_encoder-controllers[0].last_encoder))<1e-6)
result=dict(passed=passed,count=len(passed),action_reference_effect_max=float(np.max(abs(c-a))),
            token_reference_effect_max=float(np.max(abs(controllers[2].last_token-controllers[0].last_token))),
            backend=controllers[0].audit(),test_sha=s.sha(__file__))
(ROOT/'out/sonic-contract-tests.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
