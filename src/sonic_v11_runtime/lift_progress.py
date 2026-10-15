"""C2 monotone retiming of generated lift progress, not robot dynamics control.

Each positive native progress increment becomes a nonnegative weighted quintic
transition. Common finite support gives explicit Cartesian derivative bounds.
The increment weights and their ordering come from ARDY; duration/window are
explicit task adaptations. No state, body target, or object force is written.
"""
import numpy as np


class LiftProgress:
    def __init__(self, progress, duration_s=8., window_s=4.):
        progress = np.asarray(progress, dtype=float)
        if progress.ndim!=1 or not 2<=len(progress)<=2250 or not np.isfinite(progress).all():
            raise ValueError('finite progress vector of length 2..2250 required')
        if not np.isfinite(duration_s) or not np.isfinite(window_s) or not 2<=window_s<duration_s<=20:
            raise ValueError('finite 2 <= window < duration <=20 seconds required')
        if abs(progress[0])>1e-12 or abs(progress[-1]-1)>1e-12 or (np.diff(progress)<-1e-12).any():
            raise ValueError('normalized nondecreasing 0..1 progress required')
        self.duration_s=float(duration_s);self.window_s=float(window_s)
        self.weights=np.maximum(np.diff(progress),0.)
        self.weights/=self.weights.sum()
        # Preserve source order, compress centres enough that every transition
        # has the same certified width and is fully contained in [0,duration].
        native_mid=(np.arange(len(self.weights))+.5)/len(self.weights)
        self.centres=window_s*.5+native_mid*(duration_s-window_s)
        self.starts=self.centres-window_s*.5

    def evaluate(self,time_s):
        if not np.isfinite(time_s):raise ValueError('finite time required')
        x=np.clip((float(time_s)-self.starts)/self.window_s,0.,1.)
        value=x*x*x*(10-15*x+6*x*x)
        velocity=30*x*x*(1-x)*(1-x)/self.window_s
        acceleration=60*x*(1-x)*(1-2*x)/self.window_s**2
        return tuple(float(self.weights@a) for a in [value,velocity,acceleration])

    def audit(self):
        return dict(kind='nonnegative ARDY progress increments -> common-support quintic CDF mixture',
            duration_s=self.duration_s,window_s=self.window_s,positive_native_increments=int((self.weights>0).sum()),
            progress_velocity_bound_per_s=1.875/self.window_s,
            progress_acceleration_bound_per_s2=(10/np.sqrt(3))/self.window_s**2,
            progress_jerk_bound_per_s3=60/self.window_s**3,
            C2=True,monotone=True,body_motor_override=False,
            limitation='Scalar Cartesian progress only; IK/reference/decoded/actual-joint dynamics must be validated separately. Native timing is smoothed and compressed, not preserved literally.')
