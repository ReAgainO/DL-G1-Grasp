"""Recompute derived motion native-skeleton FK; no model generation and no physics."""
from pathlib import Path
import numpy as np,json,hashlib,torch
torch.set_num_threads(2);torch.set_num_interop_threads(1)
from ardy.skeleton import G1Skeleton34
r=Path(__file__).resolve().parent;o=r/'out/native_ardy22';src=o/'repaired_s42_pending_fk.npz'
with np.load(src) as z:
 a={k:np.array(z[k]) for k in ['local_rot_mats','root_positions','fps','text','source_native_sha256']}
sk=G1Skeleton34();lr=torch.tensor(a['local_rot_mats'],dtype=torch.float32);rp=torch.tensor(a['root_positions'],dtype=torch.float32)
with torch.no_grad():gr,gp,_=sk.fk(lr,rp)
a['global_rot_mats']=gr.numpy();a['posed_joints']=gp.numpy();a['smooth_root_pos']=a['root_positions'].copy();a['repair_kind']=np.asarray('Native ARDY decoded motion + explicit sparse C2 body reference repair; FK regenerated. This derived file is not a native generator output.')
out=o/'repaired_s42.npz';np.savez_compressed(out,**a)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=json.loads((o/'repair-manifest-pending.json').read_text());stamp.update(derived_motion_sha256=sha(out),fk_source_sha256=sha(__file__),pose_fk_validated=True,derived_npz_schema='local_rot_mats/root_positions/posed_joints/global_rot_mats all mutually consistent via G1Skeleton34 FK; removed stale inferred foot/heading metadata',physical_success=False,active_in_controller=False)
(o/'repair-manifest.json').write_text(json.dumps(stamp,indent=2));print(json.dumps(stamp),flush=True)
