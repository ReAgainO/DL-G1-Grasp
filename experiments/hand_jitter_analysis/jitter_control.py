"""Explicit causal actuator adapter; changes only decoded right-arm targets."""
import numpy as np

class ArmTargetSmoother:
    def __init__(self, tau_s):
        if not 0 <= tau_s <= .20:
            raise ValueError('Bounded time constant0..200ms')
        self.tau_s = float(tau_s)
        self.arm = None

    def step(self, decoded_target, dt, active):
        raw = np.asarray(decoded_target, dtype=float)
        if raw.shape != (29,) or not np.isfinite(raw).all():
            raise ValueError('Expected29 finite SONIC targets')
        if not active or self.tau_s == 0:
            self.arm = raw[22:29].copy()
            return raw.copy()
        if self.arm is None:
            self.arm = raw[22:29].copy()
        alpha = -np.expm1(-dt / self.tau_s)
        self.arm += alpha * (raw[22:29] - self.arm)
        result = raw.copy()
        result[22:29] = self.arm
        assert np.array_equal(result[:22], raw[:22])
        return result
