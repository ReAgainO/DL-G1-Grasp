#!/usr/bin/env python3
"""W4b cell-selection helper. Read-only on S1000 (d266d3a9)."""
import json
from pathlib import Path
S=Path('/data/group4/20261008-125638-qoder-d266d3a9/S1000')
jobs={}
for ln in (S/'jobs.txt').read_text().splitlines():
 f=ln.split('|')
 if len(f)>=6 and f[0].startswith('b25'):jobs[f[0]]=dict(edge=f[1],cx=f[2],cy=f[3],face=f[4],stem=f[5])
rows=[]
for p in sorted((S/'rep/out').glob('b25_*/result.json')):
 r=json.loads(p.read_text());n=p.parent.name
 red=sorted(k for k,v in r['gates'].items() if not v)
 fb=int((r.get('reference_filter') or {}).get('certified_continuation_steps') or 0)
 rows.append(dict(name=n,succ=bool(r.get('success')),fail=r.get('fail_reason') or '',red=red,
  lift=(r.get('hold_min_lift_m') or -9)*1e3,slip=(r.get('hold_slip_m') or -9)*1e3,fb=fb,jobs=jobs.get(n,{})))
def show(title,sel,key=lambda x:(x['fb']!=0,x['fb'],x['slip'])):
 print('== %s n=%d'%(title,len(sel)))
 for x in sorted(sel,key=key):
  j=x['jobs'];print('   %-11s fb=%-3d lift=%7.1f slip=%7.2f fail=%-28s red=%s  cx=%s cy=%s'%(
   x['name'],x['fb'],x['lift'],x['slip'],x['fail'][:28],'|'.join(g[:18] for g in x['red']),j.get('cx','?'),j.get('cy','?')))
succ=[x for x in rows if x['succ']]
near=[x for x in rows if not x['succ'] and not x['fail'] and x['red']==['no_robot_table_contact_full_task']]
timeout=[x for x in rows if x['fail']=='two-finger contact timeout']
liftslip=[x for x in rows if not x['succ'] and not x['fail'] and 'hold_7cm' in x['red'] and 'slip_1cm' in x['red']]
sliponly=[x for x in rows if not x['succ'] and not x['fail'] and 'slip_1cm' in x['red'] and 'hold_7cm' not in x['red']]
show('SUCCESS',succ);show('NEAR (only table gate)',near,key=lambda x:(x['fb']!=0,x['fb']))
show('TIMEOUT close two-finger',timeout,key=lambda x:(x['fb']!=0,x['fb']))
print('== LIFT+SLIP fb=0 (assertable class) n=%d'%len([x for x in liftslip if x['fb']==0]))
for x in sorted([y for y in liftslip if y['fb']==0],key=lambda y:y['slip']):
 j=x['jobs'];print('   %-11s fb=%-3d lift=%7.1f slip=%7.2f red_n=%d  cx=%s cy=%s'%(x['name'],x['fb'],x['lift'],x['slip'],len(x['red']),j.get('cx','?'),j.get('cy','?')))
show('SLIP-ONLY',sliponly)
print('== mask for easy pick: first 40 lift+slip by fb,slip')
for x in sorted(liftslip,key=lambda y:(y['fb']!=0,y['fb'],y['slip']))[:40]:
 j=x['jobs'];print('   %-11s fb=%-3d lift=%7.1f slip=%7.2f  cx=%s cy=%s'%(x['name'],x['fb'],x['lift'],x['slip'],j.get('cx','?'),j.get('cy','?')))
