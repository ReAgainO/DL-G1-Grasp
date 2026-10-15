"""Contact planning on compiled original collision-mesh convex surfaces, no marker/sphere radius."""
import numpy as np
from scipy.spatial import ConvexHull

def closest_on_triangles(p,tris):
 a,b,c=tris[:,0],tris[:,1],tris[:,2];u=b-a;v=c-a;normal=np.cross(u,v);n2=np.maximum(np.sum(normal*normal,axis=1),1e-20)
 proj=p-normal*(np.sum((p-a)*normal,axis=1)/n2)[:,None];r=proj-a;uu=np.sum(u*u,axis=1);vv=np.sum(v*v,axis=1);uv=np.sum(u*v,axis=1);ur=np.sum(u*r,axis=1);vr=np.sum(v*r,axis=1);den=np.maximum(uu*vv-uv*uv,1e-20);beta=(ur*vv-vr*uv)/den;gamma=(vr*uu-ur*uv)/den
 inside=(beta>=-1e-10)&(gamma>=-1e-10)&(beta+gamma<=1+1e-10);candidates=[proj];distances=[np.where(inside,np.sum((proj-p)**2,axis=1),np.inf)]
 for x,y in [(a,b),(b,c),(c,a)]:
  ab=y-x;t=np.clip(np.sum((p-x)*ab,axis=1)/np.maximum(np.sum(ab*ab,axis=1),1e-20),0,1);q=x+t[:,None]*ab;candidates.append(q);distances.append(np.sum((q-p)**2,axis=1))
 dd=np.stack(distances);k,i=np.unravel_index(np.argmin(dd),dd.shape);return candidates[k][i].copy()

class FingerSurfaces:
 def __init__(self,m):
  self.m=m;self.ids=[m.geom('physical_right_hand_'+n+'_link').id for n in ['thumb_2','middle_1']];self.tris=[]
  for gg in self.ids:
   mm=m.geom_dataid[gg];v=m.mesh_vert[m.mesh_vertadr[mm]:m.mesh_vertadr[mm]+m.mesh_vertnum[mm]].astype(float);h=ConvexHull(v);self.tris.append(v[h.simplices])
 def points(self,d,cube_pos,cube_R,half,zoffset=.008):
  points=[]
  for gg,tris,side in zip(self.ids,self.tris,[1.,-1.]):
   target=np.asarray(cube_pos)+np.asarray(cube_R)@np.array([0,side*half,zoffset]);world=tris@d.geom_xmat[gg].reshape(3,3).T+d.geom_xpos[gg];points.append(closest_on_triangles(target,world))
  return np.array(points)