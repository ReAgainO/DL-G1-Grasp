"""Decisive probe: does the SonicPolicy follow the CSV's RIGHT-ARM content at all?

Variants (official runner, unmodified except instrumentation):
  baseline   : no --motion-source (keyframe mode, official arm channel)
  stand_arm  : CSV with right arm frozen at stand for all 195 frames
  dock_arm   : CSV with right arm frozen at the validated dock pose
  raised_arm : CSV with right arm at a completely different pose (up/back)

For each: executed wrist pos/quat at the settled close phase, the policy's own
PD target for the 7 arm joints vs the executed joint angles (droop), the
fingertip distances, and the [RESULT] line.
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
PY = sys.executable
DELIV = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables")
BODY = os.path.join(DELIV, "g1_right_hand_grasp_body_195f30fps.csv")
HAND = os.path.join(DELIV, "g1_right_hand_grasp_hand_195f30fps.csv")

ARMCSV = list(range(29, 36))
deliv = np.loadtxt(BODY, delimiter=",", dtype=float)
base = deliv.copy()
base[:, 0:3] = [0.0, 0.0, 0.7887]
base[:, 3:7] = [1.0, 0.0, 0.0, 0.0]

variants = {}
for i, (name, arm) in enumerate([
        ("stand_arm", deliv[0, ARMCSV]),
        ("dock_arm", deliv[75, ARMCSV]),
        ("raised_arm", np.array([-1.2, 0.9, -1.6, 1.9, -1.4, 1.5, 0.1]))]):
    q = base.copy()
    q[:, ARMCSV] = arm
    p = os.path.join(NEW, "probe_%s.csv" % name)
    np.savetxt(p, q, delimiter=",", fmt="%.8f")
    variants[name] = p

rows = list(csv.reader(open(HAND)))
OPEN = [float(x) for x in rows[0][-7:]]
CLOSED = [float(x) for x in rows[-1][-7:]]

RUN = os.path.join(NEW, "probe_one.py")
open(RUN, "w").write(r'''
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
from adapters.sonic_action_adapter import SonicActionAdapter
TARGETS=[]; POLICYT=[]; LIMHIT=[]
_orig_set = SonicActionAdapter.set_action
def set_action(self, raw):
    t = _orig_set(self, raw)
    clamp = int((np.abs(np.asarray(raw))>3.5).sum())
    TARGETS.append((round(float(self._target[22]),4), round(float(self._target[23]),4),
                    round(float(self._target[24]),4), round(float(self._target[25]),4),
                    round(float(self._target[26]),4), round(float(self._target[27]),4),
                    round(float(self._target[28]),4)))
    LIMHIT.append(clamp)
    return t
SonicActionAdapter.set_action = set_action
_o=mujoco.mj_step
next_t=[0.0]
S=[]
def st2(m,dat,*a,**k):
    _o(m,dat,*a,**k)
    if dat.time < next_t[0]: return
    next_t[0] = dat.time + 0.05
    try:
        wb=int(m.body("right_wrist_yaw_link").id)
        S.append({"t":round(float(dat.time),3),
            "base":[round(float(x),4) for x in dat.qpos[0:3]],
            "wpos":[round(float(x),4) for x in dat.xpos[wb]],
            "wquat":[round(float(x),5) for x in dat.xquat[wb]],
            "armq":[round(float(dat.qpos[22+i]),4) for i in range(7)],
            "cube":[round(float(x),4) for x in dat.xpos[int(m.body("red_cube").id)]]})
    except Exception: pass
mujoco.mj_step=st2; rg.mujoco.mj_step=st2
OPEN=json.loads(os.environ["HAND_OPEN"]); CLOSED=json.loads(os.environ["HAND_CLOSED"])
A=lambda v:[str(x) for x in v]
argv=["run_grasp.py","--config",H+"/sonic_cpu.yaml","--scene",H+"/bridge/g1/scene_grasp_hand.xml",
 "--headless","--allow-failure","--duration","5.5",
 "--close-start","2.5","--close-duration","0.8","--lift-start","4.0","--lift-duration","1.4",
 "--hand-open"]+A(OPEN)+["--hand-closed"]+A(CLOSED)
if os.environ.get("MOTION"):
    argv += ["--motion-source","kimodo","--motion-file",os.environ["MOTION"],"--source-fps","30"]
sys.argv=argv
try: rg.main()
except SystemExit: pass
print("PROBE "+json.dumps({"samples":S,"targets":TARGETS[60:70],"limhit":LIMHIT[60:70]}))
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

for name, motion in [("baseline", None)] + list(variants.items()):
    env = dict(ENV)
    env["MOTION"] = motion or ""
    log = os.path.join(NEW, "probe_%s.log" % name)
    with open(log, "w") as f:
        subprocess.run([PY, RUN], stdout=f, stderr=subprocess.STDOUT,
                       env=env, cwd=OLD, timeout=1500)
    result, ftd, probe = "", {}, None
    for line in open(log):
        if line.startswith("[RESULT]"):
            result = line.strip()[:200]
        elif line.startswith("[FINGERTIP_DISTANCE]"):
            for tok in line.strip().split()[1:]:
                k, v = tok.split("=")
                ftd[k] = round(float(v) * 1000, 1)
        elif line.startswith("PROBE "):
            probe = json.loads(line[6:])
    print("=" * 74)
    print(name, "->", result)
    print("   fingertip mm:", ftd)
    if probe:
        st = [s for s in probe["samples"] if 2.9 <= s["t"] <= 3.3]
        if st:
            w = np.array([s["wpos"] for s in st]).mean(axis=0)
            q = np.array([s["armq"] for s in st]).mean(axis=0)
            b = np.array([s["base"] for s in st]).mean(axis=0)
            print("   exec wrist=%s  base=%s" % (np.round(w, 4).tolist(),
                                                 np.round(b, 4).tolist()))
            print("   exec arm q=%s" % np.round(q, 4).tolist())
        if probe["targets"]:
            print("   policy PD target (arm) mid-run=%s" % probe["targets"][-1])
            print("   raw-action clamp hits (|raw|>3.5): %s" % probe["limhit"])
