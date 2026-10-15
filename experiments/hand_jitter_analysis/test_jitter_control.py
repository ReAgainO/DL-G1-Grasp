"""Bounded unit tests: prove active/disabled branches and causal behavior."""
import unittest
import numpy as np
from jitter_control import ArmTargetSmoother

class SmoothingTests(unittest.TestCase):
    def test_disabled_is_exact_and_has_no_alias(self):
        raw = np.linspace(-.3,.3,29)
        out = ArmTargetSmoother(.06).step(raw,.001,False)
        self.assertTrue(np.array_equal(raw,out))
        out[22] += 1
        self.assertNotEqual(out[22],raw[22])

    def test_zero_tau_is_exact(self):
        raw = np.linspace(-.3,.3,29)
        self.assertTrue(np.array_equal(ArmTargetSmoother(0).step(raw,.001,True),raw))

    def test_active_branch_changes_only_arm(self):
        controller = ArmTargetSmoother(.06)
        first = np.zeros(29)
        controller.step(first,.001,False)
        goal = np.ones(29)
        out = controller.step(goal,.001,True)
        self.assertTrue(np.array_equal(out[:22],goal[:22]))
        self.assertTrue(((out[22:29]>0)&(out[22:29]<1)).all())
        self.assertFalse(np.array_equal(out[22:29],goal[22:29]))

    def test_constant_step_matches_exact_response(self):
        controller = ArmTargetSmoother(.06)
        controller.step(np.zeros(29),.001,False)
        goal = np.ones(29)
        for _ in range(60):
            out = controller.step(goal,.001,True)
        np.testing.assert_allclose(out[22:29],1-np.exp(-1),rtol=0,atol=1e-14)

    def test_bounded_and_causal(self):
        first,second = ArmTargetSmoother(.06),ArmTargetSmoother(.06)
        for index in range(100):
            target = np.sin(index)*np.ones(29)
            a,b = first.step(target,.001,True),second.step(target,.001,True)
            self.assertTrue(np.array_equal(a,b))
            self.assertLessEqual(float(abs(a[22:29]).max()),1.)
        first.step(np.ones(29)*100,.001,True)
        self.assertTrue(np.array_equal(b,a))

    def test_invalid_configuration(self):
        for tau in [-.01,.3]:
            with self.assertRaises(ValueError):
                ArmTargetSmoother(tau)
        with self.assertRaises(ValueError):
            ArmTargetSmoother(.06).step(np.zeros(7),.001,True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
