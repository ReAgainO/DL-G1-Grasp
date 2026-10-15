
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
