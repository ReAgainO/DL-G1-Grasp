import datetime,json,os,subprocess
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';L=B/'logs'/T
note='第三波继续自有输入参考离散候选搜索（编码死区有零步进原NPZ测量）；增加direct-table派生场景：方块初始高度不变、窄柱移除、桌面top=.757/front=.23，cube自由关节碰撞保留，仅pelvis-world夹具；实际桌高用于4cm离面判据。新增独立手指相对面IK，只动手指参考、1.5rad/s限速、原力矩上限，身体目标仍仅SONIC。20次启动/波与4核AS16/90s/300s/data1GiB上限不变，目前16次启动已退出，无SONIC抓取成功；之后只用剩余4次额度。'
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
p=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',note],env=env,capture_output=True,text=True,timeout=60)
(L/'wave3-adapter-receipt.txt').write_text(p.stdout+p.stderr);assert p.returncode==0
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave3_adapters='+json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),note=note))+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE3 ADAPTER NOTE]\n'+note+'\n'+p.stdout+p.stderr+'\n- FSQ measured values lie on 1/16 grid; quarter-grid test residual .5 rejects the quarter-grid hypothesis, does not establish quarter-step quantization. Earlier teleop maximum difference .25 was NOT step size.\n- First adaptive hand face-centre constraint was too restrictive (best max error13.2mm); face-region projection scan best2.066mm, zero physics steps, NOT grasp proof.\n')
print(p.stdout+p.stderr)
