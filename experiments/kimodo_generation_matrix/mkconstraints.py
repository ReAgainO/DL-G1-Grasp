#!/usr/bin/env python3
"""x04_mkconstraints.py -- build a NATIVE KIMODO constraints.json that shifts the pelvis so
the pinned-frame right-palm lands on the protocol's MuJoCo cube target (0.267, -0.118, 0.7745).

Method (mirrors work/kimodo_grasp/make_constraints.py but skips the fk_trace dependency):
  1. load the free-motion npz (produced by arm U)
  2. build the skeleton and FK the pinned frame's local_rot_mats with the library
  3. read off the KIMODO-coords of the right-palm site at that frame
  4. convert the MuJoCo cube target into KIMODO coords via MUJOCO_TO_KIMODO = [[0,1,0],[0,0,1],[1,0,0]]
     (source: repos/kimodo/kimodo/viz/g1_rig.py:18/21, exports/mujoco.py:80)
  5. shift d = kimodo_cube_target - kimodo_palm_at_frame
  6. write constraints.json with:
       frame_indices=[pin]
       local_joints_rot = axis_angle(local_rot_mats[pin]) (34,3)
       root_positions   = free root_positions[pin] + d   (3,)
       smooth_root_2d   = free smooth_root_pos[[pin], :2] + d[:2]   (1,2)

Also writes meta.json (KIMODO demo-folder format) alongside so --input_folder can replay.
"""
import argparse, json, os, sys

B = "/home/group4/group4_dasc7606c"
T = "20261006-045000-qoder-x04kimodo"
D = "/data/group4/" + T

ap = argparse.ArgumentParser()
ap.add_argument("--npz", required=True, help="free-motion npz from arm U cell")
ap.add_argument("--out", required=True, help="output constraints.json path")
ap.add_argument("--frame", type=int, default=40, help="pinned frame index")
ap.add_argument("--target-mujoco", default="0.267,-0.118,0.7745",
                help="cube target in MuJoCo world coords, comma-separated")
ap.add_argument("--palm-joint", default=None,
                help="name of the palm joint in the kimodo skeleton (auto-detect if unset)")
a = ap.parse_args()

os.environ["MUSA_VISIBLE_DEVICES"] = "-1"
os.environ["CHECKPOINT_DIR"] = B + "/weights/kimodo"
os.environ["TEXT_ENCODERS_DIR"] = B + "/work/kimodo/textenc"
os.environ["TEXT_ENCODER_MODE"] = "local"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["PYTHONPATH"] = B + "/repos/kimodo"
sys.path.insert(0, B + "/envs/kimodo/lib/python3.10/site-packages")
sys.path.insert(0, B + "/repos/kimodo")

import numpy as np
import torch
from kimodo import load_model
from kimodo.geometry import matrix_to_axis_angle
from kimodo.exports.mujoco import MujocoQposConverter

class NoTE:
    def __call__(self, t): raise AssertionError
    def to(self, d): return self
    def eval(self): return self

model, resolved = load_model("kimodo-g1-rp", device="cpu", default_family="Kimodo",
                             return_resolved_name=True, text_encoder=NoTE())
skel = model.skeleton
print("skeleton:", skel.name, "n_joints:", skel.n_joints if hasattr(skel, "n_joints") else "?",
      "root_idx:", skel.root_idx)

z = np.load(a.npz)
local_rot_mats = torch.from_numpy(z["local_rot_mats"]).float()  # (T,34,3,3)
root_positions = torch.from_numpy(z["root_positions"]).float()   # (T,3)
smooth_root_pos = torch.from_numpy(z["smooth_root_pos"]).float() # (T,3)
posed_joints = torch.from_numpy(z["posed_joints"]).float()       # (T,34,3)
T_frames = local_rot_mats.shape[0]
pin = a.frame
assert pin < T_frames, f"pin frame {pin} >= T {T_frames}"

print("free motion T:", T_frames)
# The posed_joints field is already the global joint positions. Look up palm index.
joint_names = None
for attr in ("bone_name", "joint_names", "node_names"):
    if hasattr(skel, attr):
        joint_names = getattr(skel, attr)
        break
if joint_names is None:
    # try to introspect
    for k in dir(skel):
        v = getattr(skel, k)
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], str):
            joint_names = v
            break
if joint_names is None:
    raise RuntimeError("cannot find skeleton joint names")

print("joint names (first 40):", joint_names[:40])
# Try common right-palm / right-wrist names
target_names = a.palm_joint
# Target proxy joint (KIMODO skeleton has no RightHand joint — only the site exists in MuJoCo).
# right_hand_roll_skel is the last right-arm joint, closest to the palm site.
if target_names is None:
    target_names = "right_hand_roll_skel"
if target_names not in joint_names:
    raise RuntimeError("target joint " + target_names + " not in skeleton")
palm_idx = list(joint_names).index(target_names)
print("using palm joint:", target_names, "index", palm_idx)

# palm position in KIMODO native coords at pinned frame
palm_kim = posed_joints[pin, palm_idx, :].numpy()  # (3,)
print("palm KIMODO pos at pin:", palm_kim.tolist())

# MuJoCo cube target -> KIMODO coords
MUJOCO_TO_KIMODO = np.array([[0.0,1.0,0.0],[0.0,0.0,1.0],[1.0,0.0,0.0]])
cube_mujoco = np.array([float(x) for x in a.target_mujoco.split(",")])
cube_kim = MUJOCO_TO_KIMODO @ cube_mujoco
print("cube MuJoCo:", cube_mujoco.tolist(), "-> KIMODO:", cube_kim.tolist())

shift = cube_kim - palm_kim
print("shift (KIMODO):", shift.tolist())

# Build constraint JSON
axis_angle = matrix_to_axis_angle(local_rot_mats[pin:pin+1])  # (1,34,3)
root_positions_pinned = root_positions[pin:pin+1] + torch.from_numpy(shift).unsqueeze(0)
smooth_2d = smooth_root_pos[pin:pin+1, :2] + torch.from_numpy(shift[:2]).unsqueeze(0)

out = {
    "type": "right-hand",
    "frame_indices": [int(pin)],
    "local_joints_rot": [[[float(v) for v in row] for row in aa] for aa in axis_angle.numpy()],
    "root_positions": [[float(v) for v in row] for row in root_positions_pinned.numpy()],
    "smooth_root_2d": [[float(v) for v in row] for row in smooth_2d.numpy()],
}

os.makedirs(os.path.dirname(a.out), exist_ok=True)
with open(a.out, "w") as fh:
    json.dump([out], fh, indent=1)

# Verify by re-loading via library
from kimodo.constraints import load_constraints_lst
lst = load_constraints_lst(a.out, skel)
print("re-loaded", len(lst), "constraint set(s); first:", lst[0])
print("wrote", a.out)

# Diagnostic: FK the pinned constraint on CPU to see the reconstructed palm pos
lc = lst[0]
gp = lc.global_joints_positions.numpy()  # shape (n_frames, n_joints, 3)
print("constraint FK reconstructed global joint pos at pin:", gp[0, palm_idx].tolist())
