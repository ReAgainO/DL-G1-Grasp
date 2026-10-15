"""Independent right-finger PD; never writes body targets, state, or forces."""
import numpy as np


def finger_torques(command, position, velocity, kp, kd, limits, opponent=2, gain=1.):
    if not np.isfinite(gain) or not 1<=gain<=3:
        raise ValueError('independent-finger gain must be finite and 1..3')
    if opponent not in [1, 2]:
        raise ValueError('opponent must be index or middle')
    arrays = [np.asarray(a, dtype=float) for a in [command, position, velocity, kp, kd]]
    if any(a.shape!=(7,) or not np.isfinite(a).all() for a in arrays):
        raise ValueError('finite named seven-finger arrays required')
    limits = np.asarray(limits, dtype=float)
    if limits.shape!=(7, 2) or not np.isfinite(limits).all() or (limits[:, 0]>limits[:, 1]).any():
        raise ValueError('finite original seven-actuator torque limits required')
    command, position, velocity, kp, kd = arrays
    kp, kd = kp.copy(), kd.copy()
    active = np.r_[np.arange(3), np.arange(3, 5) if opponent==1 else np.arange(5, 7)]
    kp[active] *= gain
    kd[active] *= np.sqrt(gain)
    return np.clip(kp*(command-position)-kd*velocity, limits[:, 0], limits[:, 1])


def finger_position_torques(command, position, velocity, kp, kd, limits):
    """W4b2 wrapper: official USL finger position servo law.
    Same 7-array shape/limit validation as finger_torques; torque =
    clip(kp*(command-position)-kd*velocity, limits). Default path untouched."""
    arrays = [np.asarray(a, dtype=float) for a in [command, position, velocity]]
    if any(a.shape != (7,) or not np.isfinite(a).all() for a in arrays):
        raise ValueError('finite named seven-finger arrays required')
    kp = np.full(7, kp, dtype=float) if np.ndim(kp) == 0 else np.asarray(kp, dtype=float)
    kd = np.full(7, kd, dtype=float) if np.ndim(kd) == 0 else np.asarray(kd, dtype=float)
    if kp.shape != (7,) or kd.shape != (7,) or not np.isfinite(kp).all() or not np.isfinite(kd).all():
        raise ValueError('finite scalar-or-seven finger gains required')
    limits = np.asarray(limits, dtype=float)
    if limits.shape != (7, 2) or not np.isfinite(limits).all() or (limits[:, 0] > limits[:, 1]).any():
        raise ValueError('finite original seven-actuator torque limits required')
    command, position, velocity = arrays
    return np.clip(kp*(command-position)-kd*velocity, limits[:, 0], limits[:, 1])
