import numpy as np,mujoco,json
from pathlib import Path
import sonic_v11 as s
from next_pose_policy import NextPolicyReference
from reference_filter import ReferenceFilter
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial05/scene.xml'));d=mujoco.MjData(m);a=np.load(r/'out/normal_trial05/trajectory.npz');d.qpos[:]=a['qpos'][-1];c=s.SonicV11(m);ref=a['body_reference'][-1];q=np.tile(ref,(10,1));v=np.zeros_like(q);rr=np.tile([1.,0,0,0],(10,1))
for _ in range(12):c.step_policy(d,q,v,rr)
d.qvel[c.av[22:29]]=np.linspace(-.2,.2,7);d.qpos[c.aq[22:29]]+=.001
lo=m.jnt_range[c.jids[22:29],0]+.006;hi=m.jnt_range[c.jids[22:29],1]-.006;rf=ReferenceFilter(ref[22:29],lo,hi,True);p=NextPolicyReference(c);p.ref_filter=rf;goal=np.clip(ref[22:29]+.02,lo,hi)
before_target=c.target.copy();before_action=c.last_action.copy();before_hist={k:np.array(vv).copy() for k,vv in c.hist.items()};p.predict(d,goal);expected=p.predicted_action.copy();enc=p.predicted_encoder.copy();dec=p.predicted_decoder.copy()
assert np.array_equal(c.target,before_target) and np.array_equal(c.last_action,before_action) and all(np.array_equal(np.array(c.hist[k]),vv) for k,vv in before_hist.items())
fq,fv=rf.step(goal);q[:,22:29]=fq;v[:,22:29]=fv;c.step_policy(d,q,v,rr)
res={'raw_action_max_error':float(abs(c.last_action-expected).max()),'encoder_max_error':float(abs(c.last_encoder-enc).max()),'decoder_max_error':float(abs(c.last_decoder-dec).max()),'policy_history_preserved_by_predict':True};print(json.dumps(res));assert res['raw_action_max_error']<1e-6
(r/'out/next_policy_contract07.json').write_text(json.dumps(res,indent=2))