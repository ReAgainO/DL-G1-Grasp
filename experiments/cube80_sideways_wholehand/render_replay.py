"""Recorded state visualization only. Zero physics steps, no fabricated lift."""
import os,resource,sys,json,hashlib,subprocess
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import numpy as np,mujoco
R=Path(__file__).resolve().parent;ep=R/'out'/sys.argv[1]
assert ep.parent==R/'out'
r=json.loads((ep/'result.json').read_text());z=np.load(ep/'trajectory.npz',allow_pickle=False)
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert r['runtime_stamp']['model_xml_sha']['robot']==sha(ep/'robot.xml')
out=ep/'replay';out.mkdir()
m=mujoco.MjModel.from_xml_path(str(ep/'scene.xml'));d=mujoco.MjData(m)
ff=Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
W,H=480,320;renderer=mujoco.Renderer(m,height=H,width=W)
full=mujoco.MjvCamera();full.lookat[:]=[.10,-.05,.80];full.distance=2.30;full.azimuth=-115;full.elevation=-12
hand=mujoco.MjvCamera();hand.lookat[:]=[.35,-.18,.85];hand.distance=.65;hand.azimuth=-120;hand.elevation=-20
indices=np.flatnonzero(z['time']>=34)[::4];fps=12.5
video=out/'grasp.mp4';log=(out/'ffmpeg.log').open('wb')
command=[str(ff),'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-r',str(fps),'-i','-',
 '-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
proc=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
phaseframes={}
for phase in ['CLOSE','TEST_LIFT','LIFT','HOLD']:
 xs=np.flatnonzero(z['phase'][indices]==phase)
 if len(xs):phaseframes[int(indices[xs[len(xs)//2]])]=phase
try:
 for k in indices:
  d.qpos[:]=z['qpos'][k];d.qvel[:]=z['qvel'][k];mujoco.mj_forward(m,d)
  panels=[]
  for cam in [full,hand]:
   renderer.update_scene(d,camera=cam);renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=False
   pixels=renderer.render().copy()
   text=f"WHOLE HAND {'NATIVE GEOMETRY' if r.get('native_mesh_only') else '+ SPHERICAL PADS'}\n{z['phase'][k]} t={z['time'][k]:.2f}s | recorded physics"
   mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100,mujoco.mjtGridPos.mjGRID_TOPLEFT,mujoco.MjrRect(0,0,W,H),text,
    'No attachment / free base\nSONIC body + separate fingers',renderer._mjr_context)
   mujoco.mjr_readPixels(pixels,None,mujoco.MjrRect(0,0,W,H),renderer._mjr_context);panels.append(np.flipud(pixels).copy())
  canvas=np.concatenate(panels,axis=1);proc.stdin.write(canvas.tobytes())
  if int(k) in phaseframes:
   subprocess.run([str(ff),'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-i','-',
     '-frames:v','1',str(out/f"frame_{phaseframes[int(k)]}.png")],input=canvas.tobytes(),check=True,timeout=20)
finally:
 proc.stdin.close();renderer.close()
assert proc.wait(timeout=20)==0
subprocess.run([str(ff),'-v','error','-nostdin','-threads','1','-i',str(video),'-f','null','-'],check=True,timeout=30)
stamp={'source':str(ep),'source_trajectory_sha':sha(ep/'trajectory.npz'),'source_result_sha':sha(ep/'result.json'),
 'replay_only':True,'physical_steps':0,'frames':len(indices),'fps':fps,'source_time_range_s':[float(z['time'][indices[0]]),float(z['time'][indices[-1]])],
 'success':r['success'],'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,'renderer_sha':sha(__file__),
 'ffmpeg_sha':sha(ff),'video_sha':sha(video),'video_bytes':video.stat().st_size,'decode_verified':True}
(out/'replay.json').write_text(json.dumps(stamp,indent=2));print(json.dumps(stamp,indent=2))
