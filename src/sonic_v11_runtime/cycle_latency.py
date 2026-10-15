"""Bounded wall-clock observer; never changes reference, torque or simulation.

A control cycle includes all ten 2ms physics steps between 50Hz updates:
reference construction, IK/branch searches, SONIC inference, fingers, physics
and in-loop contact/audit work. It excludes initialization and final output
serialization, which must be reported separately. No pacing is introduced.
"""
import time
import numpy as np


class CycleLatency:
    def __init__(self, clock=time.perf_counter, max_steps=45000):
        if type(max_steps) is not int or not 1<=max_steps<=45000:
            raise ValueError('max_steps must be1..45000')
        self.clock=clock;self.max_steps=max_steps;self.completed=0
        self.pending=None;self.cycle_start=None;self.cycle_phase=None
        self.steps=[];self.cycles=[]

    def begin(self, step, phase):
        if type(step) is not int or step!=self.completed or step>=self.max_steps or self.pending is not None:
            raise ValueError('Sequential bounded steps; prior observation must end')
        if not isinstance(phase,str) or not 1<=len(phase)<=32:
            raise ValueError('Bounded phase label required')
        now=float(self.clock())
        if not np.isfinite(now):raise ValueError('Finite monotonic clock required')
        self.pending=(step,phase,now)
        if step%10==0:self.cycle_start=now;self.cycle_phase=phase

    def end(self):
        if self.pending is None:raise ValueError('begin required')
        step,phase,start=self.pending;now=float(self.clock())
        if not np.isfinite(now) or now<start or now<self.cycle_start:
            raise ValueError('Monotonic finite clock required')
        self.steps.append((step,phase,(now-start)*1000))
        self.completed+=1;self.pending=None
        if self.completed%10==0:
            self.cycles.append((step//10,self.cycle_phase,(now-self.cycle_start)*1000))

    @staticmethod
    def stats(samples, budget_ms):
        values=np.asarray([row[2] for row in samples],dtype=float)
        assert values.ndim==1 and len(values)<=45000 and np.isfinite(values).all() and (values>=0).all()
        if not len(values):return dict(samples=0,budget_ms=budget_ms)
        return dict(samples=len(values),budget_ms=budget_ms,median_ms=float(np.median(values)),
            p95_ms=float(np.percentile(values,95)),p99_ms=float(np.percentile(values,99)),
            max_ms=float(values.max()),over_budget_count=int((values>budget_ms).sum()),
            over_budget_fraction=float(np.mean(values>budget_ms)))

    def audit(self):
        phases=sorted({row[1] for row in self.cycles});assert len(phases)<=16
        return dict(observed_loop_iterations=self.completed,unfinished_observation=self.pending is not None,
            partial_final_cycle_steps=self.completed%10,
            complete_50Hz_cycles=self.stats(self.cycles,20.),nominal_500Hz_iterations=self.stats(self.steps,2.),
            by_cycle_start_phase={phase:self.stats([row for row in self.cycles if row[1]==phase],20.) for phase in phases},
            observer_only=True,pacing=False,real_time_validated=False,
            definition='Host wall time for ten consecutive loop observations incl reference/branch/IK/SONIC/finger/physics/audit/state transitions; no pacing. A failed iteration may stop before physics and is counted separately by the caller. Initial model/motion load and final serialization excluded. This is execution latency, not policy-only latency or measured end-to-end user response.')
