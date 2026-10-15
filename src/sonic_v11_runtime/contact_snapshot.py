"""Inspect and render saved physical frames, never run a new physics episode."""
import json,sys
from pathlib import Path
import mujoco,numpy as np
import sonic_v11 as s
import source_physics_core as core
root=Path(__file__).resolve().parent;out=root/'out'/sys.argv[1];r=json.loads((out/'result.json').read_text());z=np.load(out/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(z['scene']));d=mujoco.MjData(m);cg=m.body('red_cube').id;w=m.body('right_wrist_yaw_link').id
telemetry=out/('telemetry.csv' if (out/'telemetry.csv').exists() else 'telemetry.csv.gz')
rows=np.loadtxt(telemetry,delimiter=',',comments='#');snap=[]
renderer=mujoco.Renderer(m,height=640,width=800)
ff='/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'
for phase in ['DESCEND','ALIGN','CLOSE']:
 ix=np.flatnonzero(z['phase']==phase)
 if not len(ix):continue
 k=int(ix[-1]);d.qpos[:]=z['qpos'][k];d.qvel[:]=z['qvel'][k];mujoco.mj_forward(m,d)
 pads=np.array([d.geom_xpos[m.geom(n).id].copy() for n in core.PADS]);center=d.xpos[cg].copy();a,b=pads[:2];v=b-a;u=float((center-a)@v/(v@v));perp=float(np.linalg.norm(center-(a+u*v)))
 hand=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[hand];ar=m.jnt_qposadr[m.actuator_trnid[22:29,0]]
 ti=np.argmin(abs(rows[:,0]-z['time'][k]));q=d.qpos[hq].copy()
 snap.append(dict(phase=phase,time=float(z['time'][k]),cube=center.tolist(),pads=pads.tolist(),hand_q=q.tolist(),arm_q=d.qpos[ar].tolist(),
                  thumb_index_pad_center_distance_m=float(np.linalg.norm(v)),cube_line_projection=u,cube_perp_to_pad_line_m=perp,
                  saved_finger_forces_N=rows[ti,7:10].tolist(),saved_support_force_N=float(rows[ti,10])))
 cam=mujoco.MjvCamera();cam.lookat[:]=center;cam.distance=.40;cam.azimuth=-125;cam.elevation=-15
 renderer.update_scene(d,camera=cam);pixels=renderer.render().copy()
 import subprocess
 imagepath=out/('snapshot_'+phase+'.png');assert not imagepath.exists()
 subprocess.run([ff,'-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','800x640','-i','-','-frames:v','1',str(imagepath)],input=pixels.tobytes(),check=True,timeout=20)
renderer.close();result=dict(physical_episodes_added=0,source_trajectory_sha=s.sha(out/'trajectory.npz'),result_sha=s.sha(out/'result.json'),
                           runtime_stamp=r['runtime_stamp'],snapshots=snap)
p=out/'contact-snapshots.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(snap,indent=2))
