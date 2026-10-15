from pathlib import Path
import numpy as np,mujoco,json
from material_hand31 import MaterialHand22
from native_profile_reader30 import NativeProfile30
R=Path('/data/group4/20261008-202654-codex-182c4568/rep');O=R/'out/normal_trial31';z=np.load(O/'trajectory.npz');m=mujoco.MjModel.from_xml_path(str(O/'scene.xml'));d=mujoco.MjData(m);plan=json.loads((R/'out/surface_exec25_plan.json').read_text());solver=MaterialHand22(m,plan['grasp_plan']);d.qpos[:]=z['qpos'][0];mujoco.mj_forward(m,d);solver.set_table(d,.003);solver.preferred=np.array(plan['open_hand_q']);solver.lo+=.018;solver.hi-=.018
w=m.body('right_wrist_yaw_link').id;motion=NativeProfile30(R);p0=np.array([.28,-.118,.7745]);gp=np.array(plan['waypoints'][-1]['wrist_p']) if False else np.array(next(x for x in plan['waypoints'] if x['name']=='GRASP')['wrist_p']);gr=np.array(next(x for x in plan['waypoints'] if x['name']=='GRASP')['wrist_R']);offset=gr.T@(p0-gp)
def low(q):
 f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[solver.aq]=q;mujoco.mj_forward(m,f);a=[]
 for gg,vv in zip(solver.table_geoms,solver.table_vertices):
  world=vv@f.geom_xmat[gg].reshape(3,3).T+f.geom_xpos[gg];sel=world[:,0]>=solver.table_front-.002
  if sel.any():a.append((float(world[sel,2].min()-solver.table_top),m.geom(gg).name))
 return min(a)
for t in [64.,65.,66.2,66.4,67.,68.,69.]:
 i=int(round((t-.002)/.04));d.qpos[:]=z['qpos'][i];mujoco.mj_forward(m,d);cmd=z['hand_reference'][i];native=float(z['native_clock_s'][i]);_,wp,wr=motion.sample([native]);target=wp[0]+wr[0]@offset;rot=wr[0]@gr.T;solver.gap=.012;goal=solver.solve(d,target,rot,cmd)
 print(json.dumps({'t':t,'actual_low':low(d.qpos[solver.aq]),'cmd_low':low(cmd),'goal_low':low(goal),'slew_low':min(low(cmd+np.clip(goal-cmd,-h,h)) for h in [.001,.01,.03,.05,.1]),'hand_tracking_max':float(abs(cmd-d.qpos[solver.aq]).max()),'target_error':solver.last['max_pad_target_error_m']}))
