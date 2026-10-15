import argparse
import importlib
import sys
import types
from collections import defaultdict

import torch


def patch_trl_online_trainer_state():
    try:
        trl_utils = importlib.import_module("trl.trainer.utils")
        if not hasattr(trl_utils, "OnlineTrainerState"):
            class OnlineTrainerState:
                pass
            trl_utils.OnlineTrainerState = OnlineTrainerState
            print("[INFO] patched missing trl.trainer.utils.OnlineTrainerState")
    except Exception as e:
        print(f"[WARN] failed to patch trl.trainer.utils: {e}")


def patch_trl_ppo_config_module():
    module_name = "trl.trainer.ppo_config"
    if module_name not in sys.modules:
        fake_mod = types.ModuleType(module_name)

        class PPOConfig:
            pass

        fake_mod.PPOConfig = PPOConfig
        sys.modules[module_name] = fake_mod
        print("[INFO] patched missing module trl.trainer.ppo_config with PPOConfig")


def group_shapes(state_dict, prefixes):
    grouped = defaultdict(list)
    for k, v in state_dict.items():
        if not hasattr(v, "shape"):
            continue
        for prefix in prefixes:
            if k.startswith(prefix):
                grouped[prefix].append((k, tuple(v.shape)))
    return grouped


def print_grouped_shapes(grouped):
    for prefix, items in grouped.items():
        print(f"\n[INFO] {prefix}")
        for k, shape in items:
            print(f"  {k}: {shape}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", type=str, required=True)
    parser.add_argument("--save-policy", type=str, default="policy_state_dict.pt")
    args = parser.parse_args()

    print(f"[INFO] loading checkpoint: {args.ckpt}")

    patch_trl_online_trainer_state()
    patch_trl_ppo_config_module()

    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)

    if not isinstance(ckpt, dict):
        print(f"[ERROR] checkpoint is not a dict, got: {type(ckpt)}")
        return

    print("\n[INFO] top-level keys:")
    print(list(ckpt.keys()))

    if "policy_state_dict" not in ckpt:
        print("[ERROR] policy_state_dict not found")
        return

    policy_sd = ckpt["policy_state_dict"]

    print(f"\n[INFO] policy_state_dict keys: {len(policy_sd)}")
    print("[INFO] first 100 keys:")
    for i, k in enumerate(policy_sd.keys()):
        if i >= 100:
            break
        v = policy_sd[k]
        shape = tuple(v.shape) if hasattr(v, "shape") else type(v)
        print(f"  {k}: {shape}")

    prefixes = [
        "actor_module.encoders.g1.",
        "actor_module.encoders.teleop.",
        "actor_module.encoders.smpl.",
        "actor_module.decoders.g1_dyn.",
        "actor_module.decoders.g1_kin.",
    ]
    grouped = group_shapes(policy_sd, prefixes)
    print_grouped_shapes(grouped)

    if "std" in policy_sd:
        print(f"\n[INFO] action std shape: {tuple(policy_sd['std'].shape)}")

    torch.save(policy_sd, args.save_policy)
    print(f"\n[INFO] saved clean policy_state_dict to: {args.save_policy}")


if __name__ == "__main__":
    main()