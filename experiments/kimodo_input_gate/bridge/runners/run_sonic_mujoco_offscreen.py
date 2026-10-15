import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
import numpy as np

try:
    import mujoco
except ImportError as e:
    raise RuntimeError("缺少 mujoco，请先安装 MuJoCo Python 依赖") from e

try:
    from PIL import Image
except ImportError as e:
    raise RuntimeError("缺少 Pillow，请先安装：python -m pip install Pillow") from e

from adapters.sonic_encoder_adapter import SonicEncoderAdapter
from adapters.sonic_policy_adapter import SonicPolicyAdapter
from adapters.sonic_action_adapter import (
    SonicActionAdapter,
    DEFAULT_ANGLES,
    STAND_INIT_HEIGHT,
)
from motion_adapter import (
    add_motion_arguments,
    load_motion_runtime,
    quaternion_yaw,
)
from policies.sonic_policy import SonicPolicy


def load_config(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_frame(renderer, data, out_dir: Path, frame_idx: int):
    renderer.update_scene(data)
    pixels = renderer.render()
    img = Image.fromarray(pixels)
    out_path = out_dir / f"frame_{frame_idx:06d}.png"
    img.save(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--max_steps", type=int, default=2000)
    parser.add_argument("--render_every", type=int, default=20)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--out_dir", type=str, default="renders")
    add_motion_arguments(parser)
    args = parser.parse_args()

    cfg = load_config(args.config)

    xml_path = cfg["robot"]["mujoco_xml"]
    if not Path(xml_path).exists():
        raise FileNotFoundError(f"MuJoCo XML 不存在: {xml_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = mujoco.MjModel.from_xml_path(xml_path)
    data = mujoco.MjData(model)

    renderer = mujoco.Renderer(model, height=args.height, width=args.width)

    sim_dt = cfg["control"]["sim_dt"]
    policy_hz = cfg["control"]["policy_hz"]
    control_every = max(1, int(round((1.0 / policy_hz) / sim_dt)))

    # 初始位姿：default 蹲姿，双脚恰好接触地面
    data.qpos[0:3] = [0.0, 0.0, STAND_INIT_HEIGHT]
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    data.qpos[7:] = DEFAULT_ANGLES
    mujoco.mj_forward(model, data)

    try:
        motion_runtime = load_motion_runtime(
            args,
            target_fps=policy_hz,
            target_root_pos=data.qpos[:3],
            target_heading=quaternion_yaw(data.qpos[3:7]),
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    policy = SonicPolicy(cfg)
    encoder_adapter = SonicEncoderAdapter(
        cfg,
        trajectory=(
            motion_runtime.trajectory if motion_runtime is not None else None
        ),
        motion_start=(
            motion_runtime.motion_start if motion_runtime is not None else 0.0
        ),
        motion_speed=(
            motion_runtime.motion_speed if motion_runtime is not None else 1.0
        ),
    )
    policy_adapter = SonicPolicyAdapter(cfg, model)
    action_adapter = SonicActionAdapter(cfg, model)

    print("[INFO] Sonic MuJoCo offscreen runner started")
    print(f"[INFO] control_every = {control_every}")
    print(f"[INFO] max_steps = {args.max_steps}")
    print(f"[INFO] render_every = {args.render_every}")
    print(f"[INFO] output_dir = {out_dir.resolve()}")
    if motion_runtime is None:
        print("[INFO] motion_source=static")
    else:
        print(f"[INFO] {motion_runtime.startup_log_line()}")

    step = 0
    frame_idx = 0
    last_action = np.zeros(action_adapter.action_dim, dtype=np.float32)

    while step < args.max_steps:
        if step % control_every == 0:
            encoder_obs = encoder_adapter.build(data)
            token_state = policy.encode(encoder_obs)

            policy_obs, policy_debug = policy_adapter.build(data, token_state, last_action)
            action = policy.act(policy_obs, token_state=token_state)

            if not np.isfinite(action).all():
                raise ValueError(f"action has NaN/Inf at step={step}: {action}")

            action_adapter.set_action(action)
            last_action = action.copy()

            if cfg["debug"]["print_shapes"] and step % (
                cfg["debug"]["print_every_n_steps"] * control_every
            ) == 0:
                base_height = float(np.asarray(data.qpos)[2]) if len(data.qpos) > 2 else float("nan")

                print(f"[DEBUG] step={step}")
                print(
                    f"[DEBUG] encoder {encoder_adapter.window_log_line()}"
                )
                print(f"[DEBUG] token_state shape={token_state.shape}")
                print(f"[DEBUG] policy_obs shape={policy_obs.shape}")
                print(f"[DEBUG] action shape={action.shape}")
                print(f"[DEBUG] action min={action.min():.4f}, max={action.max():.4f}, mean={action.mean():.4f}")
                print(f"[DEBUG] base height={base_height:.6f}")

        action_adapter.step_pd(data)
        mujoco.mj_step(model, data)

        if not np.isfinite(data.qpos).all():
            raise ValueError(f"qpos has NaN/Inf at step={step}")
        if not np.isfinite(data.qvel).all():
            raise ValueError(f"qvel has NaN/Inf at step={step}")

        if step % args.render_every == 0:
            out_path = save_frame(renderer, data, out_dir, frame_idx)
            if frame_idx % 10 == 0:
                print(f"[INFO] saved frame {frame_idx} -> {out_path}")
            frame_idx += 1

        step += 1

    print("[INFO] finished offscreen simulation")
    print(f"[INFO] total frames saved = {frame_idx}")
    print(f"[INFO] frames directory = {out_dir.resolve()}")


if __name__ == "__main__":
    main()
