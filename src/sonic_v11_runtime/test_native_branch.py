"""Positive and negative candidate validation; no model loading or mj_step."""
import copy
import numpy as np
from native_branch import validate_candidates

base=dict(body_q=[0.]*7,capture_error_m=.0005,pad_spread_m=.001,
    minimum_arm_limit_margin_rad=.05,open_robot_table_clearance_m=.015,
    finger_replan_error_m=.0004,native_pose_deviation_rad=1.)
passed=0
chosen=validate_candidates([copy.deepcopy(base)])
assert chosen['static_feasible'];passed+=1
for key,value in [('capture_error_m',.0011),('pad_spread_m',.0021),
    ('minimum_arm_limit_margin_rad',.019),('open_robot_table_clearance_m',.009),
    ('finger_replan_error_m',.0016),('native_pose_deviation_rad',np.nan),('body_q',[0.]*6)]:
    bad=copy.deepcopy(base);bad[key]=value
    try:validate_candidates([bad])
    except ValueError:passed+=1
    else:raise AssertionError(key+' negative branch accepted')
for values in [[],[copy.deepcopy(base) for _ in range(8)]]:
    try:validate_candidates(values)
    except ValueError:passed+=1
    else:raise AssertionError('count bound')
other=copy.deepcopy(base);other['finger_replan_error_m']=.0003;other['native_pose_deviation_rad']=2.
assert validate_candidates([copy.deepcopy(base),other]) is other;passed+=1
tie=copy.deepcopy(other);tie['native_pose_deviation_rad']=.5
assert validate_candidates([other,tie]) is tie;passed+=1
print(f'PASS{passed}: static branch filters, finite/schema/count negative controls, selection/tie branches; physical_steps=0')
