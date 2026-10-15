import unittest
import numpy as np
from finger_clearance import face_target


class Tests(unittest.TestCase):
    def test_default_matches_original_projection(self):
        for point in [np.array([.29,-.11,.754]),np.array([.2,-.12,.78])]:
            center=np.array([.267,-.118,.7745]);R=np.eye(3)
            expected=np.clip(point-center,-.015,.015);expected[0]=.022
            np.testing.assert_array_equal(face_target(point,center,R,0,.022,.015),center+expected)

    def test_world_clearance_preserves_side_face(self):
        center=np.array([.267,-.118,.7745]);result=face_target([.29,-.118,.75],center,np.eye(3),0,.022,.015,.764)
        self.assertGreaterEqual(result[2],.764-1e-10)
        self.assertAlmostEqual(result[0]-center[0],.022)
        self.assertTrue((abs((result-center)[1:])<=.015+1e-10).all())

    def test_tilted_face_and_region_preserved(self):
        angle=.4;R=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
        center=np.array([0,0,.775]);result=face_target([.03,0,.75],center,R,0,.022,.015,.767)
        local=R.T@(result-center)
        self.assertAlmostEqual(local[0],.022)
        self.assertTrue((abs(local[1:])<=.015+1e-10).all());self.assertGreaterEqual(result[2],.767-1e-10)

    def test_impossible_height_rejected(self):
        with self.assertRaises(ValueError):face_target([0,0,0],[0,0,.775],np.eye(3),0,.022,.015,.8)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):face_target([np.nan,0,0],[0,0,.775],np.eye(3),0,.022,.015,.767)


if __name__=='__main__':unittest.main(verbosity=2)
