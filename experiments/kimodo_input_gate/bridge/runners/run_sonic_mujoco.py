import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
import numpy as np

try:
    import mujoco
    import mujoco.viewer
except ImportError as e:
    raise RuntimeError("缺少 mujoco，请先安装 MuJoCo Python 依赖") from e

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    add_motion_arguments(parser)
    args = parser.parse_args()

    cfg = load_config(args.config)

    xml_path = cfg["robot"]["mujoco_xml"]
    if not Path(xml_path).exists():
        raise FileNotFoundError(f"MuJoCo XML 不存在: {xml_path}")

    model = mujoco.MjModel.from_xml_path(xml_path)
    data = mujoco.MjData(model)

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

    print("[INFO] Sonic MuJoCo runner started")
    print(f"[INFO] control_every = {control_every}")
    if motion_runtime is None:
        print("[INFO] motion_source=static")
    else:
        print(f"[INFO] {motion_runtime.startup_log_line()}")

    step = 0
    last_action = np.zeros(action_adapter.action_dim, dtype=np.float32)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            if step % control_every == 0:
                encoder_obs = encoder_adapter.build(data)
                token_state = policy.encode(encoder_obs)

                policy_obs, policy_debug = policy_adapter.build(data, token_state, last_action)
                action = policy.act(policy_obs, token_state=token_state)

                action_adapter.set_action(action)
                last_action = action.copy()

                if cfg["debug"]["print_shapes"] and step % (
                    cfg["debug"]["print_every_n_steps"] * control_every
                ) == 0:
                    print(f"[DEBUG] step={step}")
                    print(
                        f"[DEBUG] encoder {encoder_adapter.window_log_line()}"
                    )
                    print(f"[DEBUG] token_state shape={token_state.shape}")
                    print(f"[DEBUG] policy_obs shape={policy_obs.shape}")
                    print(f"[DEBUG] action shape={action.shape}")
                    print(f"[DEBUG] action[:5]={action[:5]}")
                    print(f"[DEBUG] base z={data.qpos[2]:.4f}")

            action_adapter.step_pd(data)
            mujoco.mj_step(model, data)
            viewer.sync()
            step += 1


if __name__ == "__main__":
    main()
