"""500Hz observer of actual body motion. Never changes state/control."""
import numpy as np


class ExecutionMonitor:
    def __init__(self, model, arm_speed_limit=2.):
        if not np.isfinite(arm_speed_limit) or not .5 <= arm_speed_limit <= 3.:
            raise ValueError('Explicit actual-arm speed limit must be .5..3rad/s')
        self.jids = np.asarray(model.actuator_trnid[:29, 0], dtype=int)
        self.aq = model.jnt_qposadr[self.jids]
        self.av = model.jnt_dofadr[self.jids]
        self.limits = model.jnt_range[self.jids].copy()
        self.names = [model.joint(int(j)).name for j in self.jids]
        self.dt = float(model.opt.timestep)
        self.arm_speed_limit = float(arm_speed_limit)
        self.phases = {}
        self.last_velocity = None
        self.samples = 0

    def step(self, data, phase):
        self.samples += 1
        assert self.samples <= 45000
        q = np.asarray(data.qpos[self.aq])
        v = np.asarray(data.qvel[self.av])
        assert np.isfinite(q).all() and np.isfinite(v).all()
        entry = self.phases.setdefault(str(phase), dict(samples=0, velocity=np.zeros(29),
            acceleration=np.zeros(29), overshoot=np.zeros(29), peak_arm_time_s=0.,peak_arm_joint=None))
        entry['samples'] += 1
        if np.max(abs(v[22:29])) > np.max(entry['velocity'][22:29]):
            index = 22 + int(np.argmax(abs(v[22:29])))
            entry['peak_arm_time_s'] = float(data.time)
            entry['peak_arm_joint'] = self.names[index]
        entry['velocity'] = np.maximum(entry['velocity'], abs(v))
        if self.last_velocity is not None:
            entry['acceleration'] = np.maximum(entry['acceleration'], abs((v-self.last_velocity)/self.dt))
        entry['overshoot'] = np.maximum(entry['overshoot'],
            np.maximum(self.limits[:, 0]-q, q-self.limits[:, 1]))
        self.last_velocity = v.copy()

    def finish(self):
        assert self.samples > 0
        maximum_velocity = np.max([x['velocity'] for x in self.phases.values()], axis=0)
        maximum_overshoot = np.max([x['overshoot'] for x in self.phases.values()], axis=0)
        rows = {phase:dict(samples=x['samples'], actual_velocity_max_rad_s=x['velocity'].tolist(),
            actual_velocity_difference_acceleration_max_rad_s2=x['acceleration'].tolist(),
            actual_joint_limit_overshoot_max_rad=x['overshoot'].tolist(),
            peak_arm_time_s=x['peak_arm_time_s'],peak_arm_joint=x['peak_arm_joint'])
            for phase,x in self.phases.items()}
        return dict(physics_samples=self.samples,sample_hz=1/self.dt,joint_names=self.names,
            phases=rows,actual_arm_speed_limit_rad_s=self.arm_speed_limit,
            actual_arm_speed_within_limit=bool(np.max(maximum_velocity[22:29]) <= self.arm_speed_limit),
            actual_body_limits_within_2mrad=bool(np.max(maximum_overshoot) <= .002),
            maximum_actual_arm_speed_rad_s=float(np.max(maximum_velocity[22:29])),
            maximum_body_joint_limit_overshoot_rad=float(np.max(maximum_overshoot)),
            state_mutations=False,control_mutations=False,
            definition='Actual post-step qvel at500Hz; finite differences include solver transients. 2rad/s default and2mrad soft-limit tolerance are explicit engineering gates, not PDF/factory safety certification.')
