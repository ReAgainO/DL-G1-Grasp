"""Preserve original 3 motions and the vendor conversion asset; copy-only."""
import datetime,json,shutil
from pathlib import Path
import sonic_v11 as s
ROOT=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c');T=ROOT.name
source=Path('/data/group4/20261005-222503-codex-a8d69b27/out')
target=ROOT/'src/original_motions';target.mkdir()
files=[]
for name in ['control_s42.npz','control_s42.csv','near_s42.npz','near_s42.csv','far_s42.npz','far_s42.csv','summary.json']:
 src=source/name;dst=target/name;shutil.copy2(src,dst);assert s.sha(src)==s.sha(dst)
 files.append(dict(source=str(src),path=str(dst),sha256=s.sha(dst),bytes=dst.stat().st_size))
ardy=B/'repos/ardy/ardy'
for src,dst in [(ardy/'assets/skeletons/g1skel34/xml/g1.xml',ROOT/'src/ardy_converter_g1.xml'),
                (ardy/'exports/mujoco.py',ROOT/'official_refs/ardy_mujoco_converter.py')]:
 assert not dst.exists();shutil.copy2(src,dst);assert s.sha(src)==s.sha(dst)
 files.append(dict(source=str(src),path=str(dst),sha256=s.sha(dst),bytes=dst.stat().st_size))
# Reuse an existing package by a private copy; do not upgrade either environment.
import yaml
dst=ROOT/'pydeps/yaml';assert not dst.exists()
shutil.copytree(Path(yaml.__file__).parent,dst)
for src in sorted(Path(yaml.__file__).parent.rglob('*')):
 if src.is_file():assert s.sha(src)==s.sha(dst/src.relative_to(Path(yaml.__file__).parent))
(ROOT/'input-npz-provenance.json').write_text(json.dumps(files,indent=2)+'\n')
with (B/'logs'/T/'steps.md').open('a') as f:
 f.write('\n## [04] '+datetime.datetime.now().astimezone().isoformat()+' 原始NPZ前门及双版本依赖\n'
         '- 原始control/near/far NPZ、配对CSV、生成summary逐SHA复制；没有重生成或改动原始motion。\n'
         '- 已读ARDY原厂MujocoQposConverter完整导出算法0-260行；用NumPy镜像进行独立重算并与原始CSV对拍，不由posed_joints反推关节。\n'
         '- 第二版本env缺yaml；把现有PyYAML包仅复制进自有pydeps（无共享env升级），SONIC import顺序改为先添加自有pydeps再导yaml。\n'
         '- 第一SONIC stand327仿真完成但JSON保存np.bool_失败，CSV/NPZ与报错日志保留；使用新名字v2重跑，未覆盖失败证据。\n')
print(json.dumps(dict(copied=len(files),files=files),indent=2))
