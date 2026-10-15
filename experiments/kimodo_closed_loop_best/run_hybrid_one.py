
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
