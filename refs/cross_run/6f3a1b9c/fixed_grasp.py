"""Bounded fixed-pelvis G1 right-arm/right-finger physical grasp experiment.

Keyframes, PD gains and three spherical fingertip pads are from the group's
sonic-bridge/runners/run_grasp.py and g1 assets. No policy inference, weld,
adhesion, external force, or object pose update is used during simulation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

DEFAULT = np.zeros(29)
for i, v in {0: -.312, 3: .669, 4: -.363, 6: -.312, 9: .669,
             10: -.363, 15: .2, 16: .2, 18: .6, 22: .2, 23: -.2, 25: .6}.items():
    DEFAULT[i] = v
ARM = np.arange(22, 29)
HAND = np.arange(36, 43)
SAFE = np.array([-1.363069, -.615202, 2.050898, .222550, .360051, 1.311507, 1.614430])
HIGH = np.array([-1.123446, -.928874, -2.164452, 2.069049, -1.405235, 1.603174, .097037])
GRASP = np.array([-1.046944, -.642793, -1.911197, 1.787889, -1.653604, 1.326327, .335080])
OPEN = np.array([0., -.70, -2., 1.40, .08, 1.40, .08])
CLOSED = np.array([0., -.60, -.425, 1.40, .08, 1.40, .08])
PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
DT, DURATION, FPS = .002, 23., 25


def blend(a, b, x):
    x = np.clip(x, 0., 1.)
    return a + (b-a) * x*x*(3-2*x)


def targets(t, no_grip):
    if t < 1:
        arm, phase = DEFAULT[ARM], 'SETTLE'
    elif t < 4:
        arm, phase = blend(DEFAULT[ARM], SAFE, (t-1)/3), 'APPROACH'
    elif t < 7:
        arm, phase = blend(SAFE, HIGH, (t-4)/3), 'PREGRASP'
    elif t < 9:
        arm, phase = HIGH, 'ALIGN'
    elif t < 12:
        arm, phase = blend(HIGH, GRASP, (t-9)/3), 'DESCEND'
    elif t < 14:
        arm, phase = GRASP, 'CLOSE'
    elif t < 17:
        arm, phase = blend(GRASP, HIGH, (t-14)/3), 'LIFT'
    elif t < 19:
        arm, phase = HIGH, 'HOLD'
    else:
        arm, phase = HIGH, 'RELEASE'
    hand = OPEN if no_grip else blend(OPEN, CLOSED, (t-12)/2)
    if t >= 19:
        hand = blend(CLOSED if not no_grip else OPEN, OPEN, (t-19)/1)
    return arm, hand, phase


def prepare_model(asset_dir, output_dir, cube_xy, cube_z, baseline_mount):
    """Make a derived XML in our copied asset directory; source stays intact."""
    root = ET.parse(asset_dir / 'g1_29dof_with_hand.xml')
    pelvis = root.find(".//body[@name='pelvis']")
    free = pelvis.find("joint[@type='free']")
    assert free is not None and free.get('name') == 'floating_base_joint'
    pelvis.remove(free)
    pelvis.set('pos', '0 0 0.788740')
    mount_angles = dict(waist_yaw_joint=.1532, waist_roll_joint=-.0686, waist_pitch_joint=.0069)
    if baseline_mount:
        # Fixed mounting pose from the successful source baseline at t=12 s.
        # This is set before simulation, not a time-varying kinematic constraint.
        pelvis.set('pos', '-0.0087 0.0079 0.7837')
        pelvis.set('quat', '0.9997 0.0143 -0.0205 -0.0032')
    # This is an isolated arm test: the waist is also structurally fixed at zero.
    for body in root.iter('body'):
        for joint in list(body.findall('joint')):
            if joint.get('name', '').startswith('waist_'):
                if baseline_mount:
                    assert np.allclose(np.fromstring(joint.get('pos', '0 0 0'), sep=' '), 0)
                    angle = mount_angles[joint.get('name')]
                    axis = np.fromstring(joint.get('axis'), sep=' ')
                    qrot = np.r_[np.cos(angle/2), axis*np.sin(angle/2)]
                    qold = np.fromstring(body.get('quat', '1 0 0 0'), sep=' ')
                    qnew = np.zeros(4)
                    mujoco.mju_mulQuat(qnew, qold, qrot)
                    body.set('quat', ' '.join(map(str, qnew)))
                body.remove(joint)
    actuators = root.find('actuator')
    for actuator in list(actuators):
        if actuator.get('name', '').startswith('waist_'):
            actuators.remove(actuator)
    sensors = root.find('sensor')
    for sensor in list(sensors):
        if sensor.get('joint', '').startswith('waist_'):
            sensors.remove(sensor)
    root.find('compiler').set('meshdir', str(asset_dir/'meshes'))
    # Match the verified baseline: only the three pads collide on the right hand.
    for body in root.iter('body'):
        if body.get('name', '').startswith('right_hand_'):
            for geom in body.findall('geom'):
                geom.set('contype', '2' if geom.get('name') in PADS else '0')
                geom.set('conaffinity', '0')
    root.write(output_dir / 'g1_fixed_base.xml', encoding='utf-8')
    scene = ET.parse(asset_dir / 'scene_grasp_hand.xml')
    scene.find('include').set('file', 'g1_fixed_base.xml')
    cube = scene.find(".//geom[@name='red_cube_geom']")
    cube.set('contype', '1')
    cube.set('conaffinity', '3')
    scene.find(".//body[@name='red_cube']").set('pos', f'{cube_xy[0]} {cube_xy[1]} {cube_z}')
    pedestal_h = cube_z-.0175-.725
    if not .005 <= pedestal_h <= .08:
        raise ValueError('Pedestal height must be 5 to 80 mm')
    pedestal = scene.find(".//geom[@name='cube_pedestal_geom']")
    pedestal.set('pos', f'{cube_xy[0]} {cube_xy[1]} {.725+pedestal_h/2}')
    pedestal.set('size', f'0.0175 0.0175 {pedestal_h/2}')
    # Unlike the old baseline, the pads also collide with the table and pedestal.
    for geom in scene.findall('.//worldbody//geom'):
        if geom is not cube:
            geom.set('conaffinity', '3')
    scene.find('visual/global').set('offwidth', '960')
    scene.find('visual/global').set('offheight', '720')
    out = output_dir / 'scene_fixed_grasp.xml'
    scene.write(out, encoding='utf-8')
    return out


def get_id(model, kind, name):
    value = mujoco.mj_name2id(model, kind, name)
    if value < 0:
        raise ValueError(name)
    return value


def gains():
    motor = np.zeros(29)
    motor[[0, 1, 3, 6, 7, 9]] = .025101925
    motor[[2, 8, 12]] = .010177520
    motor[[4, 5, 10, 11, 13, 14]] = 2*.003609725
    motor[15:] = .003609725
    motor[[20, 21, 27, 28]] = .00425
    kp = np.concatenate([motor*(20*np.pi)**2, np.ones(14)*2])
    kd = np.concatenate([4*motor*20*np.pi, np.ones(14)*.05])
    kp[ARM] = [55, 55, 45, 45, 18, 18, 18]
    kd[ARM] = [3, 3, 2.5, 2.5, 1.2, 1.2, 1.2]
    kp[HAND] = [4, 1.8, 1.2, 4, 2, 4, 2]
    kd[HAND] = [.10, .07, .05, .06, .05, .06, .05]
    return kp, kd


def simulate(args):
    start = time.monotonic()
    CLOSED[2] = args.thumb_close
    CLOSED[1] = args.thumb_base_close
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    scene = prepare_model(args.assets.resolve(), out, args.cube_xy, args.cube_z, args.baseline_mount)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    runtime_stamp = dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
                         python_version=sys.version, model_sha={
                             'scene_xml': sha(scene), 'robot_xml': sha(out/'g1_fixed_base.xml')},
                         scene_generator_sha=sha(__file__),
                         library_sha={name: sha(args.assets.parent/name) for name in
                                      ['reference_run_grasp.py', 'reference_mount.csv']},
                         timestep=DT, dt=DT)
    model = mujoco.MjModel.from_xml_path(str(scene))
    assert model.nu == 40 and model.neq == 0
    assert sum(model.jnt_type == mujoco.mjtJoint.mjJNT_FREE) == 1  # Cube only.
    assert model.opt.timestep == DT
    data = mujoco.MjData(model)
    jids = model.actuator_trnid[:, 0]
    qa, va = model.jnt_qposadr[jids], model.jnt_dofadr[jids]
    original_names = [a.get('name') for a in ET.parse(args.assets/'g1_29dof_with_hand.xml').find('actuator')]
    original_indices = np.array([original_names.index(model.actuator(i).name) for i in range(model.nu)])
    arm_ids = np.array([model.actuator(original_names[i]).id for i in ARM])
    hand_ids = np.array([model.actuator(original_names[i]).id for i in HAND])
    full_initial = np.concatenate([DEFAULT, np.zeros(14)])
    full_initial[HAND] = OPEN
    initial = full_initial[original_indices]
    data.qpos[qa] = initial  # Initialization only; never written again.
    mujoco.mj_forward(model, data)
    cube = get_id(model, mujoco.mjtObj.mjOBJ_BODY, 'red_cube')
    wrist = get_id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_wrist_yaw_link')
    pelvis = get_id(model, mujoco.mjtObj.mjOBJ_BODY, 'pelvis')
    cg = get_id(model, mujoco.mjtObj.mjOBJ_GEOM, 'red_cube_geom')
    pad_ids = [get_id(model, mujoco.mjtObj.mjOBJ_GEOM, n) for n in PADS]
    support = {get_id(model, mujoco.mjtObj.mjOBJ_GEOM, n) for n in
               ['table_top', 'cube_pedestal_geom', 'floor']}
    initial_cube = data.xpos[cube].copy()
    initial_base = data.xpos[pelvis].copy()
    full_kp, full_kd = gains()
    kp, kd = full_kp[original_indices], full_kd[original_indices]
    target = initial.copy()
    rows, qpos_frames, velocities, phases, pad_pos = [], [], [], [], []
    warnings_before = np.array([w.number for w in data.warning])
    peak_external_force = 0.
    for step in range(round(DURATION/DT)):
        t = step*DT
        arm, hand, phase = targets(t, args.no_grip)
        target[arm_ids], target[hand_ids] = arm, hand
        target = np.clip(target, model.jnt_range[jids, 0], model.jnt_range[jids, 1])
        tau = kp*(target-data.qpos[qa])-kd*data.qvel[va]
        data.ctrl[:] = np.clip(tau, model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1])
        peak_external_force = max(peak_external_force, float(np.max(np.abs(data.xfrc_applied))),
                                  float(np.max(np.abs(data.qfrc_applied))))
        mujoco.mj_step(model, data)
        if not np.isfinite(data.qpos).all() or abs(data.time-(step+1)*DT) > 1e-6:
            raise RuntimeError('Nonfinite state or simulation reset')
        forces = np.zeros(3)
        support_force = 0.
        for i in range(data.ncon):
            c = data.contact[i]
            if cg not in (c.geom1, c.geom2):
                continue
            other = c.geom2 if c.geom1 == cg else c.geom1
            f = np.zeros(6)
            mujoco.mj_contactForce(model, data, i, f)
            if other in pad_ids:
                forces[pad_ids.index(other)] += max(0., f[0])
            if other in support:
                support_force += max(0., f[0])
        pos = data.xpos[cube].copy()
        rel = data.xmat[wrist].reshape(3, 3).T @ (pos-data.xpos[wrist])
        # Rotated cube's lowest corner is measured, not just center minus half-size.
        bottom = pos[2] - .0175*np.abs(data.xmat[cube].reshape(3, 3)[2]).sum()
        rows.append([data.time, *pos, *rel, *forces, support_force, bottom,
                     np.linalg.norm(data.xpos[pelvis]-initial_base)])
        if step % 20 == 0:
            qpos_frames.append(data.qpos.copy())
            velocities.append(data.qvel.copy())
            phases.append(phase)
            pad_pos.append(data.geom_xpos[pad_ids].copy())
    r = np.asarray(rows)
    hold = (r[:, 0] >= 17.02) & (r[:, 0] <= 19.)
    release = r[:, 0] >= 21.
    h = r[hold]
    lift = r[:, 3]-initial_cube[2]
    grip_bodies = (r[:, 7:10] > .01).sum(axis=1)
    hold_slip = float(np.max(np.linalg.norm(h[:, 4:7]-h[0, 4:7], axis=1)))
    warning_delta = (np.array([w.number for w in data.warning])-warnings_before).tolist()
    gates = {
        'hold_lift_at_least_7cm': bool(np.min(lift[hold]) >= .07),
        'hold_cube_bottom_4cm_above_table': bool(np.min(h[:, 11]-.725) >= .04),
        'two_finger_contacts_entire_hold': bool(np.min(grip_bodies[hold]) >= 2),
        'hold_without_support_contact': bool(np.max(h[:, 10]) < .001),
        'hold_slip_under_1cm': bool(hold_slip < .01),
        'release_drop_at_least_6cm': bool(h[-1, 3]-np.min(r[release, 3]) >= .06),
        'release_no_finger_contact_at_end': bool(grip_bodies[-1] == 0),
        'release_supported_at_end': bool(r[-1, 10] > .05),
        'fixed_base_no_motion': bool(np.max(r[:, 12]) < 1e-12),
        'no_external_force': bool(peak_external_force == 0),
        'no_mujoco_warnings': bool(not any(warning_delta)),
    }
    result = dict(success=all(gates.values()), no_grip=args.no_grip, gates=gates,
                  runtime_stamp=runtime_stamp,
                  mujoco_version=mujoco.__version__, duration_s=DURATION, steps=len(r),
                  simulation_wall_s=time.monotonic()-start, fixed_base='pelvis freejoint and three waist joints removed',
                  controller='scripted keyframes plus torque-limited joint PD; no ARDY or SONIC inference',
                  collision_model='existing three spherical right fingertips only, radius 10mm, friction=2',
                  cube_size_m=.035, cube_mass_kg=.020, pedestal_height_m=args.cube_z-.0175-.725,
                  thumb_close_target_rad=args.thumb_close,
                  thumb_base_close_target_rad=args.thumb_base_close,
                  baseline_mount=args.baseline_mount,
                  initial_cube_xyz_m=initial_cube.tolist(), max_lift_m=float(np.max(lift)),
                  hold_min_lift_m=float(np.min(lift[hold])), hold_slip_m=hold_slip,
                  hold_min_contact_bodies=int(np.min(grip_bodies[hold])),
                  hold_min_total_finger_normal_force_N=float(np.min(h[:, 7:10].sum(axis=1))),
                  hold_max_support_force_N=float(np.max(h[:, 10])),
                  hold_min_cube_bottom_clearance_m=float(np.min(h[:, 11]-.725)),
                  release_drop_m=float(h[-1, 3]-np.min(r[release, 3])),
                  final_cube_xyz_m=r[-1, 1:4].tolist(), warning_counts=warning_delta,
                  peak_external_force=peak_external_force, scene=str(scene),
                  scene_sha256=hashlib.sha256(scene.read_bytes()).hexdigest())
    np.savez_compressed(out/'trajectory.npz', qpos=np.asarray(qpos_frames), qvel=np.asarray(velocities),
                        phase=np.asarray(phases), pad_xyz=np.asarray(pad_pos), fps=FPS,
                        runtime_stamp=json.dumps(runtime_stamp, sort_keys=True),
                        time=np.arange(len(qpos_frames))*.04+.002, scene=str(scene))
    with (out/'telemetry.csv').open('w') as csv:
        csv.write('# runtime_stamp='+json.dumps(runtime_stamp, sort_keys=True)+'\n')
        np.savetxt(csv, r, delimiter=',', comments='',
                   header='time_s,cube_x,cube_y,cube_z,hand_relative_x,hand_relative_y,hand_relative_z,thumb_normal_N,index_normal_N,middle_normal_N,support_normal_N,cube_bottom_z,base_displacement_m')
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'fixed_grasp.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result, indent=2), flush=True)
    return 0 if (result['success'] != args.no_grip) else 2


def render(args):
    """Replay saved physical trajectory only for rendering, without resimulation."""
    out = args.out.resolve()
    archive = np.load(out/'trajectory.npz', allow_pickle=False)
    model = mujoco.MjModel.from_xml_path(str(archive['scene']))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=720, width=960)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = [.25, -.10, .85]
    camera.distance, camera.azimuth, camera.elevation = .85, -125, -15
    ffmpeg = args.ffmpeg
    cmd = [ffmpeg, '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
           '-pix_fmt', 'rgb24', '-s', '960x720', '-r', str(FPS), '-i', '-', '-an',
           '-c:v', 'libx264', '-threads', '4', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', str(out/'grasp.mp4')]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i, q in enumerate(archive['qpos']):
            data.qpos[:] = q  # Offline visualization, not the grasp simulation.
            data.qvel[:] = archive['qvel'][i]
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera=camera)
            pixels = renderer.render().copy()
            phase = str(archive['phase'][i])
            mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_150,
                               mujoco.mjtGridPos.mjGRID_TOPLEFT,
                               mujoco.MjrRect(0, 0, 960, 720),
                               f'Fixed-base G1 | {phase}\nTime {i/FPS:.2f} s',
                               'Physical contacts / no object attachment', renderer._mjr_context)
            # Read again after adding the overlay to the same offscreen framebuffer.
            mujoco.mjr_readPixels(pixels, None, mujoco.MjrRect(0, 0, 960, 720), renderer._mjr_context)
            pixels = np.flipud(pixels).copy()
            proc.stdin.write(pixels.tobytes())
            if i in (0, 12*FPS, 18*FPS, 22*FPS):
                subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo',
                                '-pix_fmt', 'rgb24', '-s', '960x720', '-i', '-',
                                '-frames:v', '1', str(out/f'frame_{i:04d}.png')],
                               input=pixels.tobytes(), check=True, timeout=20)
            if i % 100 == 0:
                print(f'render {i}/{len(archive["qpos"])}', flush=True)
    finally:
        proc.stdin.close()
        renderer.close()
    if proc.wait(timeout=20) != 0:
        raise RuntimeError('ffmpeg failed')
    print('VIDEO_READY', out/'grasp.mp4', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--no-grip', action='store_true')
    p.add_argument('--cube-xy', type=float, nargs=2, default=[.267, -.118])
    p.add_argument('--cube-z', type=float, default=.7745)
    p.add_argument('--thumb-close', type=float, default=-.425)
    p.add_argument('--thumb-base-close', type=float, default=-.60)
    p.add_argument('--baseline-mount', action='store_true', default=True)
    p.add_argument('--neutral-mount', action='store_false', dest='baseline_mount')
    p.add_argument('--render', action='store_true')
    p.add_argument('--ffmpeg')
    args = p.parse_args()
    if args.render:
        if not args.ffmpeg:
            p.error('--render requires --ffmpeg')
        render(args)
    else:
        raise SystemExit(simulate(args))
