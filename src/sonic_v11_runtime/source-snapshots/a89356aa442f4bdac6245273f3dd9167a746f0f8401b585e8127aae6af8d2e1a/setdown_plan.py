"""Explicit geometric table-return scaffold; not a native generated motion.

Only the wrist task reference is planned here. SONIC still determines all
body actuator targets. This has no object-state or dynamics writes.
"""
import numpy as np


class SetdownPlan:
    def __init__(self,start,goal,duration_s=8.):
        self.start=np.asarray(start,dtype=float).copy()
        self.goal=np.asarray(goal,dtype=float).copy()
        if self.start.shape!=(3,) or self.goal.shape!=(3,) or not np.isfinite(np.r_[self.start,self.goal]).all():
            raise ValueError('finite Cartesian start and goal required')
        if not np.isfinite(duration_s) or not 6<=duration_s<=12:
            raise ValueError('table-return duration must be finite 6..12s')
        self.duration_s=float(duration_s)

    def evaluate(self,time_s):
        if not np.isfinite(time_s):raise ValueError('finite clock required')
        u=float(np.clip(time_s/self.duration_s,0,1))
        w=u*u*u*(10-15*u+6*u*u)
        dw=30*u*u*(1-u)*(1-u)/self.duration_s
        ddw=60*u*(1-u)*(1-2*u)/self.duration_s**2
        delta=self.goal-self.start
        return self.start+w*delta,dw*delta,ddw*delta

    def audit(self):
        distance=float(np.linalg.norm(self.goal-self.start))
        return dict(kind='explicit C2 Cartesian wrist table-return task scaffold',duration_s=self.duration_s,
            start_m=self.start.tolist(),goal_m=self.goal.tolist(),
            speed_bound_m_s=1.875*distance/self.duration_s,
            acceleration_bound_m_s2=10/np.sqrt(3)*distance/self.duration_s**2,
            jerk_bound_m_s3=60*distance/self.duration_s**3,
            generated_place_motion=False,body_motor_override=False,object_state_writes=False,
            limitation='Task-reference continuity only; actual SONIC tracking and contact-qualified table arrival require physics validation.')
