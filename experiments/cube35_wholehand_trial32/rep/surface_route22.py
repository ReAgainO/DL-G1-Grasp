"""Collision checking and bounded arm RRT for static approach."""
exec((__import__('pathlib').Path(__file__).parent/'coupled_surface_plan.py').read_text().split('for axis in [1,0]:')[0].replace('surface_plan22','surface_route22'))
entry=json.loads((r/'out/surface_entry22/entry.json').read_text());initial=base[qa[idx]].copy();goal=np.array(entry['vertical_approach'][-1]['arm_q']);hand=initial[7:].copy();errors=[];calls=0
def valid(q):
 global calls
 xx=initial.copy();xx[:7]=q;pose(xx);calls+=1
 if collision().max()>.00005:return False
 return not any(cube in [c.geom1,c.geom2] and c.dist<0 and (c.geom1 in slots or c.geom2 in slots) for c in d.contact[:d.ncon])
def edge(a,b):
 return all(valid(a+u*(b-a)) for u in np.linspace(0,1,max(2,int(np.max(abs(b-a))/.035)+2)))
way=json.loads((r/'out/joint_waypoints16.json').read_text())['waypoints'];safe=np.array(next(p for p in way if p['name']=='SAFE')['arm_q'])
path=None
if edge(initial[:7],safe) and edge(safe,goal):path=[initial[:7],safe,goal]
elif edge(initial[:7],goal):path=[initial[:7],goal]
else:
 rng=np.random.default_rng(22);trees=[([initial[:7].copy()],[-1]),([goal.copy()],[-1])];connected=None
 assert valid(initial[:7]) and valid(goal),'Initial or goal invalid'
 def extend(tree,target):
  qs,parents=tree;near=int(np.argmin([np.linalg.norm(q-target) for q in qs]));v=target-qs[near];q=qs[near]+v*min(1.,.2/max(np.linalg.norm(v),1e-12))
  if not edge(qs[near],q):return None
  qs.append(q);parents.append(near);return len(qs)-1
 for it in range(3000):
  if time.monotonic()-tic>35:break
  a=it%2;b=1-a;sample=trees[b][0][rng.integers(len(trees[b][0]))] if rng.random()<.25 else rng.uniform(lo[:7],hi[:7]);ia=extend(trees[a],sample)
  if ia is None:continue
  target=trees[a][0][ia]
  for z in range(35):
   ib=extend(trees[b],target)
   if ib is None:break
   if np.linalg.norm(trees[b][0][ib]-target)<1e-10:connected=(a,ia,ib);break
  if connected:break
 if connected:
  a,ia,ib=connected
  def chain(tree,k):
   qs,parents=tree;ans=[]
   while k!=-1:ans.append(qs[k]);k=parents[k]
   return ans[::-1]
  p0=chain(trees[a],ia);p1=chain(trees[1-a],ib)
  path=p0+p1[-2::-1] if a==0 else p1+p0[-2::-1]
  for _ in range(150):
   if len(path)<3:break
   i,k=sorted(rng.choice(len(path),2,replace=False))
   if k>i+1 and edge(path[i],path[k]):path=path[:i+1]+path[k:]
# Scan pre-shape and descent with planned hand; no dynamics claim.
checks={}
for phase in ['preshape','descent','closure']:
 depth=0.
 samples=[]
 if phase=='preshape':
  for u in np.linspace(0,1,61):samples.append(np.r_[goal,(1-u)*hand+u*np.array(entry['opening_path'][-1]['hand_q'])])
 elif phase=='descent':
  for p in entry['vertical_approach']:samples.append(np.r_[p['arm_q'],p['hand_q']])
 else:
  for p in entry['opening_path']:samples.append(np.r_[p['arm_q'],p['hand_q']])
 for xx in samples:pose(xx);depth=max(depth,float(collision().max()))
 checks[phase]=depth*1000
res=dict(approach_route=None if path is None else [q.tolist() for q in path],static_checks_max_penalty_mm=checks,collision_calls=calls,wall_s=time.monotonic()-tic,physics_success=False)
(o/'route.json').write_text(json.dumps(res,indent=2));print(json.dumps(res),flush=True)
