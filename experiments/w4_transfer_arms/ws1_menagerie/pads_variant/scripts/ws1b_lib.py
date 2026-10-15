"""ws1b lib: paths, hashing, runtime stamps, json io (pads-only variant harness).

Task 20261008-221515-qoder-03c4673f / worker ws1b.
Source: W1 sandbox scripts (ws1_menagerie/scripts) copied read-only and adapted;
all outputs live under ws1_menagerie/pads_variant/.
"""
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

ROOT = "/data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie/pads_variant"
W1_ROOT = "/data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie"  # read-only source
MODEL_DIR = os.path.join(ROOT, "model", "unitree_g1")
MODEL_XML = os.path.join(MODEL_DIR, "g1_with_hands.xml")          # official asset copy
VARIANT_XML = os.path.join(MODEL_DIR, "ws1b_scene_model.xml")     # pads-only variant
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

# pads-only variant: one fingertip pad sphere per finger on the distal body
PAD_BODIES = {
    "thumb": "right_hand_thumb_2_link",
    "index": "right_hand_index_1_link",
    "middle": "right_hand_middle_1_link",
}
PAD_GEOM_NAMES = {
    "thumb": "ws1b_pad_thumb",
    "index": "ws1b_pad_index",
    "middle": "ws1b_pad_middle",
}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp(extra=None):
    """runtime_stamp required by the task: mujoco/python/model/variant/generators/dt."""
    import mujoco

    s = {
        "generated": now(),
        "taskid": "20261008-221515-qoder-03c4673f",
        "worker": "ws1b",
        "variant": "pads-only",
        "mujoco_version": mujoco.__version__,
        "sys_executable": sys.executable,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "model_sha": sha256_file(MODEL_XML),
        "model_xml": MODEL_XML,
        "variant_model_xml": VARIANT_XML,
        "variant_model_sha": sha256_file(VARIANT_XML),
        "scene_generator_sha": sha256_file(os.path.join(ROOT, "scripts", "ws1b_make_scene.py")),
        "variant_generator_sha": sha256_file(os.path.join(ROOT, "scripts", "ws1b_make_variant.py")),
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


def pad_ids(m):
    """pads-only: geom ids of the three fingertip pads (the only load-bearing geoms)."""
    import mujoco

    out = {}
    for k, n in PAD_GEOM_NAMES.items():
        gid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, n)
        if gid < 0:
            raise RuntimeError("pad geom missing: %s" % n)
        out[k] = gid
    return out


def body_geom_ids(m, body_name):
    import mujoco

    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body_name)
    return [g for g in range(m.ngeom) if m.geom_bodyid[g] == bid]
