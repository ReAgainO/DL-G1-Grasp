"""Own import overlay pointing to existing read-only MuJoCo package only."""
import datetime
import hashlib
import json
from pathlib import Path

D=Path('/data/group4/20261006-093203-codex-6385a841')
B=Path('/home/group4/group4_dasc7606c')
source=B/'envs/render/lib/python3.10/site-packages/mujoco'
assert source.resolve().is_relative_to((B/'envs/render').resolve()) and source.is_dir()
files=list(source.rglob('*'));assert len(files)<=10000
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
before={str(file.relative_to(source)):sha(file) for file in files if file.is_file()}
dest=D/'mujoco314-only';assert not dest.exists()
dest.mkdir();(dest/'mujoco').symlink_to(source,target_is_directory=True)
assert (dest/'mujoco').is_symlink() and (dest/'mujoco').resolve()==source.resolve()
assert sorted(file.name for file in dest.iterdir())==['mujoco']
assert before=={str(file.relative_to(source)):sha(file) for file in files if file.is_file()}
now=datetime.datetime.now().astimezone().isoformat()
answer=dict(time=now,configuration_only=True,physical_steps=0,source=str(source),overlay=str(dest),
    source_package_hashes=before,source_files_changed=False,source_sha=sha(__file__),
    intended_python='/data/group4/20261004-205550-qoder-1280b420/env/bin/python',
    limitation='Only import-path overlay; readiness is not proof of successful import or physics. Do not change linked source. NumPy/Python/ORT fingerprint must be checked separately before trials.')
(D/'mujoco314-overlay-manifest.json').write_text(json.dumps(answer,indent=2)+'\n')
with (B/'logs/20261006-093203-codex-6385a841/steps.md').open('a') as f:
    f.write(f'\n## [MUJOCO ONLY IMPORT OVERLAY] {now}\n-Own directory{dest}, single read-only source package symlink->{source};{len(before)}file hashes unchanged. No install or shared environment writes. Prior two envs also differ Python3.10.22vs3.10.12/NumPy1.26.4vs2.2.6, so their differences are not isolated MuJoCo causality.\n')
print(json.dumps({k:v for k,v in answer.items() if k!='source_package_hashes'},indent=2))
