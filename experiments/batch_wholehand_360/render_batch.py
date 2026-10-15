"""Replay this episode's recorded states. Zero physical integration steps."""
import os,resource
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
os.environ['LP_NUM_THREADS']='2' # graphics workers stay within this job's two-core affinity
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import sys,json,hashlib,subprocess
import numpy as np,mujoco
R=Path(__file__).resolve().parent;episode=R/'out'/sys.argv[1]
assert episode.parent==R/'out'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=json.loads((episode/'result.json').read_text());stamp=result['runtime_stamp']
trajectory=np.load(episode/'trajectory.npz',allow_pickle=False)
assert stamp['mujoco_version']==mujoco.__version__
assert json.loads(str(trajectory['runtime_stamp_json']))==stamp
for key in ['robot','scene']:assert stamp['model_sha'][key]==sha(episode/(key+'.xml'))
suffix=sys.argv[2] if len(sys.argv)>2 else 'replay';assert suffix.replace('_','').isalnum()
output=episode/suffix;output.mkdir()
model=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));data=mujoco.MjData(model)
ffmpeg=Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
width,height=480,320;renderer=mujoco.Renderer(model,height=height,width=width)
full=mujoco.MjvCamera();full.lookat[:]=[.10,-.05,.80];full.distance=2.30;full.azimuth=-115;full.elevation=-12
close=mujoco.MjvCamera();close.lookat[:]=[float(model.body('red_cube').pos[0]),float(model.body('red_cube').pos[1]),.85]
close.distance=.65;close.azimuth=-120;close.elevation=-20
indices=np.arange(0,len(trajectory['time']),8);fps=6.25
video=output/'grasp.mp4';log=(output/'ffmpeg.log').open('wb')
command=[str(ffmpeg),'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-r',str(fps),'-i','-',
         '-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
phaseframes={}
for phase in ['REACH','CLOSE','TEST_LIFT','LIFT','HOLD','PLAN_REFUSED_SAFE_HOLD']:
    candidates=np.flatnonzero(trajectory['phase'][indices]==phase)
    if len(candidates):phaseframes[int(indices[candidates[len(candidates)//2]])]=phase
label='SUCCESS' if result['success'] else ('PLAN REFUSED - NO GRASP' if result['classification']=='planning_refused' else 'FAILURE')
try:
    for index in indices:
        data.qpos[:]=trajectory['qpos'][index];data.qvel[:]=trajectory['qvel'][index];mujoco.mj_forward(model,data)
        panels=[]
        for camera,subtitle in [(full,'SONIC body + finger PD'),(close,'Native hand | no ball pads')]:
            renderer.update_scene(data,camera=camera);renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=False
            pixels=renderer.render().copy()
            text=f"{episode.name} | {label}\n{subtitle}\n{trajectory['phase'][index]} | t={trajectory['time'][index]:.2f}s"
            mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100,mujoco.mjtGridPos.mjGRID_TOPLEFT,
                               mujoco.MjrRect(0,0,width,height),text,'',renderer._mjr_context)
            mujoco.mjr_readPixels(pixels,None,mujoco.MjrRect(0,0,width,height),renderer._mjr_context)
            panels.append(np.flipud(pixels).copy())
        canvas=np.concatenate(panels,axis=1);process.stdin.write(canvas.tobytes())
        if int(index) in phaseframes:
            subprocess.run([str(ffmpeg),'-v','error','-nostdin','-threads','1','-f','rawvideo','-pix_fmt','rgb24','-s','960x320','-i','-',
                            '-frames:v','1',str(output/f'frame_{phaseframes[int(index)]}.png')],input=canvas.tobytes(),check=True,timeout=20)
finally:
    process.stdin.close();renderer.close();log.close()
assert process.wait(timeout=20)==0
subprocess.run([str(ffmpeg),'-v','error','-nostdin','-threads','1','-i',str(video),'-f','null','-'],check=True,timeout=30)
meta={'id':episode.name,'classification':result['classification'],'success':result['success'],'source':str(episode),
      'source_trajectory_sha':sha(episode/'trajectory.npz'),'source_result_sha':sha(episode/'result.json'),
      'replay_only':True,'physical_steps':0,'frames':len(indices),'fps':fps,'width':960,'height':320,
      'duration_s':len(indices)/fps,'source_time_range_s':[float(trajectory['time'][indices[0]]),float(trajectory['time'][indices[-1]])],
      'starts_with_reach':str(trajectory['phase'][0])=='REACH','renderer_sha':sha(__file__),'video_sha':sha(video),
      'mesa_lp_threads':2,'cpu_affinity':sorted(os.sched_getaffinity(0)),
      'video_bytes':video.stat().st_size,'decode_verified':True,'runtime_stamp':stamp}
(output/'replay.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta),flush=True)
