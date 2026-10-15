"""Bounded SONIC input-side correction after an ARDY-seeded branch warm-up.

No MuJoCo state, actuator, policy output, or object access. The physical arm's
local IK error is added to the current *input* reference, then the caller uses
the same C2 trajectory filter and official policy as every other reference.
"""
import numpy as np


class BranchExecution:
    warmup_seconds = 6.
    approach_timeout_seconds = 32.
    correction_cap_rad = .06

    def __init__(self, selected_time, branch_q):
        self.selected_time = float(selected_time)
        self.branch_q = np.asarray(branch_q, dtype=float).copy()
        if not np.isfinite(self.selected_time) or self.selected_time < 0 or self.branch_q.shape != (7,) or not np.isfinite(self.branch_q).all():
            raise ValueError('Finite branch and nonnegative selection time required')
        self.updates = 0
        self.maximum_increment = 0.
        self.maximum_capture_error = 0.
        self.last = None

    def servo_enabled(self, time):
        time = float(time)
        if not np.isfinite(time) or time < self.selected_time - 1e-8:
            raise ValueError('Branch clock cannot precede its actual selection')
        return time - self.selected_time >= self.warmup_seconds - 1e-8

    def correction(self, reference, actual_q, desired_q, low, high):
        arrays = [np.asarray(x, dtype=float) for x in (reference, actual_q, desired_q, low, high)]
        if any(x.shape != (7,) or not np.isfinite(x).all() for x in arrays):
            raise ValueError('Finite seven-joint correction inputs required')
        reference, actual_q, desired_q, low, high = arrays
        if (low >= high).any() or (reference < low - 1e-8).any() or (reference > high + 1e-8).any():
            raise ValueError('Named legal reference bounds required')
        delta = desired_q - actual_q
        delta *= min(1., self.correction_cap_rad / max(float(abs(delta).max()), 1e-12))
        goal = np.clip(reference + delta, low, high)
        self.updates += 1
        self.maximum_increment = max(self.maximum_increment, float(abs(goal-reference).max()))
        return goal

    def observe(self, time, capture_error, speed):
        if not np.isfinite([capture_error, speed]).all() or min(capture_error, speed) < 0:
            raise ValueError('Finite nonnegative actual error/speed required')
        active = self.servo_enabled(time)
        self.maximum_capture_error = max(self.maximum_capture_error, float(capture_error))
        self.last = dict(time_s=float(time), actual_closed_recipe_capture_error_m=float(capture_error),
                         actual_arm_speed_rad_s=float(speed), warmup_complete=active,
                         ready=bool(active and capture_error < .025 and speed < .2))
        return self.last['ready']

    def audit(self):
        return dict(kind='After6s ARDY-seeded branch warmup: actual-root local capture IK delta added to current SONIC input at5Hz',
                    branch_selected_time_s=self.selected_time, warmup_s=self.warmup_seconds,
                    approach_timeout_s=self.approach_timeout_seconds, updates=self.updates,
                    max_reference_increment_rad=self.maximum_increment, increment_cap_rad=self.correction_cap_rad,
                    maximum_observed_capture_error_m=self.maximum_capture_error, last_readiness=self.last,
                    body_motor_target_override=False, object_state_writes=False, c2_filter_required=True,
                    timeout_definition='32s approach hard bound reserves6s closed-loop correction after static branch transition; global90s unchanged. Not an endpoint/safety gate relaxation.')
