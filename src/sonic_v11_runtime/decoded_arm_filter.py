"""Causal rate-bounded decoded-target adapter; no IK/manual motor targets.

Stage1 limits target displacement per tick. Stages2/3 are convex exponential
averages. A fixed dt and alpha give conservative discrete derivative bounds:
|v|<=vmax, |a|<=2*alpha*vmax/dt, |j|<=4*alpha**2*vmax/dt**2.
These bounds describe actuator setpoints, not actual joint motion, and are not
a continuous-time C2 certificate. Raw SONIC actions/history are left unchanged.
"""
import numpy as np

class DecodedArmFilter:
    def __init__(self,lo,hi,tau=.3,vmax=.6,dt=.002):
        assert .1<=tau<=1. and .2<=vmax<=1.5 and dt==.002
        self.lo=np.asarray(lo);self.hi=np.asarray(hi);self.tau=tau;self.vmax=vmax;self.dt=dt
        self.alpha=dt/(tau+dt);self.calls=0;self.q=None;self.maxima=np.zeros(3);self.max_offset=0.

    def reset(self,q):
        q=np.asarray(q,dtype=float)
        assert q.shape==self.lo.shape and np.isfinite(q).all() and (q>=self.lo-1e-12).all() and (q<=self.hi+1e-12).all()
        self.q=np.tile(q,(3,1));self.prev_v=np.zeros_like(q);self.prev_a=np.zeros_like(q)

    def step(self,target):
        target=np.asarray(target)
        assert self.q is not None and target.shape==self.lo.shape and np.isfinite(target).all()
        assert (target>=self.lo-1e-12).all() and (target<=self.hi+1e-12).all()
        old=self.q[2].copy()
        self.q[0]+=np.clip(target-self.q[0],-self.vmax*self.dt,self.vmax*self.dt)
        for i in (1,2):self.q[i]+=self.alpha*(self.q[i-1]-self.q[i])
        v=(self.q[2]-old)/self.dt;a=(v-self.prev_v)/self.dt;j=(a-self.prev_a)/self.dt
        self.maxima=np.maximum(self.maxima,[np.abs(v).max(),np.abs(a).max(),np.abs(j).max()])
        self.prev_v=v;self.prev_a=a;self.calls+=1;self.max_offset=max(self.max_offset,float(abs(self.q[2]-target).max()))
        assert (self.q[2]>=self.lo-1e-12).all() and (self.q[2]<=self.hi+1e-12).all()
        return self.q[2].copy()

    def audit(self):
        return dict(kind='causal decoded-target rate limiter followed by two convex exponential stages',calls=self.calls,tau_s=self.tau,dt_s=self.dt,
                    stage1_speed_limit_rad_s=self.vmax,conservative_discrete_derivative_bounds=[self.vmax,2*self.alpha*self.vmax/self.dt,4*self.alpha**2*self.vmax/self.dt**2],
                    measured_discrete_velocity_acceleration_jerk_max=self.maxima.tolist(),max_raw_decoded_to_applied_offset_rad=self.max_offset,
                    raw_sonic_action_or_history_modified=False,manual_ik_body_targets=False,actual_joint_limits_certified=False,continuous_C2_certified=False)
