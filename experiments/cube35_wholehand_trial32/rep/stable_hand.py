"""Implicit-discrete PD on real hand mass matrix; original torque limits retained."""
import numpy as np,mujoco

def stable_hand_torques(m,d,qa,va,target,kp,kd,limits,gain=3.):
 assert target.shape==(7,) and 1<=gain<=3
 mass=np.zeros((m.nv,m.nv));mujoco.mj_fullM(m,mass,d.qM);H=mass[np.ix_(va,va)]
 K=np.asarray(kp)*gain;D=np.asarray(kd)*np.sqrt(gain);dt=float(m.opt.timestep)
 A=H+np.diag(D*dt+K*dt*dt)
 rhs=K*(target-d.qpos[qa])-(D+K*dt)*d.qvel[va]
 tau=H@np.linalg.solve(A,rhs)
 return np.clip(tau,limits[:,0],limits[:,1])