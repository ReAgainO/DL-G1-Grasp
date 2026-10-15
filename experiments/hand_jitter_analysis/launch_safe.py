"""Task-wide fail-closed launch guard; frozen physics code remains unchanged."""
from pathlib import Path
import datetime,fcntl,json,subprocess,sys
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
def active():
    found=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():continue
        try:
            tokens=(entry/'cmdline').read_bytes().split(b'\0')
            if any(str(R/n).encode() in tokens for n in ['execute_jitter.py','execute_jitter_pose.py','run_wave.py','run_wave_pose.py','render_dense.py','render_wave.py','render_clip.py','render_clip_wave.py']):
                found.append({'pid':int(entry.name),'command':b' '.join(tokens).decode()})
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    return found
if __name__=='__main__':
    with (R/'configs/launch.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        running=active();assert not running,('Own heavy processes still active; launch refused',running)
        assert sys.argv[1] in ['physics','pose']
        runner='run_wave.py' if sys.argv[1]=='physics' else 'run_wave_pose.py'
        p=subprocess.run(['/usr/bin/python3','-B',str(R/runner),'launch',sys.argv[2]],capture_output=True,text=True,timeout=120)
        with (R/'logs'/(sys.argv[2]+'-safe-launch.log')).open('x') as log:log.write(p.stdout+p.stderr)
        with (B/'logs'/R.name/'steps.md').open('a') as log:log.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' Task-wide launch guard, zero existing own heavy processes, source='+str(R/'launch_safe.py')+' rc='+str(p.returncode)+'\n')
        assert p.returncode==0,p.stdout+p.stderr
        print(p.stdout)
