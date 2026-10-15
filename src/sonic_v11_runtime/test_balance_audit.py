import hashlib,json,sys
from pathlib import Path
import numpy as np,mujoco
from balance_audit import BalanceAudit
root=Path(__file__).resolve().parent;out=root/'out/balance-audit-tests';out.mkdir()
xml='<mujoco><worldbody><geom name="floor" type="plane" size="1 1 .1"/><geom name="table_top" type="box" pos="1 0 .1" size=".2 .2 .1"/><body name="pelvis" pos="0 0 .019"><freejoint/><geom name="torso" size=".01" pos="0 0 .1"/><body name="left_ankle_roll_link" pos="0 .04 0"><geom name="left_foot" type="box" size=".02 .02 .02"/></body><body name="right_ankle_roll_link" pos="0 -.04 0"><geom name="right_foot" type="box" size=".02 .02 .02"/></body></body></worldbody></mujoco>'
(out/'scene.xml').write_text(xml);sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);mujoco.mj_forward(m,d)
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,dt=float(m.opt.timestep),model_sha={'scene':sha(out/'scene.xml')},scene_generator_sha=sha(__file__),library_sha={'balance_audit':sha(root/'balance_audit.py')})
a=BalanceAudit(m,{m.geom('floor').id,m.geom('table_top').id},stamp,out)
checks=[]
def check(label,condition):assert condition,label;checks.append(label)
check('left_foot_floor_classification',a.category(m.geom('left_foot').id,m.geom('floor').id)==1)
check('right_foot_swapped_order',a.category(m.geom('floor').id,m.geom('right_foot').id)==2)
check('torso_table_support_detected',a.category(m.geom('torso').id,m.geom('table_top').id)==0)
check('nonfoot_floor_detected',a.category(m.geom('floor').id,m.geom('torso').id)==3)
check('robot_self_contact_excluded',a.category(m.geom('torso').id,m.geom('left_foot').id) is None)
check('physical_floor_contact_branch_present',d.ncon>0)
before=[d.qpos.copy(),d.qvel.copy(),d.qacc.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy()]
a.step(d);r=a.finish(-.1,.1)
check('both_actual_foot_forces_recorded',a.rows[0][3]>0 and a.rows[0][4]>0)
check('no_state_writes',all(np.array_equal(x,y) for x,y in zip(before,[d.qpos,d.qvel,d.qacc,d.qfrc_applied,d.xfrc_applied])))
check('unloaded_table_not_reported_as_support',r['no_table_rest_in_hold'])
(out/'result.json').write_text(json.dumps(dict(runtime_stamp=stamp,physical_steps=0,passed=True,checks=checks),indent=2)+'\n');print(json.dumps(dict(physical_steps=0,passed=True,checks=checks),indent=2))
