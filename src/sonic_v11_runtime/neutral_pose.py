"""Explicit neutral body-reference adaptation, not a motor-target override."""
import numpy as np


def neutral_body(model, factory_angles, shoulder_offset=0.):
    reference = np.asarray(factory_angles, dtype=float).copy()
    if reference.shape != (29,) or not np.isfinite(reference).all():
        raise ValueError('Require 29 finite factory body angles')
    if not np.isfinite(shoulder_offset) or not -.2 <= shoulder_offset <= .4:
        raise ValueError('Neutral shoulder offset outside labelled -.2..+.4rad domain')
    names = [model.joint(int(j)).name for j in model.actuator_trnid[:29, 0]]
    for name in ['left_shoulder_pitch_joint', 'right_shoulder_pitch_joint']:
        index = names.index(name)
        reference[index] += shoulder_offset
        jid = int(model.actuator_trnid[index, 0])
        if not model.jnt_range[jid, 0] + .002 <= reference[index] <= model.jnt_range[jid, 1] - .002:
            raise ValueError('Neutral shoulder reference violates model joint limit')
    return reference
