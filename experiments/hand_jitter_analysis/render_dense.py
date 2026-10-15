"""25fps replay of real200Hz recorded states; no synthetic smoothing/integration."""
import os,resource
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
os.environ['LP_NUM_THREADS']='2'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess
import numpy as np,mujoco
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float,default=53)
a=p.parse_args();assert a.episode.replace('_','').isalnum()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
episode=R/'out'/a.episode
result=json.loads((episode/'result.json').read_text());stamp=result['runtime_stamp']
trace=np.load(episode/'dense_trace.npz',allow_pickle=False)
assert json.loads(str(trace['runtime_stamp_json']))==stamp
assert stamp['mujoco_version']==mujoco.__version__=='3.2.7'
for k in ['robot','scene']:assert sha(episode/(k+'.xml'))==stamp['model_sha'][k]
times=trace['time'];assert np.allclose(np.diff(times),.005,rtol=0,atol=1e-12)
indices=np.flatnonzero((times>=a.start)&(times<a.end))[::8];fps=25
assert len(indices)>0
output=episode/'replay25';output.mkdir()
model=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));data=mujoco.MjData(model)
assert model.neq==0 and model.nmocap==0
renderer=mujoco.Renderer(model,height=360,width=480)
full=mujoco.MjvCamera();full.lookat[:]=[.10,-.05,.80];full.distance=2.30;full.azimuth=-115;full.elevation=-12
close=mujoco.MjvCamera();close.lookat[:]=[float(model.body('red_cube').pos[0]),float(model.body('red_cube').pos[1]),.86]
close.distance=.55;close.azimuth=-120;close.elevation=-20
ff='/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'
video=output/'grasp-25fps.mp4'
command=[ff,'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x360','-r',str(fps),'-i','-',
         '-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
phaseframes={}
for phase in ['REACH','CLOSE','TEST_LIFT','LIFT','HOLD']:
    ix=np.flatnonzero(trace['phase'][indices]==phase)
    if len(ix):phaseframes[int(indices[ix[len(ix)//2]])]=phase
log=(output/'ffmpeg.log').open('xb');process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
try:
    for index in indices:
        data.qpos[:]=trace['qpos'][index];data.qvel[:]=trace['qvel'][index];mujoco.mj_forward(model,data)
        panels=[]
        for camera,subtitle in [(full,'SONIC body + independent finger PD'),(close,'Native whole hand | actual states')]:
            renderer.update_scene(data,camera=camera);renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=False
            pixels=renderer.render().copy()
            label='SUCCESS' if result['success'] else 'FAILURE'
            message=f"{a.episode} | {label} | 25fps\n{subtitle}\n{trace['phase'][index]} | t={times[index]:.2f}s"
            mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100,mujoco.mjtGridPos.mjGRID_TOPLEFT,
                               mujoco.MjrRect(0,0,480,360),message,'',renderer._mjr_context)
            mujoco.mjr_readPixels(pixels,None,mujoco.MjrRect(0,0,480,360),renderer._mjr_context)
            panels.append(np.flipud(pixels).copy())
        canvas=np.concatenate(panels,axis=1);process.stdin.write(canvas.tobytes())
        if int(index) in phaseframes:
            subprocess.run([ff,'-v','error','-nostdin','-threads','1','-f','rawvideo','-pix_fmt','rgb24','-s','960x360','-i','-',
                            '-frames:v','1',str(output/('frame_'+phaseframes[int(index)]+'.png'))],input=canvas.tobytes(),check=True,timeout=20)
        if int(index)%400==0:print(f'frame t={times[index]:.2f}',flush=True)
finally:
    process.stdin.close();renderer.close();log.close()
assert process.wait(timeout=20)==0
progress=output/'decode-progress.txt'
subprocess.run([ff,'-v','error','-nostdin','-threads','1','-i',str(video),'-progress',str(progress),'-f','null','-'],check=True,timeout=60)
decoded={line.split('=',1)[0]:line.split('=',1)[1] for line in progress.read_text().splitlines() if '=' in line}
assert int(decoded['frame'])==len(indices) and decoded['progress']=='end'
meta={'id':a.episode,'success':result['success'],'source_dense_sha':sha(episode/'dense_trace.npz'),
      'source_result_sha':sha(episode/'result.json'),'replay_only':True,'physical_steps':0,'interpolation':False,
      'frames':len(indices),'fps':fps,'duration_s':len(indices)/fps,'source_time_range_s':[float(times[indices[0]]),float(times[indices[-1]])],
      'video_sha':sha(video),'video_bytes':video.stat().st_size,'width':960,'height':360,
      'decode_verified':True,'decoded_frames':int(decoded['frame']),'renderer_sha':sha(__file__),'runtime_stamp':stamp}
with (output/'replay.json').open('x') as f:json.dump(meta,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' Dense true-state replay '+json.dumps(meta)+'\n')
print(json.dumps({k:meta[k] for k in ['id','success','frames','fps','duration_s','video_sha','decode_verified']}),flush=True)
