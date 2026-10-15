"""Read-only robot/environment support audit, independent of cube contacts."""
import csv,gzip,json
import numpy as np,mujoco

class BalanceAudit:
    def __init__(self,model,supportids,stamp,out):
        self.m=model;self.support=set(supportids);self.stamp=stamp;self.out=out;self.rows=[];self.contacts=[]
        self.robot={model.body('pelvis').id}
        for i in range(1,model.nbody):
            if int(model.body_parentid[i]) in self.robot:self.robot.add(i)
        self.names=[model.body(i).name or '' for i in range(model.nbody)]

    def category(self,g1,g2):
        b1,b2=map(int,self.m.geom_bodyid[[g1,g2]])
        if b1 in self.robot and g2 in self.support:body,support=b1,g2
        elif b2 in self.robot and g1 in self.support:body,support=b2,g1
        else:return None
        if self.m.geom(support).name!='floor':return 0
        if self.names[body]=='left_ankle_roll_link':return 1
        if self.names[body]=='right_ankle_roll_link':return 2
        return 3

    def step(self,data,phase='UNSET'):
        assert len(self.rows)<65000 and data.ncon<=128
        loads=np.zeros(4)
        for k in range(data.ncon):
            c=data.contact[k];category=self.category(c.geom1,c.geom2)
            if category is not None:
                force=np.zeros(6);mujoco.mj_contactForce(self.m,data,k,force);loads[category]+=max(0.,force[0])
                if category in [0,3]:
                    assert len(self.contacts)<1440000,'Bounded robot-support contact log exhausted'
                    robot_geom=int(c.geom1) if int(self.m.geom_bodyid[c.geom1]) in self.robot else int(c.geom2)
                    support_geom=int(c.geom2) if robot_geom==c.geom1 else int(c.geom1)
                    self.contacts.append([float(data.time),float(data.time-self.m.opt.timestep),str(phase),k,robot_geom,self.m.geom(robot_geom).name or '<unnamed>',support_geom,self.m.geom(support_geom).name or '<unnamed>',self.names[int(self.m.geom_bodyid[robot_geom])],category,float(c.dist),*force.tolist()])
        self.rows.append(np.r_[data.time,data.time-self.m.opt.timestep,loads])

    def finish(self,start,end):
        rows=np.asarray(self.rows);h=rows[(rows[:,0]>(start if start is not None else 1e9)+.02)&(rows[:,0]<=(end if end is not None else -1))]
        result=dict(runtime_stamp=self.stamp,physics_steps=len(rows),hold_samples=len(h),foot_body_whitelist=['left_ankle_roll_link','right_ankle_roll_link'],
                    robot_table_hold_max_normal_N=float(h[:,2].max()) if len(h) else None,nonfoot_floor_hold_max_normal_N=float(h[:,5].max()) if len(h) else None,
                    foot_floor_hold_min_normal_N=float((h[:,3]+h[:,4]).min()) if len(h) else None,robot_table_all_max_normal_N=float(rows[:,2].max()),nonfoot_floor_all_max_normal_N=float(rows[:,5].max()),
                    no_table_rest_in_hold=bool(len(h) and h[:,2].max()<.001),no_nonfoot_floor_support_in_hold=bool(len(h) and h[:,5].max()<.001),feet_supported_in_hold=bool(len(h) and (h[:,3]+h[:,4]).min()>1.),state_mutations=False,
                    columns=['time_s','solver_time_s','robot_table_or_riser_force_N','left_foot_floor_force_N','right_foot_floor_force_N','nonfoot_floor_force_N'],scope='support contacts only; not a COM/COP stability-margin certificate',raw_robot_support_contact_rows=len(self.contacts),raw_robot_support_contact_limit=1440000,raw_force_frame='MuJoCo contact frame; f0 is normal, wrench on geom2; not signed world support force')
        with gzip.open(self.out/'balance_contacts.csv.gz','wt') as f:
            f.write('# runtime_stamp='+json.dumps(self.stamp)+'\n# '+','.join(result['columns'])+'\n');np.savetxt(f,rows,delimiter=',',fmt='%.12g')
        contact_columns=['time_s','solver_time_s','phase','contact_index','robot_geom_id','robot_geom_name','support_geom_id','support_geom_name','robot_body','category','distance_m','normal_force_N','tangent1_force_N','tangent2_force_N','contact_torque0_Nm','contact_torque1_Nm','contact_torque2_Nm']
        with gzip.open(self.out/'robot_support_contacts.csv.gz','wt',newline='') as f:
            f.write('# runtime_stamp='+json.dumps(self.stamp)+'\n')
            writer=csv.writer(f);writer.writerow(contact_columns);writer.writerows(self.contacts)
        result['raw_contact_columns']=contact_columns
        (self.out/'balance-audit.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
