from pathlib import Path
import json,copy
r=Path.cwd();plan=json.load(open(r/'out/pose_plan_candidates12.json'))[0];path=json.load(open(r/'out/joint_waypoints12.json'));plan=copy.deepcopy(plan);plan['wrist_target'][0]-=.06;plan['grasp_center'][0]-=.06;plan['frame_adjustment']='robot initial base x=-.06, original cube x=.28; joint targets same relative reach as previous cube .34/base0'
path=copy.deepcopy(path)
for w in path['waypoints']:w['wrist_p'][0]-=.06
path['grasp_plan']=plan;path['frame_adjustment']=plan['frame_adjustment'];(r/'out/pose_plan_candidates16.json').write_text(json.dumps([plan],indent=2));(r/'out/joint_waypoints16.json').write_text(json.dumps(path,indent=2));print('Prepared original cube .28 with base shift -.06; no episode state changed.')
