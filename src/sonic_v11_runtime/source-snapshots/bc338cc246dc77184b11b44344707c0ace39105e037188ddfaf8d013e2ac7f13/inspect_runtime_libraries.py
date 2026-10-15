"""Read-only current software environment fingerprint; never retrofits old runs."""
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
import onnxruntime as ort

root=Path(__file__).resolve().parent
dest=root/'out'/('runtime-libraries-'+mujoco.__version__+'.json')
assert not dest.exists()
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
import numpy._core._multiarray_umath as numpy_native
import onnxruntime.capi.onnxruntime_pybind11_state as ort_native
answer=dict(physical_steps=0,time=__import__('datetime').datetime.now().astimezone().isoformat(),
    versions=dict(mujoco=mujoco.__version__,numpy=np.__version__,onnxruntime=ort.__version__,python=sys.version),
    sys_executable=sys.executable,source_sha=sha(__file__),
    imported_library_files={key:dict(path=str(module.__file__),sha256=sha(module.__file__))
        for key,module in [('numpy_native',numpy_native),('ort_native',ort_native),('sonic_v11',s)]},
    limitation='Current imported environment only. Does not retroactively add missing native-library versions/hashes to old episode runtime stamps.')
dest.write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
