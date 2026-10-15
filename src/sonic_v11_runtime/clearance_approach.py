"""Explicit task-space raise-before-rotate scaffold; not a motor controller."""
import numpy as np


class ClearanceApproach:
    def __init__(self, wrist_position, wrist_rotation, table_top_z):
        self.origin = np.asarray(wrist_position,dtype=float).copy()
        self.rotation = np.asarray(wrist_rotation,dtype=float).copy()
        if self.origin.shape!=(3,) or self.rotation.shape!=(3,3) or not np.isfinite(self.origin).all() or not np.isfinite(self.rotation).all():
            raise ValueError('Finite wrist pose required')
        if not .5 <= table_top_z <= 1.:
            raise ValueError('Table height outside validated scaffold domain')
        self.clearance_z = max(.90,float(table_top_z)+.14)
        self.hover = self.origin.copy()
        self.hover[2] = max(self.clearance_z+.025,self.origin[2]+.15)
        self.passed_time = None
        self.transition_origin = None

    @staticmethod
    def quint(value):
        x = np.clip(value,0.,1.)
        return float(x*x*x*(10-15*x+6*x*x))

    def update(self, elapsed, actual_wrist_z, actual_closed_pad_center, final_pad_target):
        if not np.isfinite(elapsed) or elapsed<0 or elapsed>26:
            raise ValueError('Approach clock bound0..26s')
        if self.passed_time is None and elapsed>=4. and actual_wrist_z>=self.clearance_z:
            self.passed_time = float(elapsed)
            self.transition_origin = np.asarray(actual_closed_pad_center,dtype=float).copy()
        if self.passed_time is None:
            wrist = self.origin+self.quint(elapsed/4.)*(self.hover-self.origin)
            return dict(wrist_target=wrist,pad_target=None,rotation=self.rotation.copy(),clearance_passed=False)
        target = np.asarray(final_pad_target,dtype=float)
        if target.shape!=(3,) or not np.isfinite(target).all():
            raise ValueError('Finite final pad target required')
        u = self.quint((elapsed-self.passed_time)/6.)
        pad = (1-u)*self.transition_origin+u*target
        return dict(wrist_target=None,pad_target=pad,rotation=None,clearance_passed=True)

    def audit(self):
        return dict(kind='real-wrist full pose raise, then closed-pad task transition',
            actual_wrist_clearance_z_m=self.clearance_z,hover_wrist_position_m=self.hover.tolist(),
            clearance_passed_time_s=self.passed_time,
            approach_time_limit_s=26.,post_clearance_transition_s=6.,
            rotation_frozen_until_actual_clearance=True,body_motor_target_override=False,
            geometry_constraint_certified=False,
            limits='Task scaffold into SONIC reference only; clearance checks wrist height, not every link. Original solver contacts and actual velocity/limits remain the acceptance evidence.')
