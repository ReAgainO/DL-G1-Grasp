"""Isolated CPU ONNX runtime and copied official model; no shared install."""
import datetime,hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T
BR=B/'repos/sonic-bridge';OFF=B/'repos/sonic/GR00T-WholeBodyControl'
assert hashlib.sha256((B/'AGENTS.md').read_bytes()).hexdigest()=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
now=datetime.datetime.now().astimezone().isoformat()
assert shutil.disk_usage(D).free>30*1024**3+1024**3
with (B/'claims'/T/'card.txt').open('a') as f:
 f.write('scope_extension='+now+' 用户持续测试改进授权范围内增加官方SONIC v1.1 CPU加载和闭环接口实验；只在自有data模型副本和pydeps安装onnxruntime/flatbuffers（no-deps，不升级既有env）；预算data峰值1GiB/AS16GiB/4核/每命令300s；无GPU、无共享源码写入、无服务。\n')
with (B/'logs'/T/'steps.md').open('a') as f:
 f.write('\n## [03] '+now+' SONIC官方ONNX独立运行前置\n- 已完整读sonic-bridge/AGENTS（旧规约，根新版优先），已读取官方配置和C++对应槽位/动作scale。\n- 重要契约：encoder_mode_4是mode id加3个零，不是one-hot；v1.1四个G1槽实际读取，其余槽为零但全宽1751；heading-only相对朝向按C++首两列行序排列。\n- 本任务首轮错误osmesa库目录使用aarch64而节点为amd64，引发glGetError AttributeError；原始日志已存。非渲染测试改MUJOCO_GL=disable，无安装/全局变量更改。\n- W4已有属主，当前只做独立控制器实验，不替换W4接口。前置: data12T, home12G;只写data的大件，估计峰值1GiB。\n')
env=os.environ.copy()
for n in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']: env.pop(n,None)
r=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '持续优化授权内建立官方SONIC v1.1 CPU隔离后端，只装自有pydeps无共享环境升级；预算1GiB、4核AS16GiB，先验证槽名/宽度/图形状'],env=env,text=True,capture_output=True,timeout=100)
(B/'logs'/T/'sonic-scope-receipt.txt').write_text(r.stdout+r.stderr)
assert r.returncode==0
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):h.update(block)
 return h.hexdigest()
copies=[]
models=D/'sonic_v11';models.mkdir()
for name in ['model_encoder.onnx','model_decoder.onnx']:
 src=Path('/data/group4/20261006-063957-qoder-w01sonic11/sonic_v1_1')/name;dst=models/name
 shutil.copy2(src,dst);assert sha(src)==sha(dst)
 copies.append(dict(source=str(src),destination=str(dst),sha256=sha(dst),bytes=dst.stat().st_size))
src=Path('/data/group4/20261006-063957-qoder-w01sonic11/observation_config_v11.yaml')
shutil.copy2(src,models/'observation_config.yaml');assert sha(src)==sha(models/'observation_config.yaml')
refs=D/'official_refs';refs.mkdir()
for src in [OFF/'gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp',
            OFF/'gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/policy_parameters.hpp',
            OFF/'docs/source/references/observation_config.md',BR/'adapters/sonic_action_adapter.py']:
 dst=refs/src.name;shutil.copy2(src,dst);assert sha(src)==sha(dst)
 copies.append(dict(source=str(src),destination=str(dst),sha256=sha(dst),bytes=dst.stat().st_size))
target=D/'pydeps';assert not target.exists()
env.update(UV_CACHE_DIR=str(D/'uv-cache'),TMPDIR=str(D/'tmp'),XDG_CACHE_HOME=str(D/'cache'))
cmd=[str(B/'tools/uv'),'pip','install','--python',sys.executable,'--target',str(target),'--no-deps',
     '--index-url','https://pypi.tuna.tsinghua.edu.cn/simple','onnxruntime','flatbuffers']
log=B/'logs'/T/'onnx-install.log'
with log.open('x') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
assert r.returncode==0, 'Install failed, see '+str(log)
sys.path.insert(0,str(target))
import onnxruntime as ort
import numpy as np
opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
opts.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
graphs={}
for name in ['model_encoder.onnx','model_decoder.onnx']:
 session=ort.InferenceSession(str(models/name),sess_options=opts,providers=['CPUExecutionProvider'])
 graphs[name]=dict(inputs=[dict(name=x.name,shape=x.shape,type=x.type) for x in session.get_inputs()],
                   outputs=[dict(name=x.name,shape=x.shape,type=x.type) for x in session.get_outputs()],providers=session.get_providers())
manifest=dict(time=now,copies=copies,ort_version=ort.__version__,numpy_version=np.__version__,python=sys.executable,
              graphs=graphs,installed_only=str(target),shared_environment_modified=False,license='NVIDIA Open Model License; no publication',
              documentation=['https://onnxruntime.ai/docs/get-started/with-python.html','https://onnxruntime.ai/docs/api/python/api_summary.html'])
(D/'out/sonic-setup.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
