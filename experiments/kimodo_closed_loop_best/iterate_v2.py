"""Closed-loop pre-compensation of the hybrid CSV against the OFFICIAL runner.

Each round:
  1. build_v2.py with current joint-space compensation `comp`
  2. run the official run_grasp.py (unmodified) with a dense tracer
  3. measure executed wrist pos/quat at the settled close phase (2.9-3.3s)
  4. update comp: shift the dock reference by the observed execution error
     (position via Cartesian IK on the fixed-base model, orientation folded
     into the IK target)
Stop early when [RESULT] success=True.

Run with the official env python. ~2-3 min per round.
"""
import csv
import json
import os
import subprocess
import sys

import mujoco
import numpy as np

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
PY = sys.executable
SCENE = os.path.join(OLD, "harness/bridge/g1/scene_grasp_hand.xml")
DELIV = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables")
HAND = os.path.join(DELIV, "g1_right_hand_grasp_hand_195f30fps.csv")
ROUNDS = int(os.environ.get("ROUNDS", "4"))

ARM_NAMES = ["right_shoulder_pitch_joint", "right_shoulder_roll_joint",
             "right_shoulder_yaw_joint", "right_elbow_joint",
             "right_wrist_roll_joint", "right_wrist_pitch_joint",
             "right_wrist_yaw_joint"]
ROOT = np.array([0.0, 0.0, 0.7887])
DOCK_QUAT = np.array([0.64145, -0.5888, -0.2656, 0.41389])

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
JO = json.load(open(os.path.join(OLD, "joint_order.json")))["sonic_order"]
ADR, DOF = {}, {}
for i in range(m.njnt):
    n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i)
    if n:
        ADR[n] = int(m.jnt_qposadr[i])
        DOF[n] = int(m.jnt_dofadr[i])
ARM_Q = [ADR[n] for n in ARM_NAMES]
ARM_DOF = [DOF[n] for n in ARM_NAMES]
ARMCSV = [7 + JO.index(n) for n in ARM_NAMES]
ARM_RANGE = np.array([m.jnt_range[m.joint(n).id] for n in ARM_NAMES])
WB = int(m.body("right_wrist_yaw_link").id)
deliv = np.loadtxt(os.path.join(DELIV, "g1_right_hand_grasp_body_195f30fps.csv"),
                   delimiter=",", dtype=float)
BASE = deliv[0]
DOCK_ARM = deliv[75, ARMCSV].copy()

rows = list(csv.reader(open(HAND)))
OPEN = [float(x) for x in rows[0][-7:]]
CLOSED = [float(x) for x in rows[-1][-7:]]

# ---------------- runner with tracer (written once) ----------------
TRACE_RUN = os.path.join(NEW, "trace_round.py")
open(TRACE_RUN, "w").write(r'''
import sys, os, types, importlib.abc, importlib.machinery, json
import numpy as np
class _S(types.ModuleType):
    __path__=[]
    def __getattr__(self,n):
        if n.startswith("__"): raise AttributeError(n)
        c=type(n,(object,),{"__module__":self.__name__}); setattr(self,n,c); return c
class _L(importlib.abc.Loader):
    def create_module(self,s):
        m=_S(s.name); m.__path__=[]; return m
    def exec_module(self,m): pass
class _F(importlib.abc.MetaPathFinder):
    def find_spec(self,fn,path=None,target=None):
        if fn=="trl" or fn.startswith("trl."):
            return importlib.machinery.ModuleSpec(fn,_L(),is_package=True)
        return None
sys.meta_path.insert(0,_F())
D=os.environ["TASKDIR"]; H=D+"/harness"
sys.path.insert(0,H+"/bridge")
import importlib.util
spec=importlib.util.spec_from_file_location("rgmod",H+"/bridge/runners/run_grasp.py")
rg=importlib.util.module_from_spec(spec)
sys.argv=["run_grasp.py"]
try: spec.loader.exec_module(rg)
except SystemExit: pass
import mujoco
S=[]
_o=mujoco.mj_step
next_t=[0.0]
def st2(m,dat,*a,**k):
    _o(m,dat,*a,**k)
    if dat.time < next_t[0]: return
    next_t[0] = dat.time + 0.05
    try:
        wb=int(m.body("right_wrist_yaw_link").id); cid=int(m.body("red_cube").id)
        gid=int(m.geom("red_cube_geom").id)
        ft=[int(m.geom(g).id) for g in
            ["right_thumb_fingertip","right_index_fingertip","right_middle_fingertip"]]
        nb=0
        for i in range(dat.ncon):
            c=dat.contact[i]
            if int(c.geom1)==gid or int(c.geom2)==gid:
                og=int(c.geom2) if int(c.geom1)==gid else int(c.geom1)
                bn=mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,int(m.geom_bodyid[og])) or ""
                if bn.startswith("right_hand_"): nb+=1
        S.append({"t":round(float(dat.time),3),
                  "base":[round(float(x),4) for x in dat.qpos[0:3]],
                  "wpos":[round(float(x),4) for x in dat.xpos[wb]],
                  "wquat":[round(float(x),5) for x in dat.xquat[wb]],
                  "cube":[round(float(x),4) for x in dat.xpos[cid]],
                  "ft":[[round(float(y),4) for y in dat.geom_xpos[g]] for g in ft],
                  "nfc":nb})
    except Exception: pass
mujoco.mj_step=st2; rg.mujoco.mj_step=st2
OPEN=json.loads(os.environ["HAND_OPEN"]); CLOSED=json.loads(os.environ["HAND_CLOSED"])
A=lambda v:[str(x) for x in v]
sys.argv=["run_grasp.py","--config",H+"/sonic_cpu.yaml","--scene",H+"/bridge/g1/scene_grasp_hand.xml",
 "--headless","--allow-failure","--duration","8",
 "--motion-source","kimodo","--motion-file",os.environ["MOTION"],"--source-fps","30",
 "--close-start","2.5","--close-duration","0.8",
 "--lift-start","4.0","--lift-duration","2.0",
 "--hand-open"]+A(OPEN)+["--hand-closed"]+A(CLOSED)
try: rg.main()
except SystemExit: pass
print("TRACERESULT "+json.dumps(S))
''')

ENV = dict(os.environ)
ENV.update({
    "TASKDIR": OLD,
    "HAND_OPEN": json.dumps(OPEN), "HAND_CLOSED": json.dumps(CLOSED),
    "MUJOCO_GL": "osmesa", "PYOPENGL_PLATFORM": "osmesa",
    "LD_LIBRARY_PATH": "/home/group4/group4_dasc7606c/render_test/mesa_probe"
                       "/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64"
                       "/usr/lib/x86_64-linux-gnu:"
                       + os.environ.get("LD_LIBRARY_PATH", ""),
    "OMP_NUM_THREADS": "8", "TMPDIR": NEW,
})


def fk(q):
    d.qpos[:] = 0
    d.qpos[0:3] = ROOT
    d.qpos[3:7] = [1, 0, 0, 0]
    for name in JO:
        d.qpos[ADR[name]] = BASE[7 + JO.index(name)]
    for k, adr in enumerate(ARM_Q):
        d.qpos[adr] = q[k]
    mujoco.mj_forward(m, d)
    return d.xpos[WB].copy(), d.xquat[WB].copy()


def ik(q_init, p_tgt, quat_tgt, iters=300, lam=1e-3):
    q = q_init.copy()
    jacp = np.zeros((3, m.nv))
    jacr = np.zeros((3, m.nv))
    for _ in range(iters):
        wpos, wquat = fk(q)
        e_p = p_tgt - wpos
        q_neg = np.zeros(4)
        mujoco.mju_negQuat(q_neg, wquat)
        q_err = np.zeros(4)
        mujoco.mju_mulQuat(q_err, quat_tgt, q_neg)
        e_r = np.zeros(3)
        mujoco.mju_quat2Vel(e_r, q_err, 1.0)
        if np.linalg.norm(e_p) < 1e-4 and np.linalg.norm(e_r) < 0.005:
            break
        mujoco.mj_jacBody(m, d, jacp, jacr, WB)
        J = np.vstack([jacp[:, ARM_DOF], jacr[:, ARM_DOF]])
        e = np.concatenate([e_p, 0.6 * e_r])
        dq = J.T @ np.linalg.solve(J @ J.T + lam**2 * np.eye(6), e)
        dq = np.clip(dq, -0.2, 0.2)
        q = np.clip(q + dq, ARM_RANGE[:, 0] + 0.02, ARM_RANGE[:, 1] - 0.02)
    return q


def quat_mul(a, b):
    out = np.zeros(4)
    mujoco.mju_mulQuat(out, a, b)
    return out


DOCK_POS, _ = fk(DOCK_ARM)
comp = np.zeros(7)
best = None
for r in range(ROUNDS):
    comp_path = os.path.join(NEW, "v2_comp.json")
    json.dump({"comp": [float(x) for x in comp]}, open(comp_path, "w"))
    body_csv = os.path.join(NEW, "hybrid_body_v2r%d.csv" % r)
    b = subprocess.run([PY, os.path.join(NEW, "build_v2.py"), body_csv, comp_path],
                       capture_output=True, text=True, timeout=300)
    if b.returncode != 0:
        print("BUILD FAIL", b.stdout, b.stderr)
        break
    env = dict(ENV)
    env["MOTION"] = body_csv
    log = os.path.join(NEW, "v2_round%d.log" % r)
    with open(log, "w") as f:
        subprocess.run([PY, TRACE_RUN], stdout=f, stderr=subprocess.STDOUT,
                       env=env, cwd=OLD, timeout=1500)
    result, ftd, trace = "", {}, None
    for line in open(log):
        if line.startswith("[RESULT]"):
            result = line.strip()
        elif line.startswith("[FINGERTIP_DISTANCE]"):
            for tok in line.strip().split()[1:]:
                k, v = tok.split("=")
                ftd[k] = float(v)
        elif line.startswith("TRACERESULT "):
            trace = json.loads(line[len("TRACERESULT "):])
    print("=" * 72)
    print("ROUND %d comp=%s" % (r, np.round(comp, 4).tolist()))
    print(" ", result)
    print("  fingertip_distance:", {k: round(v * 1000, 1) for k, v in ftd.items()})
    if trace is None:
        print("  NO TRACE -- abort")
        break
    settle = [s for s in trace if 2.9 <= s["t"] <= 3.3]
    wpos = np.array([s["wpos"] for s in settle]).mean(axis=0)
    wquat = np.array([s["wquat"] for s in settle]).mean(axis=0)
    wquat = wquat / np.linalg.norm(wquat)
    if np.dot(wquat, DOCK_QUAT) < 0:
        wquat = -wquat
    e_pos = DOCK_POS - wpos
    q_tmp = np.zeros(4)
    mujoco.mju_negQuat(q_tmp, wquat)
    q_err = quat_mul(DOCK_QUAT, q_tmp)
    e_rot = np.zeros(3)
    mujoco.mju_quat2Vel(e_rot, q_err, 1.0)
    nfc = max((s["nfc"] for s in settle), default=0)
    print("  exec wrist=%s err_pos=%s mm err_ori=%.1f deg cube_contacts=%d"
          % (np.round(wpos, 4).tolist(), np.round(e_pos * 1000, 1).tolist(),
             float(np.degrees(np.linalg.norm(e_rot))), nfc))
    if "success=True" in result:
        print("SUCCESS at round %d -> %s" % (r, body_csv))
        best = body_csv
        break
    # first-order pre-compensation: shift the dock reference by the error
    cur_ref = DOCK_ARM + comp
    ref_pos, ref_quat = fk(cur_ref)
    tgt_pos = ref_pos + e_pos
    # rotate reference orientation by the execution orientation error
    eq = np.zeros(4)
    mujoco.mju_axisAngle2Quat(eq, e_rot, float(np.linalg.norm(e_rot)))
    tgt_quat = quat_mul(eq, ref_quat)
    new_ref = ik(cur_ref, tgt_pos, tgt_quat)
    step = np.clip(new_ref - cur_ref, -0.35, 0.35)
    comp = comp + step
    over_lo = (ARM_RANGE[:, 0] + 0.02 - (DOCK_ARM + comp)).clip(min=0)
    over_hi = ((DOCK_ARM + comp) - ARM_RANGE[:, 1] + 0.02).clip(min=0)
    comp = comp + over_lo - over_hi
    if best is None and nfc >= 2:
        best = body_csv
print("DONE best=", best)
