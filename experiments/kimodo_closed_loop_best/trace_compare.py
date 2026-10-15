"""Compare OFFICIAL-runner tracking between delivered CSV (known SUCCESS) and
the hybrid V1 (failed): trace actual base/wrist/fingertips at key times and
all cube contacts. Read-only diagnostic; writes trace JSON to NEW dir.
"""
import json
import os
import subprocess

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
PY = "/data/group4/20261004-205550-qoder-1280b420/env/bin/python"
DELIV_BODY = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables"
    "/g1_right_hand_grasp_body_195f30fps.csv")
HAND = os.path.join(NEW, "hybrid_hand_v1.csv")

import csv
rows = list(csv.reader(open(HAND)))
OPEN = [float(x) for x in rows[0][-7:]]
CLOSED = [float(x) for x in rows[-1][-7:]]

RUN = os.path.join(NEW, "trace_one.py")
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
SAMPLES=[]
_o=mujoco.mj_step
KEYS={1.2,1.8,2.2,2.4,2.5,2.6,3.0,3.3,3.6,4.0,4.5,5.0,5.5,6.0,6.4}
t=[0.0]
def st2(m,dat,*a,**k):
    _o(m,dat,*a,**k)
    t[0]+=m.opt.timestep
    tt=round(t[0],3)
    if any(abs(tt-k)<m.opt.timestep*0.6 for k in KEYS):
        try:
            wb=int(m.body("right_wrist_yaw_link").id)
            cid=int(m.body("red_cube").id)
            gid=int(m.geom("red_cube_geom").id)
            ft=[int(m.geom(g).id) for g in
                ["right_thumb_fingertip","right_index_fingertip","right_middle_fingertip"]]
            hits=[]
            for i in range(dat.ncon):
                c=dat.contact[i]; g1,g2=int(c.geom1),int(c.geom2)
                if g1==gid or g2==gid:
                    og = g2 if g1==gid else g1
                    hits.append(mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,og) or str(og))
            SAMPLES.append({"t":tt,
                "base":[round(x,4) for x in dat.qpos[0:3]],
                "wrist":[round(x,4) for x in dat.xpos[wb]],
                "cube":[round(x,4) for x in dat.xpos[cid]],
                "ft":[ [round(x,4) for x in dat.geom_xpos[g]] for g in ft],
                "cube_hits":hits})
        except Exception as e:
            SAMPLES.append({"t":tt,"err":str(e)})
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
print("TRACERESULT "+json.dumps(SAMPLES))
''')

env = dict(os.environ)
env.update({
    "TASKDIR": OLD,
    "HAND_OPEN": json.dumps(OPEN), "HAND_CLOSED": json.dumps(CLOSED),
    "MUJOCO_GL": "osmesa", "PYOPENGL_PLATFORM": "osmesa",
    "LD_LIBRARY_PATH": "/home/group4/group4_dasc7606c/render_test/mesa_probe"
                       "/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64"
                       "/usr/lib/x86_64-linux-gnu:"
                       + os.environ.get("LD_LIBRARY_PATH", ""),
    "OMP_NUM_THREADS": "8", "TMPDIR": NEW,
})
DOCK = [0.20256, -0.22152, 0.87778]
for tag, motion in (("delivered", DELIV_BODY),
                    ("hybrid_v1", os.path.join(NEW, "hybrid_body_v1.csv"))):
    env["MOTION"] = motion
    log = os.path.join(NEW, "trace_%s.log" % tag)
    with open(log, "w") as f:
        subprocess.run([PY, RUN], stdout=f, stderr=subprocess.STDOUT,
                       env=env, cwd=OLD, timeout=1500)
    trace = None
    result = ""
    for line in open(log):
        if line.startswith("TRACERESULT "):
            trace = json.loads(line[len("TRACERESULT "):])
        if line.startswith("[RESULT]"):
            result = line.strip()
    print("=" * 70)
    print(tag, "->", result[:150])
    if trace:
        for s in trace:
            if "err" in s:
                print("  ", s)
                continue
            wd = sum((a - b) ** 2 for a, b in zip(s["wrist"], DOCK)) ** 0.5 * 1000
            print("  t=%.2f base=%s wrist=%s (vs dock %.0fmm) cube=%s hits=%s"
                  % (s["t"], s["base"], s["wrist"], wd, s["cube"],
                     s["cube_hits"]))
