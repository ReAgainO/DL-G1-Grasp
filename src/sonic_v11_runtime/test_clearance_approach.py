import numpy as np
from clearance_approach import ClearanceApproach
planner=ClearanceApproach([.18,-.12,.7],np.eye(3),.757)
origin=np.array([.18,-.12,.7]);pad=np.array([.25,-.12,.94]);final=np.array([.267,-.118,.8745])
start=planner.update(0.,.7,pad,final)
assert np.array_equal(start['wrist_target'],origin) and not start['clearance_passed']
waiting=planner.update(5.,.899,pad,final)
assert waiting['wrist_target'][2]>.9 and not waiting['clearance_passed']
passed=planner.update(6.,.901,pad,final)
assert passed['wrist_target'] is None and np.array_equal(passed['pad_target'],pad)
end=planner.update(12.,.901,pad,final)
assert np.allclose(end['pad_target'],final)
assert np.array_equal(planner.rotation,np.eye(3))
late=ClearanceApproach([.18,-.12,.7],np.eye(3),.757)
assert not late.update(18.,.899,pad,final)['clearance_passed']
assert late.update(19.,.901,pad,final)['clearance_passed']
assert np.allclose(late.update(25.,.901,pad,final)['pad_target'],final)
try:planner.update(27.,.901,pad,final)
except ValueError:pass
else:raise AssertionError('clock bound not enforced')
print('PASS9: initial full-pose target, actual-height negative branch, qualified transition, endpoint, frozen orientation, late negative/positive/endpoint branches, clock rejection; physical_steps=0')
