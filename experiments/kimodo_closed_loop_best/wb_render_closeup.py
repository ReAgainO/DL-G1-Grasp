#!/usr/bin/env python
"""Close-up render of a harness cell, camera tracking the cube/hand.

Reads ONLY recorded poses. Writes key-phase PNGs + an MP4.

Usage: wb_render_closeup.py <cell_dir> <out_dir> [--stride N] [--width W] [--height H]
"""
import argparse, json, os, subprocess
from pathlib import Path
import numpy as np
import mujoco

FF = "/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cell"); ap.add_argument("outdir")
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    cell = Path(a.cell); out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    z = np.load(cell / "trajectory.npz", allow_pickle=True)
    res = json.loads((cell / "result.json").read_text())
    gates = res["gates"]; ok = sum(1 for v in gates.values() if v)
    m = mujoco.MjModel.from_xml_path(str(cell / "scene.xml"))
    d = mujoco.MjData(m)
    cube = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "red_cube")
    wrist = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")

    W, H = a.width, a.height
    renderer = mujoco.Renderer(m, height=H, width=W)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.distance = 0.45
    cam.azimuth = -150
    cam.elevation = -20

    frames = out / "frames"; frames.mkdir(exist_ok=True)
    phase = [str(p) for p in z["phase"]]
    qpos = z["qpos"]; qvel = z["qvel"]; t = z["time"]
    stride = a.stride; fps = 25.0 / stride

    # track the midpoint of cube and wrist so both stay in frame
    look = np.zeros((len(qpos), 3))
    for i in range(len(qpos)):
        d.qpos[:] = qpos[i]
        mujoco.mj_forward(m, d)
        look[i] = 0.5 * (d.xpos[cube] + d.xpos[wrist]) + np.array([0, 0, 0.03])

    mp4 = out / "grasp_closeup.mp4"
    proc = subprocess.Popen([FF, "-v", "error", "-nostdin", "-y", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{fps}", "-i", "-",
                             "-an", "-c:v", "libx264", "-threads", "4", "-crf", "20",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
                            stdin=subprocess.PIPE)
    keys = {}
    for ph in ["APPROACH", "PREGRASP", "DESCEND", "CLOSE", "LIFT", "HOLD", "RELEASE"]:
        ix = np.flatnonzero(np.asarray(phase) == ph)
        if len(ix):
            keys[int(ix[len(ix) // 2])] = ph

    n = 0
    try:
        for i in range(0, len(qpos), stride):
            d.qpos[:] = qpos[i]; d.qvel[:] = qvel[i]
            mujoco.mj_forward(m, d)
            cam.lookat[:] = look[i]
            renderer.update_scene(d, camera=cam)
            renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
            renderer.render()
            mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100, mujoco.mjtGridPos.mjGRID_TOPLEFT,
                               mujoco.MjrRect(0, 40, W, H), f"{a.label}",
                               f"{phase[i]} | t={t[i]:.2f}s | gates {ok}/{len(gates)} | cube z={d.xpos[cube][2]:.3f}",
                               renderer._mjr_context)
            buf = np.empty((H, W, 3), dtype=np.uint8)
            mujoco.mjr_readPixels(buf, None, mujoco.MjrRect(0, 0, W, H), renderer._mjr_context)
            frame = np.flipud(buf).copy()
            proc.stdin.write(frame.tobytes()); n += 1
            if i in keys:
                subprocess.run([FF, "-v", "error", "-nostdin", "-y", "-f", "rawvideo",
                                "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-i", "-", "-frames:v", "1",
                                str(frames / f"key_{keys[i]}_f{i:05d}.png")],
                               input=frame.tobytes(), check=True, timeout=30)
            if i % (stride * 50) == 0:
                print(f"render {i}/{len(qpos)}", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        renderer.close()
    assert proc.wait(timeout=30) == 0
    print("FRAMES", n, "MP4", mp4, flush=True)


if __name__ == "__main__":
    main()
