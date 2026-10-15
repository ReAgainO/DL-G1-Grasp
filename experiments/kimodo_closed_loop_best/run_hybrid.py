"""Run the OFFICIAL SONIC grasp harness on the hybrid CSV.

Same invocation as the delivered SUCCESS run (reverify_correct.py): the
official env python, harness copy in the old task dir, runner flags
--motion-source kimodo + --hand-open/--hand-closed (fingers driven by the
runner's own program: open before close-start, close 2.5s..+0.8s, hold).
Adds a cube-contact trace for diagnosis. Prints [RESULT] lines verbatim.
"""
import json
import os
import subprocess

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
PY = "/data/group4/20261004-205550-qoder-1280b420/env/bin/python"
MOTION = os.path.join(NEW, "hybrid_body_v1.csv")
HAND = os.path.join(NEW, "hybrid_hand_v1.csv")

import csv
rows = list(csv.reader(open(HAND)))
OPEN = [float(x) for x in rows[0][-7:]]
CLOSED = [float(x) for x in rows[-1][-7:]]

RUN = os.path.join(NEW, "run_hybrid_one.py")
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
TRACE=[]
_o=mujoco.mj_step
def st2(m,dat,*a,**k):
    _o(m,dat,*a,**k)
    try:
        gid=int(m.geom("red_cube_geom").id); cid=int(m.body("red_cube").id)
    except Exception: return
    hit=[]
    for i in range(dat.ncon):
        c=dat.contact[i]; g1,g2=int(c.geom1),int(c.geom2)
        other = g2 if g1==gid else (g1 if g2==gid else None)
        if other is None: continue
        hit.append(mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,int(m.geom_bodyid[other])) or "?")
    TRACE.append({"t":round(len(TRACE)*0.002,3),"cube":dat.xpos[cid].copy().tolist(),"hit":hit})
mujoco.mj_step=st2; rg.mujoco.mj_step=st2
OPEN=json.loads(os.environ["HAND_OPEN"]); CLOSED=json.loads(os.environ["HAND_CLOSED"])
A=lambda v:[str(x) for x in v]
sys.argv=["run_grasp.py","--config",H+"/sonic_cpu.yaml","--scene",H+"/bridge/g1/scene_grasp_hand.xml",
 "--headless","--allow-failure","--duration",os.environ.get("DURATION","8"),
 "--motion-source","kimodo","--motion-file",os.environ["MOTION"],"--source-fps","30",
 "--close-start",os.environ.get("CLOSE_START","2.5"),"--close-duration","0.8",
 "--lift-start",os.environ.get("LIFT_START","4.0"),"--lift-duration","2.0",
 "--hand-open"]+A(OPEN)+["--hand-closed"]+A(CLOSED)
try: rg.main()
except SystemExit: pass
cube0=np.array([0.267,-0.118,0.7745])
drift=0.0; first=None; touched=set()
for i,r in enumerate(TRACE):
    c=np.array(r["cube"]); drift=max(drift,float(np.linalg.norm(c-cube0))*1000)
    for b in r["hit"]:
        touched.add(b)
        if first is None and b and not b.startswith("right_hand_"): first=(r["t"],b)
pre=[r for r in TRACE if r["t"]<2.5]
pre_drift=max((float(np.linalg.norm(np.array(r["cube"])-cube0))*1000 for r in pre),default=0.0)
print("SEARCHRESULT "+json.dumps({"first_nonfinger_hit":first,
      "max_cube_drift_mm":round(drift,1),
      "pre_close_drift_mm":round(pre_drift,2),
      "touched":sorted(touched),
      "final_cube":[round(x,4) for x in TRACE[-1]["cube"]] if TRACE else None}))
''')

env = dict(os.environ)
env.update({
    "TASKDIR": OLD, "MOTION": MOTION,
    "HAND_OPEN": json.dumps(OPEN), "HAND_CLOSED": json.dumps(CLOSED),
    "CLOSE_START": "2.5", "LIFT_START": "4.0", "DURATION": "8",
    "MUJOCO_GL": "osmesa", "PYOPENGL_PLATFORM": "osmesa",
    "LD_LIBRARY_PATH": "/home/group4/group4_dasc7606c/render_test/mesa_probe"
                       "/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64"
                       "/usr/lib/x86_64-linux-gnu:"
                       + os.environ.get("LD_LIBRARY_PATH", ""),
    "OMP_NUM_THREADS": "8", "TMPDIR": NEW,
})
log = os.path.join(NEW, "hybrid_run1.log")
with open(log, "w") as f:
    p = subprocess.run([PY, RUN], stdout=f, stderr=subprocess.STDOUT,
                       env=env, cwd=OLD, timeout=1500)
print("runner rc =", p.returncode)
for line in open(log):
    if line.startswith(("[RESULT]", "[FINGERTIP_DISTANCE]", "[ROBOT_STATE]",
                        "SEARCHRESULT")):
        print(line.rstrip())
