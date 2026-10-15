"""Two camera replay with short readable labels; never integrates physics."""
import os,resource,sys,json,hashlib,subprocess
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import numpy as np,mujoco
root=Path(__file__).resolve().parent
episode=root/'out'/sys.argv[1]
assert episode.parent==root/'out'
result=json.loads((episode/'result.json').read_text())
trajectory=np.load(episode/'trajectory.npz',allow_pickle=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert result['runtime_stamp']['mujoco_version']==mujoco.__version__
for key,filename in [('robot','robot.xml'),('scene','scene.xml')]:
    assert result['runtime_stamp']['model_xml_sha'][key]==sha(episode/filename)
output=episode/'replay_clean';output.mkdir()
model=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));data=mujoco.MjData(model)
ffmpeg=Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
width,height=480,320
renderer=mujoco.Renderer(model,height=height,width=width)
full=mujoco.MjvCamera();full.lookat[:]=[.10,-.05,.80];full.distance=2.30;full.azimuth=-115;full.elevation=-12
close=mujoco.MjvCamera();close.lookat[:]=[.35,-.18,.85];close.distance=.65;close.azimuth=-120;close.elevation=-20
indices=np.flatnonzero(trajectory['time']>=34)[::4];fps=12.5
video=output/'grasp.mp4'
log=(output/'ffmpeg.log').open('wb')
command=[str(ffmpeg),'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-r',str(fps),'-i','-',
         '-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
phaseframes={}
for phase in ['CLOSE','TEST_LIFT','LIFT','HOLD']:
    candidates=np.flatnonzero(trajectory['phase'][indices]==phase)
    if len(candidates):phaseframes[int(indices[candidates[len(candidates)//2]])]=phase
try:
    for index in indices:
        data.qpos[:]=trajectory['qpos'][index];data.qvel[:]=trajectory['qvel'][index];mujoco.mj_forward(model,data)
        panels=[]
        for camera,label in [(full,'SONIC body + finger PD'),(close,'Native hand | no ball pads')]:
            renderer.update_scene(data,camera=camera);renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=False
            pixels=renderer.render().copy()
            text=f"{label}\n{trajectory['phase'][index]} | t={trajectory['time'][index]:.2f}s"
            mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100,mujoco.mjtGridPos.mjGRID_TOPLEFT,
                               mujoco.MjrRect(0,0,width,height),text,'',renderer._mjr_context)
            mujoco.mjr_readPixels(pixels,None,mujoco.MjrRect(0,0,width,height),renderer._mjr_context)
            panels.append(np.flipud(pixels).copy())
        canvas=np.concatenate(panels,axis=1);process.stdin.write(canvas.tobytes())
        if int(index) in phaseframes:
            subprocess.run([str(ffmpeg),'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-i','-',
                            '-frames:v','1',str(output/f'frame_{phaseframes[int(index)]}.png')],input=canvas.tobytes(),check=True,timeout=20)
finally:
    process.stdin.close();renderer.close()
assert process.wait(timeout=20)==0
subprocess.run([str(ffmpeg),'-v','error','-nostdin','-threads','1','-i',str(video),'-f','null','-'],check=True,timeout=30)
stamp={'source':str(episode),'source_trajectory_sha':sha(episode/'trajectory.npz'),'source_result_sha':sha(episode/'result.json'),
       'replay_only':True,'physical_steps':0,'frames':len(indices),'fps':fps,
       'source_time_range_s':[float(trajectory['time'][indices[0]]),float(trajectory['time'][indices[-1]])],
       'mujoco_version':mujoco.__version__,'renderer_sha':sha(__file__),'video_sha':sha(video),
       'video_bytes':video.stat().st_size,'decode_verified':True}
(output/'replay.json').write_text(json.dumps(stamp,indent=2));print(json.dumps(stamp,indent=2))
