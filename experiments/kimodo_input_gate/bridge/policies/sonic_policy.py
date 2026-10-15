import numpy as np
import torch
import torch.nn as nn


def build_mlp(layer_dims, activation=nn.SiLU):
    layers = []
    for i in range(len(layer_dims) - 1):
        in_dim = layer_dims[i]
        out_dim = layer_dims[i + 1]
        layers.append(nn.Linear(in_dim, out_dim))
        if i < len(layer_dims) - 2:
            layers.append(activation())
    return nn.Sequential(*layers)


class SonicActorModule(nn.Module):
    def __init__(self):
        super().__init__()

        # 根据 checkpoint 结构确认：
        # g1:     640 -> 2048 -> 1024 -> 512 -> 512 -> 64
        # teleop: 267 -> 2048 -> 1024 -> 512 -> 512 -> 64
        # smpl:   840 -> 2048 -> 1024 -> 512 -> 512 -> 64
        self.encoders = nn.ModuleDict({
            "g1": build_mlp([640, 2048, 1024, 512, 512, 64]),
            "teleop": build_mlp([267, 2048, 1024, 512, 512, 64]),
            "smpl": build_mlp([840, 2048, 1024, 512, 512, 64]),
        })

        # 根据 checkpoint 结构确认：
        # g1_dyn: 994 -> 2048 -> 2048 -> 1024 -> 1024 -> 512 -> 512 -> 29
        # g1_kin: 64  -> 2048 -> 1024 -> 512 -> 512 -> 640
        self.decoders = nn.ModuleDict({
            "g1_dyn": build_mlp([994, 2048, 2048, 1024, 1024, 512, 512, 29]),
            "g1_kin": build_mlp([64, 2048, 1024, 512, 512, 640]),
        })

    def encode(self, mode, encoder_obs):
        return self.encoders[mode](encoder_obs)

    def decode(self, decoder_type, decoder_input):
        return self.decoders[decoder_type](decoder_input)


class SonicPolicy:
    def __init__(self, cfg):
        self.cfg = cfg

        requested_device = cfg["policy"].get("device", "cpu")
        if requested_device == "cuda" and not torch.cuda.is_available():
            print("[WARN] cuda requested but not available, falling back to cpu")
            requested_device = "cpu"
        self.device = torch.device(requested_device)

        self.encoder_mode = cfg["observation"].get("mode", "g1")
        self.decoder_type = cfg["policy"].get("decoder_type", "g1_dyn")
        self.checkpoint = cfg["policy"]["checkpoint"]

        self.actor = SonicActorModule().to(self.device)
        self.actor.eval()

        self.action_std = None

        self._load_policy_state_dict()

    def _remap_state_dict_keys(self, sd):
        new_sd = {}
        for k, v in sd.items():
            if k == "std":
                continue

            nk = k
            nk = nk.replace("actor_module.encoders.", "encoders.")
            nk = nk.replace("actor_module.decoders.", "decoders.")
            nk = nk.replace(".module.", ".")
            new_sd[nk] = v
        return new_sd

    def _load_policy_state_dict(self):
        print(f"[INFO] loading policy checkpoint: {self.checkpoint}")
        sd = torch.load(self.checkpoint, map_location=self.device)

        if "std" in sd:
            self.action_std = sd["std"].detach().cpu().numpy()
            print(f"[INFO] loaded action std shape={self.action_std.shape}")

        remapped_sd = self._remap_state_dict_keys(sd)

        missing, unexpected = self.actor.load_state_dict(
            remapped_sd,
            strict=False,
        )

        print(f"[INFO] load_state_dict missing keys: {missing}")
        print(f"[INFO] load_state_dict unexpected keys: {unexpected}")

    @torch.no_grad()
    def encode(self, encoder_obs):
        if not isinstance(encoder_obs, dict):
            raise TypeError(f"encoder_obs must be dict, got {type(encoder_obs)}")

        required_keys = [
            "motion_joint_velocities_10frame_step5",
            "motion_joint_positions_10frame_step5",
            "motion_anchor_orientation_10frame_step5",
        ]
        for k in required_keys:
            if k not in encoder_obs:
                raise KeyError(f"missing encoder_obs key: {k}")

        parts = [
            np.asarray(encoder_obs[k], dtype=np.float32).reshape(-1)
            for k in required_keys
        ]

        x = np.concatenate(parts, axis=0).astype(np.float32)

        if x.shape[0] != 640:
            raise ValueError(f"g1 encoder input dim must be 640, got {x.shape[0]}")

        x = torch.from_numpy(x.reshape(1, -1)).to(self.device)

        token = self.actor.encode(self.encoder_mode, x)
        token = token.squeeze(0).detach().cpu().numpy().astype(np.float32)
        return token

    @torch.no_grad()
    def act(self, policy_obs, token_state=None):
        # 注意：当前 checkpoint 的 g1_dyn 直接吃 994 维输入。
        # 这里默认 policy_obs 已经包含 token_state(64) + 930 维历史状态 = 994。
        policy_obs = np.asarray(policy_obs, dtype=np.float32).reshape(-1)

        if self.decoder_type == "g1_dyn":
            if policy_obs.shape[0] != 994:
                raise ValueError(f"g1_dyn input dim must be 994, got {policy_obs.shape[0]}")
            decoder_in = policy_obs

        elif self.decoder_type == "g1_kin":
            if token_state is None:
                raise ValueError("token_state must be provided when decoder_type is g1_kin")
            token_state = np.asarray(token_state, dtype=np.float32).reshape(-1)
            print(f"[DEBUG] token_state dim={token_state.shape[0]}")
            if token_state.shape[0] != 64:
                raise ValueError(f"g1_kin input dim must be 64, got {token_state.shape[0]}")
            decoder_in = token_state

        else:
            raise ValueError(f"unsupported decoder_type: {self.decoder_type}")

        decoder_in = torch.from_numpy(decoder_in.reshape(1, -1)).to(self.device)

        action = self.actor.decode(self.decoder_type, decoder_in)
        action = action.squeeze(0).detach().cpu().numpy().astype(np.float32)

        return action