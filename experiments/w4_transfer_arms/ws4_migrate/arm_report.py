#!/usr/bin/env python3
"""W4b arm report: injected cells vs S1000 baseline (and rep_base where re-run)."""
import json
from pathlib import Path
W=Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
S1000=Path('/data/group4/20261008-125638-qoder-d266d3a9/S1000/rep/out')
A=W/'rep_ext_cfg/rep/out'; BASE=W/'rep_base/rep/out'
CELLS=['b25_12_04','b25_04_01','b25_02_06','b25_00_10','b25_10_18','b25_02_09','b25_12_05','b25_10_19','b25_00_18','b25_12_10','b25_04_04','b25_12_14']
def row(p):
 try:r=json.loads((p/'result.json').read_text())
 except Exception:return None
 red=sorted(k for k,v in r['gates'].items() if not v)
 g=r.get('grip_target_json') or {}
 return dict(succ=bool(r['success']),fail=(r.get('fail_reason') or ''),lift=round((r.get('hold_min_lift_m') or -1)*1e3,1),
  slip=round((r.get('hold_slip_m') or -1)*1e3,2),red=red,ik=(r.get('adaptive_hand') or {}).get('calls'),applied=g.get('applied'))
print('%-11s | %-42s | %-42s | %-40s'%('cell','S1000 baseline (W4a)','rep_ext_cfg INJECTED','rep_base (re-run, if any)'))
def fmt(x):
 if x is None:return '-'
 r='S' if x['succ'] else 'F'
 f=('fail='+x['fail'][:20]) if x['fail'] else 'ran'
 return '%s %s lift=%s slip=%s red=%d ik=%s'%(r,f,x['lift'],x['slip'],len(x['red']),x['ik'])
summary={'succ_all':0,'lost':0,'gain':0,'tmo':0,'ran':0}
for c in CELLS:
 s=row(S1000/c);a=row(A/c);b=row(BASE/c)
 print('%-11s | %-42s | %-42s | %-40s'%(c,fmt(s),fmt(a),fmt(b)))
 if a:
  if a['succ']:summary['succ_all']+=1
  if a['fail']:summary['tmo']+=1
  else:summary['ran']+=1
  if s and s['succ'] and not a['succ']:summary['lost']+=1
  if s and not s['succ'] and a['succ']:summary['gain']+=1
print('injected arm: success=%d  close-timeout=%d  ran-all=%d  (baseline successes lost=%d, newly gained=%d)'%(
 summary['succ_all'],summary['tmo'],summary['ran'],summary['lost'],summary['gain']))
print('--- gates detail (injected)')
for c in CELLS:
 a=row(A/c)
 if a:print('  %-11s red=%s'%(c,'|'.join(a['red'])))
print('--- bitwise A(noflag smoke) vs injected, same cell b25_12_04 (should now DIFFER)')
