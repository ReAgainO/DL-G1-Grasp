"""Observation-only cube contact recorder. Never changes simulation state.

MuJoCo contact frame axes are rows; its wrench acts on geom2. Store raw
contact data as well as signed world force and moment about the cube COM.
No mj_forward/mj_step is called here. Values after mj_step belong to the
solver stage before integration; both solver-stage and advanced times are saved.
"""
import gzip,json
from pathlib import Path
import numpy as np

CATEGORIES=('pad','wrist','other_robot','support','other')
RAW_COLUMNS=['time_s','solver_time_s','step','contact_id','geom1','geom2','other_geom','other_body','category','efc_address','distance_m','condim']+['contact_'+a+'_m' for a in 'xyz']+['frame_'+str(i) for i in range(9)]+['contact_'+a for a in ('fn_N','ft1_N','ft2_N','tn_Nm','tt1_Nm','tt2_Nm')]+['cube_force_'+a+'_N' for a in 'xyz']+['cube_moment_com_'+a+'_Nm' for a in 'xyz']+['cube_com_'+a+'_m' for a in 'xyz']+['cube_rotation_'+str(i) for i in range(9)]
STEP_COLUMNS=['time_s','solver_time_s','phase_id']+[c+'_'+a for c in CATEGORIES for a in ('normal_N','world_fx_N','world_fy_N','world_fz_N')]

def cube_wrench(frame,wrench,position,cube_com,cube_is_geom2):
    frame=np.asarray(frame).reshape(3,3);wrench=np.asarray(wrench)
    sign=1. if cube_is_geom2 else -1.
    force=sign*(frame.T@wrench[:3])
    moment=sign*(frame.T@wrench[3:])+np.cross(np.asarray(position)-cube_com,force)
    return force,moment

def classify(geom,body,pads,support,robot_bodies,body_names):
    if geom in pads:return 0
    if body in robot_bodies:return 1 if 'wrist' in body_names[body] else 2
    if geom in support:return 3
    return 4

def fingertip_only_gate(hold_loads):
    return bool(len(hold_loads) and not (hold_loads[:,1:3,0].sum(axis=1)>.001).any())

class ContactAudit:
    def __init__(self,model,cube_body,cube_geom,pads,support,out,stamp):
        self.model=model;self.cube=cube_body;self.cg=cube_geom
        self.pads=set(pads);self.support=set(support);self.out=Path(out)
        self.stamp=stamp;self.body_names=[model.body(i).name or '' for i in range(model.nbody)]
        pelvis=model.body('pelvis').id;self.robot_bodies={pelvis}
        for i in range(1,model.nbody):
            if int(model.body_parentid[i]) in self.robot_bodies:self.robot_bodies.add(i)
        self.metadata={str(i):dict(name=model.geom(i).name or '',body=int(model.geom_bodyid[i]),body_name=self.body_names[int(model.geom_bodyid[i])],category=CATEGORIES[classify(i,int(model.geom_bodyid[i]),self.pads,self.support,self.robot_bodies,self.body_names)]) for i in range(model.ngeom) if i!=cube_geom}
        self.file=gzip.open(self.out/'cube_contacts.csv.gz','wt')
        self.file.write('# runtime_stamp='+json.dumps(stamp)+'\n# '+','.join(RAW_COLUMNS)+'\n')
        self.steps=[];self.phases={};self.raw_contacts=0;self.by_geom={};self.totals=None

    def begin(self,data,phase,step):
        assert step<45000 and data.ncon<=128,('Contact audit hard bound exceeded',step,data.ncon)
        self.step=step;self.time=float(data.time);self.solver_time=self.time-float(self.model.opt.timestep)
        self.phase=self.phases.setdefault(phase,len(self.phases));self.totals=np.zeros((5,4))
        self.com=data.xipos[self.cube].copy();self.rot=data.xmat[self.cube].copy()

    def record(self,contact,k,wrench):
        other=int(contact.geom1 if contact.geom2==self.cg else contact.geom2)
        body=int(self.model.geom_bodyid[other]);category=classify(other,body,self.pads,self.support,self.robot_bodies,self.body_names)
        force,moment=cube_wrench(contact.frame,wrench,contact.pos,self.com,contact.geom2==self.cg)
        normal=max(0.,float(wrench[0]));self.totals[category]+=np.r_[normal,force]
        row=np.r_[self.time,self.solver_time,self.step,k,contact.geom1,contact.geom2,other,body,category,contact.efc_address,contact.dist,contact.dim,contact.pos,contact.frame,wrench,force,moment,self.com,self.rot]
        assert len(row)==len(RAW_COLUMNS)
        self.file.write(','.join(format(float(v),'.12g') for v in row)+'\n');self.raw_contacts+=1
        counts=self.by_geom.setdefault(str(other),dict(contact_rows=0,loaded_rows=0,max_normal_N=0.))
        counts['contact_rows']+=1;counts['loaded_rows']+=int(normal>.001);counts['max_normal_N']=max(counts['max_normal_N'],normal)

    def end(self):
        self.steps.append(np.r_[self.time,self.solver_time,self.phase,self.totals.ravel()])

    def finish(self,hold_start,hold_end):
        self.file.close();steps=np.asarray(self.steps)
        assert len(steps)>0 and steps.shape[1]==len(STEP_COLUMNS)
        with gzip.open(self.out/'cube_contact_steps.csv.gz','wt') as f:
            f.write('# runtime_stamp='+json.dumps(self.stamp)+'\n# '+','.join(STEP_COLUMNS)+'\n')
            np.savetxt(f,steps,delimiter=',',fmt='%.12g')
        hold=(steps[:,0]>(hold_start if hold_start is not None else 1e9)+.02)&(steps[:,0]<=(hold_end if hold_end is not None else -1))
        loads=steps[:,3:].reshape(-1,5,4);h=loads[hold]
        def stats(values):
            return {c:dict(max_normal_N=float(values[:,i,0].max()),loaded_steps=int((values[:,i,0]>.001).sum()),max_upward_force_N=float(values[:,i,3].max()),min_vertical_force_N=float(values[:,i,3].min())) for i,c in enumerate(CATEGORIES)} if len(values) else {}
        result=dict(schema_version=1,runtime_stamp=self.stamp,physics_steps=len(steps),raw_contact_rows=self.raw_contacts,
                    all_steps=stats(loads),hold_steps=stats(h),hold_sample_count=int(hold.sum()),
                    fingertip_only_robot_contacts_in_hold=fingertip_only_gate(h),forbidden_robot_normal_threshold_N=.001,
                    threshold_definition='sum of wrist and other non-whitelisted robot normal forces per solver step',
                    raw_columns=RAW_COLUMNS,step_columns=STEP_COLUMNS,category_ids={i:c for i,c in enumerate(CATEGORIES)},phase_ids=self.phases,
                    geom_metadata=self.metadata,geom_contact_counts=self.by_geom,
                    force_convention='contact frame rows; positive wrench on geom2; signed cube-world force and contact moment about xipos COM',
                    timestamp_convention='time_s advanced by mj_step; solver_time_s=time_s-dt for preintegration contact/xipos/xmat values',
                    state_mutations=False,raw_path='cube_contacts.csv.gz',step_path='cube_contact_steps.csv.gz')
        (self.out/'contact-audit.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
