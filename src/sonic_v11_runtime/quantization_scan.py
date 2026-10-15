"""Zero-step frozen-observation perturbation scan on original ARDY frames."""
import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from motion_input import ArdyMotion
root=Path(__file__).resolve().parent;out=root/'out/quantization-scan.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
motion=ArdyMotion(root/'src/original_motions/near_s42.npz',check_csv=root/'src/original_motions/near_s42.csv')
records=[];values=[]
for frame in [0,31,60,99]:
 d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=motion.qpos[frame,7:];mujoco.mj_forward(m,d)
 q=np.tile(motion.qpos[frame,7:],(10,1));c.step_policy(d,q,np.zeros_like(q),np.tile([1.,0,0,0],(10,1)))
 baseline=c.last_token.copy();values.extend(baseline.tolist())
 for eps in [.001,.005,.01,.03,.06,.12]:
  token_counts=[];motor_delta=[]
  for j in range(7):
   enc=c.last_encoder.copy();idx=4+np.arange(10)*29+s.M2I[22+j];enc[0,idx]+=eps
   token=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);values.extend(token.tolist())
   dec=c.last_decoder.copy();dec[0,:64]=token;action=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1)
   token_counts.append(int(np.count_nonzero(token!=baseline)))
   motor_delta.append(float(np.max(abs((action-c.last_action)[s.M2I[22:29]]*s.ACTION_SCALE[22:29]))))
  records.append(dict(frame=frame,eps_rad=eps,unchanged_token_probes=int(np.sum(np.array(token_counts)==0)),changed_components=token_counts,max_motor_delta_rad=motor_delta))
unique=np.unique(values);grid=np.abs(unique*4-np.round(unique*4)).max()
r=dict(physical_steps=0,source=motion.audit,models=c.model_stamp,all_observed_token_values=unique.tolist(),quarter_grid_max_residual=float(grid),records=records)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['source','records']},indent=2));print(json.dumps(records,indent=2))
