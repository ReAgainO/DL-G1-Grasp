from pathlib import Path
import json
from collections import Counter
def vi(b,p):
 v=0;s=0
 while True:
  x=b[p];p+=1;v|=(x&127)<<s
  if x<128:return v,p
  s+=7

def fields(b):
 p=0
 while p<len(b):
  x,p=vi(b,p);n=x>>3;w=x&7
  if w==0:v,p=vi(b,p)
  elif w==1:v=b[p:p+8];p+=8
  elif w==2:l,p=vi(b,p);v=b[p:p+l];p+=l
  elif w==5:v=b[p:p+4];p+=4
  else:raise ValueError(w)
  yield n,w,v
b=Path('sonic_v11/model_encoder.onnx').read_bytes();graph=next(v for n,w,v in fields(b) if n==7);nodes=[];outputs=[]
for n,w,v in fields(graph):
 if n==1:
  dd={'inputs':[],'outputs':[]}
  for nn,ww,vv in fields(v):
   if nn in (1,2,3,4):
    tt=vv.decode('utf8');k={1:'inputs',2:'outputs',3:'name',4:'op'}[nn]
    if nn in (1,2):dd[k].append(tt)
    else:dd[k]=tt
  nodes.append(dd)
 if n==12:outputs.extend(vv.decode() for nn,ww,vv in fields(v) if nn==1)
byout={k:nd for nd in nodes for k in nd['outputs']};seen=set();stack=outputs.copy()
while stack:
 o=stack.pop()
 if o in seen:continue
 seen.add(o)
 if o in byout:stack.extend(byout[o]['inputs'])
rs=[nd for nd in nodes if nd['op']=='Round'];print(json.dumps({'outputs':outputs,'node_count':len(nodes),'ops':dict(Counter(nd['op'] for nd in nodes)),'round_nodes':[dict(nd,connected_to_output=any(o in seen for o in nd['outputs'])) for nd in rs]},indent=2))