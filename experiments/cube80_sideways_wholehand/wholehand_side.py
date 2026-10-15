"""Bounded whole-hand geometry search and dynamic SONIC-side-grasp experiment.

ARDY provides a source arm prior; geometry correction is explicitly separate.
FK search changes scratch data only. During physics only actuator controls are
written: body torques from SONIC, independently commanded finger torques.
"""
import os,sys,resource
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'lib'))
sys.path.insert(0,str(ROOT/'plandeps310'))
import argparse,json,time,hashlib,xml.etree.ElementTree as ET
from functools import lru_cache
import numpy as np,mujoco
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
import sonic_v11 as sonic
from motion_input import ArdyMotion

PADS=['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(out,edge,xy,mass):
    src=ROOT/'lib/src/g1'
    robot=ET.parse(src/'g1_29dof_with_hand.xml');robot.find('compiler').set('meshdir',str(src/'meshes'))
    armed=[]
    for body in robot.iter('body'):
        name=body.get('name','')
        if name.startswith(('right_hand_','left_hand_')):
            for i,g in enumerate(body.findall('geom')):
                # Use original non-visual physical geometry, not duplicated meshes.
                active=g.get('group')!='1'
                g.set('contype','2' if active else '0');g.set('conaffinity','3' if active else '0')
                if active:
                    if not g.get('name'):g.set('name',name+'_collision_'+str(i))
                    armed.append(dict(body=name,geom=g.get('name'),type=g.get('type','sphere')))
    robot.write(out/'robot.xml',encoding='utf8')
    scene=ET.parse(src/'scene_grasp_hand.xml');scene.find('include').set('file','robot.xml')
    world=scene.find('worldbody');world.remove(world.find("body[@name='cube_pedestal']"))
    world.find("body[@name='grasp_table']/geom[@name='table_top']").set('pos','0.66 0 0.700')
    for g in world.findall('.//geom'):g.set('conaffinity','3')
    block=world.find("body[@name='red_cube']");block.set('pos',f'{xy[0]} {xy[1]} {.725+edge/2}')
    g=block.find('geom');g.set('size',' '.join([str(edge/2)]*3));g.set('mass',str(mass));g.set('contype','1')
    eq=scene.find('equality')
    if eq is not None:scene.getroot().remove(eq)
    scene.write(out/'scene.xml',encoding='utf8')
    m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m)
    bodyids=m.actuator_trnid[:29,0];bodyq=m.jnt_qposadr[bodyids]
    handids=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[handids]
    d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[bodyq]=sonic.DEFAULT_ANGLES
    d.qpos[hq]=[0,-.7,-1.5,.5,.5,.5,.5]
    mujoco.mj_forward(m,d)
    assert m.nq==57 and m.nu==43 and m.neq==0
    return m,d,bodyq,handids,hq,armed
def setup(m,d,bq,hj,hq):
    aq=bq[22:29];av=m.jnt_dofadr[m.actuator_trnid[22:29,0]];hv=m.jnt_dofadr[hj]
    joints=np.r_[m.actuator_trnid[22:29,0],hj]
    limits=m.jnt_range[joints];qidx=np.r_[aq,hq]
    pads=np.array([m.geom(n).id for n in PADS]);cube=m.geom('red_cube_geom').id;table=m.geom('table_top').id
    bones=np.array([i for i in range(m.ngeom) if m.body(int(m.geom_bodyid[i])).name.startswith('right_hand_')
                    and m.geom_contype[i] and i not in pads])
    assert len(bones)==7 and len(pads)==3
    assert all(m.geom_type[g]==mujoco.mjtGeom.mjGEOM_SPHERE and m.geom_size[g,0]==.01 for g in pads)
    return aq,av,hv,limits,qidx,pads,cube,table,bones
def clearances(m,d,bones,cube,table):
    # mesh-vs-table mj_geomDistance is UNVERIFIED on MuJoCo3.2.7.
    # For this horizontal table use exact transformed vertices and a conservative
    # vertical half-space, rather than its known negative-distance hull artifact.
    v=np.array([[separating_gap(m,d,int(g),int(cube)),
                 float(vertices(m,d,int(g))[:,2].min()-(d.geom_xpos[table,2]+m.geom_size[table,2]))]
                for g in bones])
    return v
@lru_cache(maxsize=256)
def local_vertices(m,g):
    typ=m.geom_type[g]
    if typ==mujoco.mjtGeom.mjGEOM_MESH:
        mid=m.geom_dataid[g];a=m.mesh_vertadr[mid];n=m.mesh_vertnum[mid]
        return m.mesh_vert[a:a+n].astype(float)
    if typ==mujoco.mjtGeom.mjGEOM_BOX:
        return np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])*m.geom_size[g]
    raise ValueError('Expected physical mesh or box')
def vertices(m,d,g):return local_vertices(m,g)@d.geom_xmat[g].reshape(3,3).T+d.geom_xpos[g]
@lru_cache(maxsize=256)
def hull_axes(m,g):
    v=local_vertices(m,g);h=ConvexHull(v)
    edges=set()
    for face in h.simplices:
        for a,b in [(face[0],face[1]),(face[1],face[2]),(face[2],face[0])]:edges.add(tuple(sorted([int(a),int(b)])))
    e=np.array([v[b]-v[a] for a,b in edges]);e/=np.linalg.norm(e,axis=1)[:,None]
    return v[h.vertices],np.unique(np.round(h.equations[:,:3],6),axis=0),np.unique(np.round(e,6),axis=0)
def separating_gap(m,d,g,box):
    """Complete convex hull/OBB SAT signed support gap (not Euclidean distance).

    Positive = a proven separation lower bound; negative = intersecting convex
    hulls. Includes edge-cross axes. Independent of mj_geomDistance.
    """
    v,n,e=hull_axes(m,g);R=d.geom_xmat[g].reshape(3,3);B=d.geom_xmat[box].reshape(3,3)
    v=v@R.T+d.geom_xpos[g];n=n@R.T;e=e@R.T
    cross=np.cross(e[:,None,:],B.T[None,:,:]).reshape(-1,3)
    norms=np.linalg.norm(cross,axis=1);cross=cross[norms>1e-7]/norms[norms>1e-7,None]
    axes=np.r_[B.T,n,cross]
    projection=v@axes.T;bc=d.geom_xpos[box]@axes.T;br=np.abs(axes@B)@m.geom_size[box]
    return float(np.maximum(projection.min(axis=0)-(bc+br),(bc-br)-projection.max(axis=0)).max())
def contact_summary(m,d,pads,cube,bones):
    forces=np.zeros(3);other=0.;table=0.;depth=0.;contacts=[]
    for i in range(d.ncon):
        c=d.contact[i]
        if cube not in [c.geom1,c.geom2]:continue
        gid=c.geom2 if c.geom1==cube else c.geom1
        f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f);force=max(0.,float(f[0]));depth=min(depth,float(c.dist))
        body=m.body(int(m.geom_bodyid[gid])).name
        if gid in pads:forces[np.where(pads==gid)[0][0]]+=force
        elif body.startswith('right_hand_'):other+=force
        elif body in ['grasp_table','cube_pedestal','world']:table+=force
        contacts.append(dict(geom=m.geom(gid).name,body=body,normal_N=force,dist_m=float(c.dist)))
    return forces,other,table,depth,contacts
def plan(args,out,m,d,bq,hj,hq,armed):
    aq,av,hv,lim,idx,pads,cube,table,bones=setup(m,d,bq,hj,hq)
    motion=ArdyMotion(ROOT/'lib/src/original_motions/near_s42.npz')
    # Select a real generated arm prior; finite bounds are solver constraints,
    # not execution-time clipping of a claimed native ARDY trajectory.
    frame=min(150,len(motion.qpos)-1);prior=motion.qpos[frame,29:36].copy()
    cube_pos=d.xpos[m.body('red_cube').id].copy();edge=args.edge
    rows=[];seeds=[]
    arms=[prior,np.array([-1.1,-.8,-1.7,1.5,-1.5,1.2,.3]),np.array([-.7,-.4,.7,1.2,0.,.5,0.])]
    for arm in arms:
        for fingers in [[0,-.5,-1.,.8,.6,.8,.6],[.8,-.4,-.8,.4,1.2,.4,1.2],[-.8,-.4,-.8,1.4,.2,1.4,.2]]:
            seeds.append(np.r_[arm,fingers])
    best=None
    for axis in [0,1]:
      targets=np.tile(cube_pos,(3,1));targets[:,axis]+=[-(edge/2+.01+args.gap),edge/2+.01+args.gap,edge/2+.01+args.gap]
      # Two opposing fingers are anatomically 57mm apart along palm-local Z.
      # Earlier +/-0.22*edge gave an impossible 26.4mm separation at edge60.
      targets[1,(axis+1)%2]+=.0285;targets[2,(axis+1)%2]-=.0285
      for si,seed in enumerate(seeds[:args.seeds]):
        x0=np.minimum(np.maximum(seed,lim[:,0]+.005),lim[:,1]-.005)
        def residual(x):
            d.qpos[idx]=x;mujoco.mj_forward(m,d)
            gaps=clearances(m,d,bones,cube,table)
            # side grasp: thumb opposite index+middle, table clear at terminal.
            return np.r_[((d.geom_xpos[pads]-targets)*1000).ravel(),
                          np.maximum(.001-gaps,0.).ravel()*1000,
                          (x[:7]-prior)*.15]
        def pad_residual(x):
            d.qpos[idx]=x;mujoco.mj_forward(m,d)
            return np.r_[((d.geom_xpos[pads]-targets)*1000).ravel(),(x[:7]-prior)*.01]
        rough=least_squares(pad_residual,x0,bounds=(lim[:,0]+.003,lim[:,1]-.003),max_nfev=250,diff_step=1e-5)
        x0=rough.x
        fit=least_squares(residual,x0,bounds=(lim[:,0]+.003,lim[:,1]-.003),max_nfev=400,ftol=1e-8,xtol=1e-8,gtol=1e-8,diff_step=1e-3)
        residual(fit.x);gaps=clearances(m,d,bones,cube,table);error=float(np.max(np.linalg.norm(d.geom_xpos[pads]-targets,axis=1)))
        record=dict(axis=axis,seed=si,pad_error_m=error,pad_errors_m=np.linalg.norm(d.geom_xpos[pads]-targets,axis=1).tolist(),
                    pad_positions=d.geom_xpos[pads].tolist(),targets=targets.tolist(),min_bone_cube_gap_m=float(gaps[:,0].min()),min_bone_table_gap_m=float(gaps[:,1].min()),q=fit.x.tolist(),nfev=fit.nfev)
        rows.append(record);print(json.dumps(record),flush=True)
        score=error+max(0.,.001-gaps.min())*4
        if best is None or score<best[0]:best=(score,record.copy())
    r=best[1];d.qpos[idx]=r['q'];mujoco.mj_forward(m,d)
    # Opening occurs in the air. Retraction from closed terminal must avoid
    # sweeping the real finger links into the object, independently screened.
    openhand=np.array(r['q'][7:]);openhand[2]-=.30;openhand[3:]-=.35
    openhand=np.minimum(np.maximum(openhand,lim[7:,0]+.003),lim[7:,1]-.003)
    wrist=m.body('right_wrist_yaw_link').id
    result=dict(best=r,candidates=rows,open_hand=openhand.tolist(),closed_hand=r['q'][7:],arm=r['q'][:7],
      wrist_pos=d.xpos[wrist].tolist(),wrist_R=d.xmat[wrist].reshape(3,3).tolist(),
      cube_pos=cube_pos.tolist(),edge_m=edge,pad_gap_m=args.gap,mass_kg=args.mass,hand_geoms=armed,
      ardy_source=motion.audit,ardy_frame=frame,scope='ARDY seven-arm prior + bounded geometry correction, NOT native fullbody ARDY',
      geometry_pass=bool(r['pad_error_m']<.003 and min(r['min_bone_cube_gap_m'],r['min_bone_table_gap_m'])>=0),
      geometry_metric='full convex hull/OBB SAT support gap to cube; conservative transformed-vertex/table-top halfspace; mj_geomDistance excluded after contradictory no-contact result',
      runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
        model_sha={'robot':sha(out/'robot.xml'),'scene':sha(out/'scene.xml')},scene_generator_sha=sha(__file__),library_sha={'ardy_npz':motion.audit['source_npz_sha256'],'sonic_v11':sha(sonic.__file__)},dt=float(m.opt.timestep)),
      hand_self_collision='all original nonvisual finger geometry masks2/3; hand-world and nonadjacent inter-finger collisions enabled; MuJoCo parent-body exclusions remain',
      synthetic_pads='three inherited 10mm spherical pads retained and disclosed; finger bones NOT ghosts')
    (out/'plan.json').write_text(json.dumps(result,indent=2));print('PLAN',json.dumps(dict(geometry_pass=result['geometry_pass'],best=r)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['plan']);p.add_argument('--name',required=True);p.add_argument('--edge',type=float,default=.06);p.add_argument('--mass',type=float,default=.12);p.add_argument('--seeds',type=int,default=3);p.add_argument('--gap',type=float,default=-.0005)
    a=p.parse_args();assert .025<=a.edge<=.08 and .02<=a.mass<=.2 and 1<=a.seeds<=9 and -.002<=a.gap<=.02
    out=ROOT/'out'/a.name;out.mkdir();m,d,bq,hj,hq,armed=build(out,a.edge,[.35,-.18],a.mass)
    plan(a,out,m,d,bq,hj,hq,armed)
