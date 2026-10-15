"""Observer arithmetic/branch tests; not a simulation real-time certificate."""
import unittest
from cycle_latency import CycleLatency


class Clock:
    def __init__(self):self.value=0.
    def __call__(self):return self.value


class Tests(unittest.TestCase):
    def test_measures_ten_step_whole_cycle_not_policy_only(self):
        clock=Clock();observer=CycleLatency(clock)
        for step in range(10):
            observer.begin(step,'APPROACH');clock.value+=.003;observer.end();clock.value+=.001
        audit=observer.audit()
        self.assertEqual(audit['complete_50Hz_cycles']['samples'],1)
        self.assertAlmostEqual(audit['complete_50Hz_cycles']['max_ms'],39.)
        self.assertEqual(audit['complete_50Hz_cycles']['over_budget_count'],1)
        self.assertEqual(audit['physics_steps_500Hz']['over_budget_count'],10)
        self.assertFalse(audit['real_time_validated']);self.assertFalse(audit['pacing'])

    def test_partial_cycle_is_not_reported_as_complete(self):
        clock=Clock();observer=CycleLatency(clock)
        for step in range(13):
            observer.begin(step,'HOLD');clock.value+=.001;observer.end()
        audit=observer.audit()
        self.assertEqual(audit['partial_final_cycle_steps'],3)
        self.assertEqual(audit['complete_50Hz_cycles']['samples'],1)
        self.assertEqual(audit['physics_steps_500Hz']['samples'],13)

    def test_phase_at_cycle_start_and_mixed_cycle(self):
        clock=Clock();observer=CycleLatency(clock)
        for step in range(20):
            observer.begin(step,'LIFT' if step<5 else 'HOLD');clock.value+=.001;observer.end()
        self.assertEqual(set(observer.audit()['by_cycle_start_phase']),{'LIFT','HOLD'})

    def test_bound(self):
        clock=Clock();observer=CycleLatency(clock,max_steps=1)
        observer.begin(0,'HOLD');clock.value=.001;observer.end()
        with self.assertRaises(ValueError):observer.begin(1,'HOLD')

    def test_sequence(self):
        observer=CycleLatency(Clock())
        with self.assertRaises(ValueError):observer.begin(2,'HOLD')

    def test_no_duplicate_begin(self):
        observer=CycleLatency(Clock());observer.begin(0,'HOLD')
        with self.assertRaises(ValueError):observer.begin(0,'HOLD')

    def test_end_requires_begin(self):
        with self.assertRaises(ValueError):CycleLatency(Clock()).end()

    def test_backwards_clock(self):
        clock=Clock();observer=CycleLatency(clock);observer.begin(0,'HOLD');clock.value=-.1
        with self.assertRaises(ValueError):observer.end()

    def test_bad_bounds_and_labels(self):
        for limit in [0,45001,1.5,True]:
            with self.assertRaises(ValueError):CycleLatency(max_steps=limit)
        with self.assertRaises(ValueError):CycleLatency(Clock()).begin(0,'x'*33)

    def test_actual_clock_branch(self):
        observer=CycleLatency();observer.begin(0,'HOLD');observer.end()
        self.assertGreaterEqual(observer.audit()['physics_steps_500Hz']['max_ms'],0.)


if __name__=='__main__':unittest.main(verbosity=2)
