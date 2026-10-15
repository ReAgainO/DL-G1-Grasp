
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
