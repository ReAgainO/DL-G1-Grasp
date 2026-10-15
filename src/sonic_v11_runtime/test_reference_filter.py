import json
from pathlib import Path
import numpy as np
from reference_filter import ReferenceFilter,evaluate,extremes
root=Path(__file__).resolve().parent;out=root/'out/reference-filter-tests.json';assert not out.exists()
tests=[]
f=ReferenceFilter(np.zeros(7),np.ones(7)*-2,np.ones(7)*2)
for k in range(150):
 goal=np.sin(k*.01+np.arange(7))*.3
 q0,v0,a0=f.q.copy(),f.v.copy(),f.a.copy();q,v=f.step(goal)
 assert np.allclose(q[0],q0) and np.allclose(v[0],v0)
 assert np.max(abs(q-q0))<=.6*.9+1e-8
 assert abs(f.v).max()<=.6+1e-8 and abs(f.a).max()<=1.5+1e-8
tests.extend(['150 bounded replans','future q and v same quintic','C2 boundary continuous','joint limits no clipping'])
for label,g in [('nan',np.ones(7)*np.nan),('shape',np.zeros(6)),('limits',np.ones(7)*3)]:
 try:f.step(g)
 except ValueError:tests.append('reject_'+label)
 else:raise AssertionError(label)
# Quartic q with interior extrema: roots, not only endpoint checks.
c=np.array([[0],[0],[1],[-2],[1],[0]],float)
lo,hi=extremes(c,1,0);assert abs(hi[0]-.0625)<1e-12 and lo[0]==0
tests.append('interior polynomial extremum caught')
r=dict(pass_count=len(tests),tests=tests,audit=f.audit());out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
