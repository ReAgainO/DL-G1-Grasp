"""Project a fingertip target onto a bounded cube face ABOVE a table.

This is geometry for the independent finger IK, not measured contact avoidance.
No source/robot/object state or motor target is written here.
"""
import numpy as np


def face_target(point,cube_pos,cube_R,axis,face_coordinate,half_region,min_world_z=None):
    point=np.asarray(point,dtype=float);center=np.asarray(cube_pos,dtype=float);R=np.asarray(cube_R,dtype=float)
    if point.shape!=(3,) or center.shape!=(3,) or R.shape!=(3,3) or not np.isfinite(np.r_[point,center,R.ravel(),face_coordinate,half_region]).all():
        raise ValueError('Finite cube face geometry required')
    if axis not in [0,1,2] or not .006<=half_region<=.015:raise ValueError('Face axis/region contract')
    local=R.T@(point-center);target=np.clip(local,-half_region,half_region);target[axis]=face_coordinate
    if min_world_z is not None:
        if not np.isfinite(min_world_z):raise ValueError('Finite table clearance required')
        tangents=[index for index in range(3) if index!=axis]
        weights=R[2,tangents];maximum=center[2]+R[2,axis]*face_coordinate+half_region*abs(weights).sum()
        if maximum<min_world_z-1e-10:raise ValueError('Selected cube face region cannot clear table')
        current=float((center+R@target)[2])
        if current<min_world_z:
            # Monotone bounded projection toward the highest feasible corner;
            # preserves selected face and its tangential region, even if tilted.
            corner=target.copy();corner[tangents]=half_region*np.sign(weights)
            high=float((center+R@corner)[2]);fraction=(min_world_z-current)/max(high-current,1e-15)
            target+=np.clip(fraction,0.,1.)*(corner-target)
    result=center+R@target
    if min_world_z is not None and result[2]<min_world_z-1e-9:raise ValueError('Table projection failed')
    return result
