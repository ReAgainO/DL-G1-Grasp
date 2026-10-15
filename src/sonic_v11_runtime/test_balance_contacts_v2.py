"""Exercise actual robot/table raw logging; all calls are zero-step mj_forward."""
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from balance_audit import BalanceAudit

root=Path(__file__).resolve().parent
out=root/'out/balance-contact-tests-v2'
out.mkdir()
xml='<mujoco><worldbody><geom name="floor" type="plane" size="1 1 .1"/><geom name="table_top" type="box" pos="1 0 .1" size=".2 .2 .1"/><body name="pelvis" pos="1 0 .099"><freejoint/><geom name="torso" size=".01" pos="0 0 .1"/><body name="left_ankle_roll_link" pos="0 .04 0"><geom name="left_foot" type="box" size=".02 .02 .02"/></body><body name="right_ankle_roll_link" pos="0 -.04 0"><geom name="right_foot" type="box" size=".02 .02 .02"/></body></body></worldbody></mujoco>'
(out/'scene.xml').write_text(xml)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=mujoco.MjModel.from_xml_string(xml)
d=mujoco.MjData(m)
mujoco.mj_forward(m,d)
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,dt=float(m.opt.timestep),model_sha={'scene':sha(out/'scene.xml')},scene_generator_sha=sha(__file__),library_sha={'balance_audit':sha(root/'balance_audit.py')})
audit=BalanceAudit(m,{m.geom('floor').id,m.geom('table_top').id},stamp,out)
before=[d.qpos.copy(),d.qvel.copy(),d.qacc.copy(),d.ctrl.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy()]
audit.step(d,'HOLD')
r=audit.finish(-.1,.1)
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
check('actual_robot_table_contacts_present',d.ncon>0 and len(audit.contacts)>0)
check('torso_table_pair_named_in_raw_log',any(row[8]=='pelvis' and row[5]=='torso' and row[7]=='table_top' for row in audit.contacts))
check('positive_table_force_branch',audit.rows[0][2]>0)
check('table_rest_rejected',not r['no_table_rest_in_hold'])
check('contact_phase_and_category_recorded',all(row[2]=='HOLD' and row[9]==0 for row in audit.contacts))
check('full_contact_wrench_six_components',all(len(row)==17 for row in audit.contacts))
check('observer_no_state_or_force_mutation',all(np.array_equal(a,b) for a,b in zip(before,[d.qpos,d.qvel,d.qacc,d.ctrl,d.qfrc_applied,d.xfrc_applied])))
check('raw_CSV_written',(out/'robot_support_contacts.csv.gz').stat().st_size>200)
check('contact_budget_is_explicit',r['raw_robot_support_contact_limit']==1440000)
(out/'result.json').write_text(json.dumps(dict(runtime_stamp=stamp,physical_steps=0,passed=True,checks=checks,raw_contacts=len(audit.contacts),table_force_N=float(audit.rows[0][2])),indent=2)+'\n')
print(json.dumps(dict(physical_steps=0,passed=True,checks=checks,raw_contacts=len(audit.contacts),table_force_N=float(audit.rows[0][2])),indent=2))
