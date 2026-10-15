"""Import/CLI and actual final-table gate branches; absolutely no mj_step."""
import contextlib
import hashlib
import inspect
import io
import json
import runpy
import sys
from pathlib import Path
import mujoco
import sonic_grasp
from setdown_plan import table_supported_gate

root=Path(__file__).resolve().parent;out=root/'out/setdown-interface-tests';out.mkdir()
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
check('setdown_default_disabled',inspect.signature(sonic_grasp.run).parameters['setdown'].default is False)
check('empty_or_short_window_cannot_pass',not table_supported_gate([]) and not table_supported_gate([.2]*49))
check('floor_load_not_counted_as_table',not table_supported_gate([0.]*50))
check('table_full_window_passes',table_supported_gate([.1962]*50))
check('threshold_is_strict',not table_supported_gate([.05]*50) and table_supported_gate([.050001]*50))
check('interrupted_support_fails',not table_supported_gate([.2]*49+[0.]))
check('old_unloaded_steps_outside_window_ignored',table_supported_gate([0.]*100+[.2]*50))
for name,values in [('nan',[float('nan')]*50),('negative',[-1.]*50),('oversize',[.2]*45001),('shape',[[.2]*50])]:
    rejected=False
    try:table_supported_gate(values)
    except ValueError:rejected=True
    check('reject_'+name,rejected)
old_argv=sys.argv.copy()
stream=io.StringIO()
try:
    sys.argv=[str(root/'sonic_grasp.py'),'--help']
    with contextlib.redirect_stdout(stream):
        try:runpy.run_path(str(root/'sonic_grasp.py'),run_name='__main__')
        except SystemExit as e:check('CLI_help_exit_zero',e.code==0)
finally:sys.argv=old_argv
check('CLI_declares_setdown_and_finger_gain','--setdown' in stream.getvalue() and '--finger-gain' in stream.getvalue())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
episode=root/'out/w5_fingergain3_free327';r=json.loads((episode/'result.json').read_text())
answer=dict(runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=.002,model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'sonic_grasp':sha(root/'sonic_grasp.py'),'setdown_plan':sha(root/'setdown_plan.py')}),
    physical_steps=0,passed=True,checks=checks,reference_model_only=True,
    limitation='CLI/help and support-gate branch tests only. Does not execute a simulation or establish physical placing success.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
