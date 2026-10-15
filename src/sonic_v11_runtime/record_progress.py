"""Add scoped evidence notes through sanctioned shared writers; no global takeover."""
import json,os,subprocess
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';L=B/'logs'/T
out=L/'progress-issue-receipts.txt';assert not out.exists()
states={}
for line in (B/'claims/issues.jsonl').read_text().splitlines():
 r=json.loads(line);states[r['issue']]=r
notes=[
 ('ISS-SONIC-OBS-CONTRACT-ALIGNED-1762-CLEARS-ZERO-BASELINE','独立官方v1.1 CPU后端1751/994已验证，不替换遗留1762策略口径',
  '本TASKID只在自有目录加入官方SONIC v1.1 ONNX后端，graph实际输入1751/994、token64、输出29；与遗留1762 Torch策略不是同一个导出，不能互相改数字。G1接口15测试PASS；teleop16测试PASS且冷启动逐字节重复、右腕目标变更影响action，G1重构前后encoder/decoder/action逐字节不变。MuJoCo3.2.7小幅动态ON/OFF RMS .0373709/.0492076rad，3.14.0 .0402706/.0480088rad，均无跌倒；这是脚本识别探针而非ARDY或抓取。证据reports/'+T+'-wave1-report.md、/data/group4/'+T+'/out/sonic-contract-tests.json、teleop-contract-tests.json。下一步本TASKID继续原始NPZ任务参考闭环，不改他人bridge/env；判据为保留身体SONIC输出、真实接触7cm抬升等，预计2波CPU实验。全局issue保持OPEN，不声明迁移共享主干。'),
 ('ISS-ARDY-G1-FPS-CONTRACT-25','原始与新增G1 NPZ直接转换25fps对拍通过，独立预检入口已落实',
  '本TASKID motion_input.py强制native fps25与source_fps一致、G1Skeleton34/旋转矩阵/有限值/帧数上限，100帧末时刻3.96s→50Hz199帧。原始control/near/far三个NPZ与vendor CSV关节最大差≤1.79e-7rad；新增reach/lift/hold/release四段也对拍≤1.20e-7rad，无原生关节超限。未覆盖共享生产入口，因此保持OPEN。证据/data/group4/'+T+'/out/native-npz-contract.json、wave2-analysis-01.json。接手命令bash /data/group4/'+T+'/run.sh motion_input.py需用新的报告输出路径避免覆盖旧证据；现有输出只读查看。判据为25fps拒20fps、named joint order与vendor parity；本TASKID继续补负样本与阶段消费审计，预计10min CPU。'),
 ('ISS-GRASP-ARDY-ATTRIBUTION-BLOCKED','最终固定底座同版零ARDY消融仍成功；纯SONIC新链未完成抓取',
  '本TASKID重新做最终同路径ARDY零空间.08/0消融：MuJoCo3.2.7保持最低84.0118/83.7957mm，3.14.0 83.6345/83.3019mm，ON与OFF均成功；每版no-grip/pads-off峰值0，固定底座成功仍不是ARDY必要贡献。原始nearNPZ→官方v1.1纯SONIC身体执行，3.2.7速度.25 RMS .0753595rad但张手仅偶然3.859mm抬动，不算抓取；小幅动态未跌倒不等于任务成立。新增CPU生成四段25fps文本动作，cold encoder68.8s，每段2.78–3.16s；当前早期抓取候选全部对齐/接触超时，phase_clips_loaded不能当作phase_clips_consumed。回放还发现物体被碰离支撑后旧坐标失效，现本TASKID仅自有代码改为仿真状态目标（非视觉）、接触门控及SONIC参考端补偿。证据reports/'+T+'-wave1-report.md、/data/group4/'+T+'/out/native_capture22_on/contact-snapshots.json。继续本TASKID独立≤20集/波CPU，成功判据7cm保持/≥2指/无支撑/释放，无腕目标覆盖、外力、weld或物体脚本运动。预计2波；保持OPEN。')]
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
receipts=[]
for issue,title,body in notes:
 if issue not in states or states[issue]['state']=='CLOSED':
  receipts.append('SKIPPED closed/missing '+issue);continue
 cmd=['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_append.sh'),'--field','owner_task='+T,'--field','evidence=reports/'+T+'-wave1-report.md',
      issue,'note',states[issue]['state'],title,body]
 p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=150);receipts.append(p.stdout+p.stderr)
 assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
for path in ['work/20260930-0310-qoder-issuereg/issue_view.sh','work/20260930-0310-qoder-issuereg/issue_verify.sh']:
 p=subprocess.run(['bash',str(B/path)],env=env,capture_output=True,text=True,timeout=150);receipts.append(p.stdout+p.stderr);assert p.returncode==0
out.write_text('\n'.join(receipts))
with (L/'steps.md').open('a') as f:f.write('\n## [ISSUE NOTES]\n'+ '\n'.join(receipts)+'\n- All issues remain open/scoped; no takeover or shared implementation change.\n')
print('\n'.join(receipts))
