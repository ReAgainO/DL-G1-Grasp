"""Own-task frozen source/trajectory verification and operation receipt."""
from pathlib import Path
import json,hashlib,datetime,subprocess,os
import numpy as np,mujoco
D=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
S=D/'source-snapshots';S.mkdir(exist_ok=True)
for name in ['wholehand_side.py','execute_side.py','run_record.py','render_replay.py','audit_episode.py','GATES-v2.md']:
 p=D/name;dest=S/(sha(p)+'-'+name)
 if not dest.exists():dest.write_bytes(p.read_bytes())
A=D/'out/side80_native3';C=D/'out/side80_native3_repeat';N=D/'out/side80_native_negative3'
a=json.loads((A/'result.json').read_text());c=json.loads((C/'result.json').read_text());n=json.loads((N/'result.json').read_text())
with np.load(A/'trajectory.npz',allow_pickle=False) as x,np.load(C/'trajectory.npz',allow_pickle=False) as y:
 equal={k:bool(np.array_equal(x[k],y[k])) for k in x.files}
 assert all(equal.values())
m=mujoco.MjModel.from_xml_path(str(A/'scene.xml'))
hand=[]
for g in range(m.ngeom):
 b=m.body(int(m.geom_bodyid[g])).name
 if b.startswith(('right_hand_','left_hand_','right_wrist_yaw_link')):
  hand.append({'id':g,'body':b,'geom':m.geom(g).name,'type':int(m.geom_type[g]),'group':int(m.geom_group[g]),'mask':[int(m.geom_contype[g]),int(m.geom_conaffinity[g])]})
bones=[g for g in hand if g['body'].startswith('right_hand_') and g['mask'][0] and g['geom'] not in ['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']]
pads=[g for g in hand if g['geom'] in ['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']]
assert len(bones)==7 and len(pads)==3 and all(g['mask']==[0,0] for g in pads)
assert m.neq==0 and m.nu==43
assert a['runtime_stamp']['source_sha']==sha(D/'execute_side.py')==c['runtime_stamp']['source_sha']==n['runtime_stamp']['source_sha']
assert a['runtime_stamp']['model_xml_sha']==c['runtime_stamp']['model_xml_sha']==n['runtime_stamp']['model_xml_sha']
assert a['success'] and c['success'] and not n['success'] and n['hold_safe_steps']==0
assert a['sonic']['decoded_target_adapter_used'] is False
# Build a replay model from the full recorded recipe; explicitly reconstructed,
# not falsely described as captured directly at integration time.
m.opt.timestep=a['runtime_stamp']['dt'];m.opt.impratio=a['runtime_stamp']['impratio']
for g in range(m.ngeom):
 b=m.body(int(m.geom_bodyid[g])).name
 if g==m.geom('red_cube_geom').id or (b.startswith(('right_hand_','right_wrist_','right_elbow','right_shoulder')) and m.geom_contype[g]):
  m.geom_margin[g]=.001;m.geom_solref[g,:2]=[.02,1]
m.dof_armature[m.jnt_dofadr[m.actuator_trnid[36:43,0]]]=.1
runtime_sha=hashlib.sha256(m.geom_contype.tobytes()+m.geom_conaffinity.tobytes()+m.geom_margin.tobytes()+m.geom_solref.tobytes()+m.dof_armature.tobytes()).hexdigest()
assert runtime_sha==a['runtime_stamp']['in_memory_geometry_sha']
mujoco.mj_saveModel(m,str(A/'reconstructed_runtime.mjb'))
verification={'timestamp':datetime.datetime.now().astimezone().isoformat(),'bitwise_repeat_arrays':equal,
 'frozen_source_and_model_pairing':True,'right_bones_count':len(bones),'right_spherical_pads_physical':0,'hand_geom_manifest':hand,
 'runtime_reconstruction_fingerprint_matches':True,'runtime_reconstruction_sha':runtime_sha,'runtime_mjb_sha':sha(A/'reconstructed_runtime.mjb'),
 'cases':{D0.name:{'success':r['success'],'max_lift_m':r['max_lift_m'],'max_wristlocal_slip_alllift_m':r['max_wristlocal_slip_alllift_m'],
 'hold_safe_steps':r['hold_safe_steps'],'source_sha':r['runtime_stamp']['source_sha'],'result_sha':sha(D0/'result.json'),'trajectory_sha':sha(D0/'trajectory.npz')} for D0,r in [(A,a),(C,c),(N,n)]}}
(D/'verification.json').write_text(json.dumps(verification,indent=2));print(json.dumps(verification,indent=2))
steps=B/'logs'/D.name/'steps.md'
receipt='''
## [03] Physics, comparison, scope and failure receipts
- Nine updated peer report copies matched server SHA256 9/9. Local Luna summaries distinguish report statements from raw prior audit and this task tests.
- Geometry searches plan4/5/6 rejected; corrected impossible 26.4mm opposing-finger target to actual57mm separation; cube increased80mm120g on725mm tabletop, removed original pedestal, table edge shifted310mm. No peer files modified.
- mj_geomDistance cube claimed -2.425mm while actual collision list empty and thumb convex vertices all x<cube left face. SAT full convex-hull/OBB + transformed-vertex tabletop diagnostics replace this metric. All earlier failed candidates retained.
- side80_open7 SAT independently checked min cube gap8.238mm/table25.540mm; path reference no penetrating contact at20ms samples. side80_open8 SAT geometry passes, best pad error2.007micrometres/gap0.997mm.
- Path1 reference speed3.598rad/s refused for physics; global2x time scaling gives1.799rad/s, unchanged joint path. Path check remains reference, not actual trajectory guarantee.
- Physics1:111.53mm lift,2.5s loaded hold; original world-vector slip29.19mm leads success=false. Independent FK shows wristlocal3.50mm; old result untouched. Physics2 wrist feedback104.44mm/local3.41mm, same old world criterion false. Matched first negative7.17mm transient lift and0loaded hold.
- GATES-v2.md saved/uploaded BEFORE native trials; transforms cube-minus-wrist into wrist local coordinates, same10mm threshold, adds opposing physical finger-chain loads/each-foot support/no robot-table rest. It is not S1000 v5/v6 and not comparable pooled success rate.
- Native3 closes with only original7 right phalanx collision bodies+physical palm/wrist. Inherited synthetic3 spheres masks0/0 and invisible. Native3/repeat108.574mm/local3.839mm/HOLD2.5s,2500/2500 support; no equality/object actuator/state override/xfrc/qfrc. Matched native negative1.464mm/0support.
- Important residual: actual early cube contact remains35.389s, preclose peak10.045N; no clean all-path claim. ARDY clip is source posture prior (frame99 of100 at25Hz), not full time-varying ARDY root/body reference. Other body references neutral, SONIC controls43motor plant29body+independent14fingers.
- Render-only first osmesa probe failed AttributeError: NoneType object has no attribute glGetError; fixed by read-only lib path from220500 task, no shared env upgrade. Render actual recorded states, zero integrations.
- Remote lookup failures retained: guessed S/out/.../trajectory.npz absent (actual replay dir onlyimages/video); guessed S/lib/sonic_v11.py absent (source atS root); guessed fullhand2/fp51_ruler.py absent (actual ardygen4/src). No mutation from lookups.
- Local apply_patch first v2 attempt failed context verification, no files changed, retried matching actual line.
- Resource exception: while two2core physics runs active, a2.9s render-import probe+readonly replay audit used CPU84 (temporarily fifth distinct allowed core), outside declaredmax4; no GPU. Subsequent tasks all restricted80-83 and max2 concurrent jobs. Exception disclosed, not hidden as full budget compliance.
- Assets in /data; /home4.4GiB and /data11TiB checked. Own 1MiB probe retained. Wrong interpreter-target scipy311 retained unused, correct own-target310 dependency installed; shared env unchanged.
- Source snapshots current frozen successful source saved; earlier preliminary source revisions were overwritten before snapshot mechanism, so original full source reconstruction for those preliminary hashes not archived. They are not selected release.
'''
with steps.open('a') as f:f.write(receipt+'\nIndependent repeat/model verification: '+json.dumps({k:v for k,v in verification.items() if k!='hand_geom_manifest'})+'\n')
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE']:env.pop(k,None)
q=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),D.name,'note','-',
 'Own whole-hand side-grasp native collision milestone: no synthetic pads, free base+free cube, SONIC29body decoded outputs and fingerPD;80mm120g lift108.574mm/local-slip3.839mm/HOLD2.5s. Same frozen repeat bitwise14/14 arrays, matched no-grip1.464mm/0hold. wholehand-v2 gate is new coordinate-corrected scope, not S1000/H1b pooled result. Still early preclose contact10.045N, ARDY posture prior+referenceIK not native fullbody. All evidence own data task.'],env=env,text=True,capture_output=True)
print(q.stdout,q.stderr);assert q.returncode==0
