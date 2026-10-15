"""Offline saved-trajectory visualization, explicitly labeled as hybrid."""
import json,subprocess,sys
from pathlib import Path
import mujoco,numpy as np
root=Path(sys.argv[1]);out=root/'out'/sys.argv[2]
r=json.loads((out/'result.json').read_text());z=np.load(out/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(out/'scene_fixed_grasp.xml'));d=mujoco.MjData(m)
width,height,stride=640,480,2
renderer=mujoco.Renderer(m,height=height,width=width);cam=mujoco.MjvCamera()
cam.type=mujoco.mjtCamera.mjCAMERA_FREE;cam.lookat[:]=[.25,-.1,.85];cam.distance=.85;cam.azimuth=-125;cam.elevation=-15
ff='/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'
size=f'{width}x{height}';fps=str(float(z['fps'])/stride)
proc=subprocess.Popen([ff,'-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-r',fps,'-i','-',
                       '-an','-c:v','libx264','-threads','4','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'grasp.mp4')],stdin=subprocess.PIPE)
selected={}
for phase in ['CLOSE','LIFT','HOLD','RELEASE']:
 ix=np.flatnonzero(z['phase']==phase)
 if len(ix):selected[int(ix[len(ix)//2])//stride*stride]=phase
try:
 for i in range(0,len(z['qpos']),stride):
  q=z['qpos'][i]
  d.qpos[:]=q;d.qvel[:]=z['qvel'][i];mujoco.mj_forward(m,d);renderer.update_scene(d,camera=cam)
  pixels=renderer.render().copy();status='GRASP PASS' if r['success'] else 'GRASP FAILED'
  mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100,mujoco.mjtGridPos.mjGRID_TOPLEFT,mujoco.MjrRect(0,0,width,height),
                     f'HYBRID calibrated + ARDY prior\n{z["phase"][i]} | t={z["time"][i]:.2f}s',
                     f'{status}\nPhysical contact / no attachment',renderer._mjr_context)
  mujoco.mjr_readPixels(pixels,None,mujoco.MjrRect(0,0,width,height),renderer._mjr_context);pixels=np.flipud(pixels).copy()
  proc.stdin.write(pixels.tobytes())
  if i in selected:
   subprocess.run([ff,'-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-i','-',
                   '-frames:v','1',str(out/('frame_'+selected[i]+'.png'))],input=pixels.tobytes(),check=True,timeout=20)
  if i%100==0:print(f'render {i}/{len(z["qpos"])}',flush=True)
finally:
 proc.stdin.close();renderer.close()
assert proc.wait(timeout=20)==0
subprocess.run([ff,'-v','info','-nostdin','-threads','4','-i',str(out/'grasp.mp4'),'-f','null','-'],check=True,timeout=30)
print('VIDEO_READY',out/'grasp.mp4')
