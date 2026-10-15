"""Second full decode and per-video identity check; preserve bounded progress."""
import resource, os
resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
from pathlib import Path
import json, subprocess, re, time, hashlib, argparse

R = Path(__file__).resolve().parent
ffmpeg = '/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'
manifest = json.loads((R/'manifest.json').read_text())
parser=argparse.ArgumentParser()
parser.add_argument('--attempt',default='01')
parser.add_argument('--resume',help='own prior attempt report filename, preserve earlier failures')
args=parser.parse_args()
assert re.fullmatch(r'[A-Za-z0-9-]{1,16}',args.attempt)
attempt_path=R/('video-verification-attempt-'+args.attempt+'.json')
assert not attempt_path.exists(),'attempt already recorded; use a new attempt ID'
prior={}
if args.resume:
    assert Path(args.resume).name==args.resume
    old=json.loads((R/args.resume).read_text())
    assert old['source_sha']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'resume only same verifier build'
    assert old['manifest_sha']==hashlib.sha256((R/'manifest.json').read_bytes()).hexdigest(),'resume only same frozen manifest'
    prior={row['id']:row for row in old['videos']}
rows, failed, stamps = [], [], {}
reused=[]
start = time.monotonic()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
decoder_sha=sha(ffmpeg)

def report():
    stamp = None
    if stamps:
        first = next(iter(stamps.values()))
        stamp = {key: first[key] for key in ['mujoco_version', 'sys_executable', 'python_version', 'scene_generator_sha', 'library_sha', 'dt']}
        stamp.update(model_sha={name: value['model_sha'] for name, value in stamps.items()},
                     coverage_count=len(stamps), coverage='per-video replay stamp equality to original result; attempted source identities preserved')
        stamp['library_sha']={'common':{key:value for key,value in first['library_sha'].items() if key!='plan'},
                              'per_trial_plan':{name:value['library_sha']['plan'] for name,value in stamps.items()}}
    return {'runtime_stamp': stamp, 'source_sha': sha(__file__), 'manifest_sha':sha(R/'manifest.json'), 'checked_videos': len(rows),
            'attempted_videos': len(rows)+len(failed), 'failures': failed, 'videos': rows,
            'attempt_id':args.attempt,'resumed_from':args.resume,'resumed_verified_ids':reused,'decoder_sha':decoder_sha,
            'wall_s': time.monotonic()-start,
            'scope': 'independent metadata measurement and second full decode, zero physics steps'}

def progress():
    temp = R/('video-verification-progress-'+args.attempt+'.tmp')
    temp.write_text(json.dumps(report(), indent=2))
    temp.replace(R/('video-verification-progress-'+args.attempt+'.json'))

for index, trial in enumerate(manifest['trials']):
    remaining = 575-(time.monotonic()-start)
    if remaining <= 2:
        failed.extend({'id': item['id'], 'error': 'not checked: overall verification wall bound'}
                      for item in manifest['trials'][index:])
        progress()
        break
    out = R/'out'/trial['id']
    path = out/'replay/grasp.mp4'
    try:
        result = json.loads((out/'result.json').read_text())
        meta = json.loads((out/'replay/replay.json').read_text())
        stamps[trial['id']] = result['runtime_stamp']
        assert meta['id'] == trial['id'] and meta['runtime_stamp'] == result['runtime_stamp']
        assert meta['classification'] == result['classification'] and meta['success'] == result['success']
        assert meta['renderer_sha'] == manifest['sources_sha']['render_batch.py']
        assert meta['replay_only'] is True and meta['physical_steps'] == 0 and meta['mesa_lp_threads'] == 2
        assert len(meta['cpu_affinity']) == 2 and set(meta['cpu_affinity']) <= set(range(80,96))
        assert meta['video_sha'] == sha(path)
        assert meta['source_result_sha'] == sha(out/'result.json')
        assert meta['source_trajectory_sha'] == sha(out/'trajectory.npz')
        previous=prior.get(trial['id'])
        if previous:
            log=Path(previous['decode_log']).resolve()
            assert log.is_relative_to((R/'logs').resolve())
            assert previous['log_sha']==sha(log) and previous['full_decode_rc']==0
            assert previous['runtime_stamp']==result['runtime_stamp'] and previous['decoder_sha']==decoder_sha
            assert previous['video_sha']==meta['video_sha'] and previous['source_result_sha']==meta['source_result_sha']
            assert previous['source_trajectory_sha']==meta['source_trajectory_sha']
            assert previous['decoded_frames']==meta['frames'] and abs(previous['measured_container_duration_s']-meta['duration_s'])<.025
            rows.append(previous);reused.append(trial['id']);progress();continue
        proc = subprocess.run([ffmpeg, '-v', 'info', '-nostdin', '-threads', '1', '-i', str(path), '-f', 'null', '-'],
                              capture_output=True, text=True, timeout=min(30,remaining-1))
        log = R/'logs'/(trial['id']+'-independent-decode-'+args.attempt+'.log')
        with log.open('x') as stream:
            stream.write(proc.stdout+'\nSTDERR\n'+proc.stderr)
        assert proc.returncode == 0, proc.stderr[-1000:]
        durations = re.findall(r'Duration:\s+(\d+):(\d+):(\d+\.\d+)', proc.stderr)
        assert len(durations) == 1
        h, m, s = map(float, durations[0])
        duration = h*3600+m*60+s
        frames = re.findall(r'frame=\s*(\d+)', proc.stderr)
        assert frames
        count = int(frames[-1])
        assert count == meta['frames'] and abs(duration-meta['duration_s']) < .025
        assert meta['source_result_sha'] == sha(out/'result.json')
        assert meta['source_trajectory_sha'] == sha(out/'trajectory.npz')
        rows.append({'id':trial['id'], 'measured_container_duration_s':duration,
                     'decoded_frames':count, 'video_sha':meta['video_sha'],
                     'source_result_sha':meta['source_result_sha'], 'source_trajectory_sha':meta['source_trajectory_sha'],
                     'runtime_stamp':result['runtime_stamp'], 'full_decode_rc':proc.returncode,
                     'decoder_sha':decoder_sha,
                     'decode_log':str(log), 'log_sha':sha(log)})
    except Exception as error:
        failure = {'id':trial['id'], 'error':repr(error)}
        if isinstance(error, subprocess.TimeoutExpired):
            log = R/'logs'/(trial['id']+'-independent-decode-timeout-'+args.attempt+'.log')
            with log.open('xb') as stream:
                stream.write((error.stdout or b'')+b'\nSTDERR\n'+(error.stderr or b''))
            failure['log'] = str(log)
        failed.append(failure)
    progress()

result = report()
with attempt_path.open('x') as stream:
    json.dump(result, stream, indent=2)
if not failed:
    assert len(rows)==len(manifest['trials'])==len({row['id'] for row in rows})==360
    with (R/'video-verification.json').open('x') as stream:
        json.dump(result,stream,indent=2)
print(json.dumps({'verified':len(rows), 'failures':failed, 'wall_s':result['wall_s']}))
raise SystemExit(bool(failed))
