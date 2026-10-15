"""C2 receding quintic motion reference with exact polynomial extrema gates.

Only the SONIC reference is filtered. Actual robot/object states are untouched.
Future q and dq come from the SAME polynomial and clock, avoiding mismatched
filtered velocities and linearly extrapolated/overshooting positions.
"""
import numpy as np

def derivative(c,k=1):
 for _ in range(k):c=np.arange(1,len(c))[:,None]*c[1:]
 return c

def evaluate(c,t,k=0):
 c=derivative(c,k);t=np.asarray(t);return np.polynomial.polynomial.polyval(t,c).T

def extremes(c,T,k):
 p=derivative(c,k);dp=derivative(p);lo=[];hi=[]
 for j in range(p.shape[1]):
  coefficients=np.trim_zeros(dp[:,j],'b');times=[0.,T]
  if len(coefficients)>1:
   for r in np.roots(coefficients[::-1]):
    if abs(r.imag)<1e-8 and 0<r.real<T:times.append(float(r.real))
  values=np.polynomial.polynomial.polyval(times,p[:,j]);lo.append(float(np.min(values)));hi.append(float(np.max(values)))
 return np.array(lo),np.array(hi)

class ReferenceFilter:
 def __init__(self,q,lo,hi):
  self.q=np.asarray(q,dtype=float).copy();self.v=np.zeros_like(self.q);self.a=np.zeros_like(self.q)
  self.lo=np.asarray(lo);self.hi=np.asarray(hi);self.calls=0;self.maxima=np.zeros(3);self.max_T=0.;self.max_boundary_jump=0.
  assert np.all(self.q>=self.lo) and np.all(self.q<=self.hi)
 def step(self,goal,dt=.02):
  goal=np.asarray(goal)
  if goal.shape!=self.q.shape or not np.isfinite(goal).all():raise ValueError('Reference goal shape/finite')
  if (goal<self.lo-1e-9).any() or (goal>self.hi+1e-9).any():raise ValueError('Reference goal outside named joint limits')
  delta=goal-self.q;T=.9
  for attempt in range(18):
   if T>8:break
   c=np.stack([self.q,self.v,self.a/2,
     10*delta/T**3-6*self.v/T**2-1.5*self.a/T,
     -15*delta/T**4+8*self.v/T**3+1.5*self.a/T**2,
     6*delta/T**5-3*self.v/T**4-.5*self.a/T**3])
   qlo,qhi=extremes(c,T,0);bounds=[]
   for order in [1,2,3]:
    lower,upper=extremes(c,T,order);bounds.append(float(np.max(np.maximum(abs(lower),abs(upper)))))
   if (qlo>=self.lo-1e-9).all() and (qhi<=self.hi+1e-9).all() and np.all(np.asarray(bounds)<=[.6+1e-9,1.5+1e-9,12+1e-9]):break
   T*=1.2
  else:raise RuntimeError('Bounded reference search exhausted')
  if T>8:raise RuntimeError('No C2 plan inside eight-second motion horizon; stop, do not clip')
  old=(self.q.copy(),self.v.copy(),self.a.copy())
  self.max_boundary_jump=max(self.max_boundary_jump,max(float(abs(evaluate(c,[0],k)[0]-old[k]).max()) for k in range(3)))
  times=np.arange(10)*.1;qf=evaluate(c,times);vf=evaluate(c,times,1)
  self.q=evaluate(c,[dt])[0];self.v=evaluate(c,[dt],1)[0];self.a=evaluate(c,[dt],2)[0]
  self.calls+=1;self.maxima=np.maximum(self.maxima,bounds);self.max_T=max(self.max_T,T)
  return qf,vf
 def audit(self):
  return dict(kind='receding C2 quintic; analytic full-segment extrema; consistent q/dq future samples',calls=self.calls,
              velocity_max_rad_s=float(self.maxima[0]),acceleration_max_rad_s2=float(self.maxima[1]),jerk_max_rad_s3=float(self.maxima[2]),
              max_replan_C2_boundary_jump=self.max_boundary_jump,max_plan_horizon_s=self.max_T,
              velocity_limit=.6,acceleration_limit=1.5,jerk_limit=12)
