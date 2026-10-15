"""ws1 shared lib: paths, hashing, runtime stamps, json io.

Task 20261008-221515-qoder-03c4673f / worker ws1 (menagerie G1 grip reproduction).
"""
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

ROOT = "/data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie"
MODEL_XML = os.path.join(ROOT, "model", "unitree_g1", "g1_with_hands.xml")
MODEL_DIR = os.path.join(ROOT, "model", "unitree_g1")
OUT = os.path.join(ROOT, "out")
PROBE_DIR = os.path.join(OUT, "probe")
RUNS_DIR = os.path.join(OUT, "runs")
VIDEO_DIR = os.path.join(ROOT, "video")

# right-hand finger joint names, declaration order per body in g1_with_hands.xml
RH_JOINTS = [
    "right_hand_thumb_0_joint",
    "right_hand_thumb_1_joint",
    "right_hand_thumb_2_joint",
    "right_hand_middle_0_joint",
    "right_hand_middle_1_joint",
    "right_hand_index_0_joint",
    "right_hand_index_1_joint",
]
RH_BODIES_THUMB = ["right_hand_thumb_0_link", "right_hand_thumb_1_link", "right_hand_thumb_2_link"]
RH_BODIES_INDEX = ["right_hand_index_0_link", "right_hand_index_1_link"]
RH_BODIES_MIDDLE = ["right_hand_middle_0_link", "right_hand_middle_1_link"]
RH_BODY_PALM = "right_hand_palm_link"
HAND_BODY = "right_wrist_yaw_link"  # frame that carries the finger curl axes

RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp(extra=None):
    """runtime_stamp required by the task: mujoco/python/model/scene-gen/dt."""
    import mujoco

    s = {
        "generated": now(),
        "taskid": "20261008-221515-qoder-03c4673f",
        "worker": "ws1",
        "mujoco_version": mujoco.__version__,
        "sys_executable": sys.executable,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "model_sha": sha256_file(MODEL_XML),
        "model_xml": MODEL_XML,
        "scene_generator_sha": sha256_file(os.path.join(ROOT, "scripts", "ws1_make_scene.py")),
        "dt": None,  # filled by caller from m.opt.timestep
        "hostname": platform.node(),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
    }
    if extra:
        s.update(extra)
    return s


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)


def jload(path):
    with open(path) as f:
        return json.load(f)


def joint_ids(m, names):
    import mujoco

    return [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n) for n in names]


def body_geom_ids(m, body_name):
    """ids of all geoms attached to body (visual+collision)."""
    import mujoco

    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body_name)
    out = []
    for g in range(m.ngeom):
        if m.geom_bodyid[g] == bid:
            out.append(g)
    return out


def finger_groups(m):
    """dict group -> list of geom ids (thumb/index/middle/palm).

    Note: the palm is a geom attached to right_wrist_yaw_link (mesh
    right_hand_palm_link.STL), there is no separate palm body.
    """
    import mujoco

    palm_mesh = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_MESH, "right_hand_palm_link")
    palm = []
    if palm_mesh >= 0:
        palm = [g for g in range(m.ngeom) if m.geom_dataid[g] == palm_mesh]
    return {
        "thumb": sum((body_geom_ids(m, b) for b in RH_BODIES_THUMB), []),
        "index": sum((body_geom_ids(m, b) for b in RH_BODIES_INDEX), []),
        "middle": sum((body_geom_ids(m, b) for b in RH_BODIES_MIDDLE), []),
        "palm": palm,
    }
