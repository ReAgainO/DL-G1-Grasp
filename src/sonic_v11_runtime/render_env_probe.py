"""Tiny bounded render-only runtime probe, zero physical integration."""
import sys
import mujoco
import numpy as np
m=mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="1 1 .1"/><body pos="0 0 .2"><geom type="box" size=".1 .1 .1"/></body></worldbody></mujoco>')
d=mujoco.MjData(m);mujoco.mj_forward(m,d)
with mujoco.Renderer(m,height=32,width=32) as renderer:
    renderer.update_scene(d);frame=renderer.render().copy()
assert frame.shape==(32,32,3) and np.ptp(frame)>0
print(dict(physical_steps=0,mujoco_version=mujoco.__version__,numpy_version=np.__version__,sys_executable=sys.executable,pixel_range=[int(frame.min()),int(frame.max())],render_branch_executed=True))
