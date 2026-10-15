#!/usr/bin/env python3
"""P0b ARDY CPU probe (W-ardy, task 20261004-205543-qoder-f5a4a02a).

Loads the text encoder and the G1 denoiser ONCE, times each load, then runs a list of
generation jobs (prompt x seed, optional constraint JSON), saving NPZ + 36-col MuJoCo qpos CSV.
Mirrors the code path of repos/ardy/scripts/generate.py:167-316 but with per-stage timers,
a text-embedding cache and RSS sampling.
"""
import argparse
import json
import os
import resource
import subprocess
import sys
import threading
import time

import numpy as np
import torch

# Task-local resource controls only; model/encoder mathematics are unchanged.
torch.set_num_threads(8)
torch.set_num_interop_threads(1)

os.environ.setdefault("TEXT_ENCODER_MODE", "local")

from ardy.exports.mujoco import MujocoQposConverter          # noqa: E402
from ardy.model import load_model                            # noqa: E402
from ardy.model.load_model import load_text_encoder          # noqa: E402
from ardy.motion_rep.tools import length_to_mask             # noqa: E402
from ardy.constraints import load_constraints_lst            # noqa: E402
from ardy.tools import seed_everything, to_numpy             # noqa: E402

STOP = False


def rss_sampler(out):
    pid = os.getpid()
    for sample_index in range(600):  # <=300s at 0.5s; bounded by external watchdog too
        if STOP:
            break
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        out.append(int(line.split()[1]))  # kB
                        break
        except Exception:
            pass
        time.sleep(0.5)


class CachedEncoder:
    """Wraps the text encoder to prove that each distinct prompt costs one LLM forward."""

    def __init__(self, inner):
        self.inner = inner
        self.cache = {}
        self.encode_seconds = 0.0
        self.calls = 0
        self.hits = 0

    def __call__(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        out = []
        for t in texts:
            self.calls += 1
            if t in self.cache:
                self.hits += 1
                out.append(self.cache[t])
                continue
            t0 = time.perf_counter()
            feat, ln = self.inner([t])
            self.encode_seconds += time.perf_counter() - t0
            self.cache[t] = (feat, ln)
            out.append((feat, ln))
        feats = torch.cat([o[0] for o in out], dim=0)   # each o[0] is (1,1,dim) -> (n,1,dim)
        lengths = [int(l) for o in out for l in np.atleast_1d(o[1])]
        return feats, lengths

    def to(self, *a, **k):
        self.inner = self.inner.to(*a, **k)
        return self

    def eval(self):
        self.inner.eval()
        return self


class LLM2VecAsEncoder:
    """Same __call__ contract as ardy.model.llm2vec.LLM2VecEncoder (llm2vec_wrapper.py:71-101)."""

    def __init__(self, llm2vec, device="cpu"):
        self.inner = llm2vec
        self.device = device
        self.llm_dim = 4096

    def __call__(self, texts):
        with torch.no_grad():
            emb = self.inner.encode(list(texts), batch_size=1, show_progress_bar=False,
                                    device=self.device)
        assert emb.shape[-1] == self.llm_dim, emb.shape
        out = torch.tensor(np.asarray(emb)[:, None]).to(self.device)
        return out, np.ones(len(out), dtype=int).tolist()

    def to(self, *a, **k):
        self.inner = self.inner.to(*a, **k)
        return self

    def eval(self):
        self.inner.eval()
        return self


def build_encoder(mode: str, tex_dir: str, device: str):
    """Rebuild the LLM2Vec encoder from the assets that are actually on disk.

    The ARDY preset (ardy/model/load_model.py:25-26) asks for
    base="McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp" as a *weight* dir, but on this node
    that repo holds only adapter_model.safetensors (169 M) + config.json -> from_pretrained has
    no model.safetensors to load.  So:
      stacked : LlamaBiModel(meta-llama 15 G) + Peft(mntp) merged + Peft(supervised)
      suponly : LlamaBiModel(meta-llama) + Peft(supervised) only        (mntp LoRA skipped)
      preset  : the vendor code path verbatim, expected to raise OSError (recorded, not used)
    """
    import json as _json
    import torch as _torch
    from peft import PeftModel
    from transformers import AutoConfig, AutoTokenizer

    from ardy.model.llm2vec import LLM2Vec
    from ardy.model.llm2vec.models.bidirectional_llama import LlamaBiModel

    META = os.path.join(tex_dir, "meta-llama/Meta-Llama-3-8B-Instruct")
    A_MNTP = os.path.join(tex_dir, "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp")
    A_SUP = os.path.join(tex_dir, "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised")

    if mode == "preset":
        from ardy.model.llm2vec import LLM2VecEncoder
        return LLM2VecEncoder(base_model_name_or_path="McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp",
                              peft_model_name_or_path="McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised",
                              dtype="bfloat16", llm_dim=4096, device="cpu")

    tok = AutoTokenizer.from_pretrained(META)
    tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    AutoConfig.from_pretrained(META)  # warm the config path
    model = LlamaBiModel.from_pretrained(META, torch_dtype=_torch.bfloat16)
    applied = []
    if mode == "stacked":
        model = PeftModel.from_pretrained(model, A_MNTP)
        model = model.merge_and_unload()
        applied.append("mntp(merged)")
    model = PeftModel.from_pretrained(model, A_SUP)
    applied.append("supervised(unmerged)")
    # llm2vec.py:135-139 does this when base ships a config.json; keep the behaviour so that
    # prepare_for_tokenization() picks the Llama-3-Instruct chat prefix.  The local meta-llama
    # config.json has no "_name_or_path" key, while the *intended* base repo
    # (…-mntp/config.json) carries "meta-llama/Meta-Llama-3-8B-Instruct" — so that literal is
    # what the ARDY preset would have produced; without it the Llama-3 user header is silently
    # dropped and every embedding changes.
    with open(os.path.join(META, "config.json")) as f:
        cfg = _json.load(f)
    model.config._name_or_path = cfg.get("_name_or_path") or "meta-llama/Meta-Llama-3-8B-Instruct"
    enc = LLM2Vec(model=model, tokenizer=tok)
    enc = enc.to(device)
    enc.eval()
    for p in enc.parameters():
        p.requires_grad = False
    print(f"[encoder] mode={mode} adapters={applied} _name_or_path={model.config._name_or_path!r}", flush=True)
    return LLM2VecAsEncoder(enc, device=device)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints_dir", required=True)
    ap.add_argument("--model", default="ARDY-G1-RP-25FPS-Horizon52")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--duration", type=float, default=2.0)
    ap.add_argument("--diffusion_steps", type=int, default=None)
    ap.add_argument("--jobs", required=True,
                    help='JSON list: [{"prompt":...,"seed":0,"constraints":null,"stem":"a_s0"}]')
    ap.add_argument("--summary", default=None)
    ap.add_argument("--enc_mode", default="stacked", choices=["stacked", "suponly", "preset"])
    ap.add_argument("--tex_dir", default="/home/group4/group4_dasc7606c/weights/ardy_textenc")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    jobs = json.loads(args.jobs)
    device = "cpu"
    torch.set_grad_enabled(False)

    peak = []
    th = threading.Thread(target=rss_sampler, args=(peak,), daemon=True)
    th.start()

    summary = {"device": device, "torch": torch.__version__, "jobs": []}

    t0 = time.perf_counter()
    enc = CachedEncoder(build_encoder(args.enc_mode, args.tex_dir, device))
    summary["enc_mode"] = args.enc_mode
    t_enc_load = time.perf_counter() - t0
    print(f"[time] text_encoder load = {t_enc_load:.1f} s", flush=True)
    summary["textencoder_load_s"] = round(t_enc_load, 1)
    summary["rss_after_textenc_mib"] = round(max(peak) / 1024, 1) if peak else None

    t1 = time.perf_counter()
    model = load_model(args.model, device=device, text_encoder=enc,
                       checkpoints_dir=args.checkpoints_dir)
    t_model_load = time.perf_counter() - t1
    print(f"[time] model (denoiser+tokenizer) load = {t_model_load:.1f} s", flush=True)
    summary["model_load_s"] = round(t_model_load, 1)
    summary["rss_after_model_mib"] = round(max(peak) / 1024, 1) if peak else None
    summary["peak_rss_mib_to_date"] = round(max(peak) / 1024, 1) if peak else None

    fps = model.motion_rep.fps
    skeleton = model.skeleton
    names = list(getattr(skeleton, "bone_order_names", []))
    info = {
        "fps": float(fps),
        "gen_horizon_len": int(model.gen_horizon_len),
        "num_frames_per_token": int(model.num_frames_per_token),
        "num_base_steps": int(model.diffusion.num_base_steps),
        "skeleton_cls": type(skeleton).__name__,
        "nbjoints": int(skeleton.nbjoints),
        "bone_names": names,
    }
    print("[info] " + json.dumps({k: v for k, v in info.items() if k != "bone_names"}), flush=True)
    summary.update({k: v for k, v in info.items() if k != "bone_names"})
    summary["bone_names"] = names

    patch = model.num_frames_per_token
    num_frames = int(args.duration * fps)
    hist = ((int(10 * fps) // patch) * patch - model.gen_horizon_len) // patch * patch
    diffusion_steps = args.diffusion_steps or int(model.diffusion.num_base_steps)
    if not 1 <= diffusion_steps <= int(model.diffusion.num_base_steps):
        raise SystemExit(f"--diffusion_steps {diffusion_steps} out of range "
                         f"(num_base_steps={int(model.diffusion.num_base_steps)}); "
                         f"ardy_model.py:267 t_map=map_tensor[t] would IndexError")
    print(f"[plan] num_frames={num_frames} history_frames={hist} steps={diffusion_steps}", flush=True)

    conv = MujocoQposConverter(skeleton)

    def find_idx(subs):
        for i, n in enumerate(names):
            ln = n.lower()
            if all(s in ln for s in subs):
                return i
        return None

    wrist_i = find_idx(["right", "wrist_yaw"])
    hand_i = find_idx(["right", "hand"])
    wrist_i = wrist_i if wrist_i is not None else hand_i
    print(f"[skeleton] wrist_idx={wrist_i} name={names[wrist_i] if wrist_i is not None else None} "
          f"hand_idx={hand_i} ee={names[-6:]}", flush=True)
    summary["wrist_bone"] = names[wrist_i] if wrist_i is not None else None

    def to_mujoco(p):
        # ardy (x,y_up,z_fwd) -> mujoco (x_fwd,y_left,z_up)
        return np.asarray([p[..., 2], p[..., 0], p[..., 1]]).swapaxes(-1, 0)

    for job in jobs:
        stem = job["stem"]
        prompt = job["prompt"]
        seed = job.get("seed")
        climit = job.get("constraints")
        if seed is not None:
            seed_everything(int(seed))
        cpath = os.path.join(args.out_dir, stem)
        dur = float(job.get("duration", args.duration))
        num_frames = int(dur * fps)
        observed_motion = motion_mask = None
        t_cond = 0.0
        n_cons = 0
        try:
            constraint_lst = load_constraints_lst(climit, skeleton) if climit else []
            n_cons = len(constraint_lst)
            if constraint_lst:
                tc = time.perf_counter()
                lengths = torch.tensor([num_frames], device=device)
                observed_motion, motion_mask = model.motion_rep.create_conditions_from_constraints_batched(
                    constraint_lst, lengths, to_normalize=True, device=device)
                t_cond = time.perf_counter() - tc
                print(f"[cond] {stem}: {len(constraint_lst)} sets, "
                      f"{[type(c).__name__ for c in constraint_lst]}, "
                      f"frames {[c.frame_indices.tolist() for c in constraint_lst]}", flush=True)
            else:
                lengths = torch.tensor([num_frames], device=device)
        except Exception as e:
            rec = {"stem": stem, "prompt": prompt, "seed": seed, "duration_s": dur,
                   "num_frames": num_frames, "constraints": climit,
                   "error": f"constraint stage: {type(e).__name__}: {e}"}
            print("[job-fail] " + json.dumps(rec), flush=True)
            summary["jobs"].append(rec)
            continue

        pad_mask = length_to_mask(lengths)
        first_heading_angle = torch.zeros(1, device=device)
        enc_before, sec_before, calls_before = len(enc.cache), enc.encode_seconds, enc.calls
        t2 = time.perf_counter()
        try:
            motion = model([prompt], num_frames, num_denoising_steps=diffusion_steps,
                           pad_mask=pad_mask, first_heading_angle=first_heading_angle,
                           motion_mask=motion_mask, observed_motion=observed_motion,
                           cfg_weight=tuple(job.get('cfg_weight', [2.0, 2.0])), crop_history_length=hist)
            output = model.motion_rep.inverse(motion, is_normalized=True)
        except Exception as e:
            rec = {"stem": stem, "prompt": prompt, "seed": seed, "duration_s": dur,
                   "num_frames": num_frames, "constraints": bool(climit),
                   "wall_s": round(time.perf_counter() - t2, 2),
                   "error": f"{type(e).__name__}: {e}"}
            print("[job-fail] " + json.dumps(rec), flush=True)
            summary["jobs"].append(rec)
            continue
        t_total = time.perf_counter() - t2
        new_embeds = len(enc.cache) - enc_before
        t_encode = sec_before - enc.encode_seconds
        t_encode = -t_encode if t_encode else 0.0
        encode_calls = enc.calls - calls_before
        output = to_numpy(output)
        qpos = conv.dict_to_qpos(output, device)
        qpos = np.asarray(qpos)
        if qpos.ndim == 3:
            qpos = qpos[0]
        arrays = {k: np.asarray(v) for k, v in output.items()}
        # mirror generate.py:151-156 _select_sample so the NPZ is un-batched like upstream's
        arrays = {k: (v[0] if v.ndim > 0 and v.shape[0] == 1 else v) for k, v in arrays.items()}
        arrays["fps"] = np.asarray(fps)
        arrays["text"] = np.asarray(prompt)
        np.savez(cpath + ".npz", **arrays)
        np.savetxt(cpath + ".csv", qpos, delimiter=",")
        rec = {
            "stem": stem, "prompt": prompt, "seed": seed,
            "duration_s": dur, "num_frames": num_frames,
            "constraints": bool(climit), "n_constraints": n_cons,
            "wall_s": round(t_total, 2),
            "text_encode_s": round(t_encode, 2), "encode_calls": int(encode_calls),
            "new_embeds": int(new_embeds), "cond_s": round(t_cond, 2),
            "qpos_shape": list(qpos.shape),
            "cfg_weight": job.get('cfg_weight', [2.0, 2.0]),
            "peak_rss_mib": round(max(peak) / 1024, 1) if peak else None,
        }
        try:
            pj = np.asarray(output["posed_joints"])[0]        # (T,J,3) ARDY frame (y up, z fwd)
            root = qpos[:, :3]
            rec["root_final_xyz"] = [round(float(v), 4) for v in root[-1]]
            rec["root_z_min_max"] = [round(float(root[:, 2].min()), 4), round(float(root[:, 2].max()), 4)]
            if wrist_i is not None and pj.ndim == 3 and pj.shape[1] > wrist_i:
                w = to_mujoco(pj[:, wrist_i, :])              # (T,3) MuJoCo frame
                rel = w - root
                rec["wrist_final_xyz"] = [round(float(v), 4) for v in w[-1]]
                rec["wrist_rel_final_xyz"] = [round(float(v), 4) for v in rel[-1]]
                rec["wrist_rel_best_xyz"] = [round(float(v), 4) for v in rel[np.argmax(rel[:, 0])]]
                rec["wrist_rel_max_forward"] = round(float(rel[:, 0].max()), 4)
                rec["wrist_z_min_max"] = [round(float(w[:, 2].min()), 4), round(float(w[:, 2].max()), 4)]
                rec["wrist_z_last5"] = [round(float(v), 4) for v in w[-5:, 2]]
        except Exception as e:
            rec["wrist_stat_err"] = f"{type(e).__name__}: {e}"
        print("[job] " + json.dumps(rec), flush=True)
        summary["jobs"].append(rec)

    STOP = True
    summary["peak_rss_mib_final"] = round(max(peak) / 1024, 1) if peak else None
    summary["rss_samples"] = len(peak)
    ru = resource.getrusage(resource.RUSAGE_SELF)
    summary["ru_maxrss_mib"] = round(ru.ru_maxrss / 1024, 1)
    summary["ru_utime_s"] = round(ru.ru_utime, 1)
    summary["ru_stime_s"] = round(ru.ru_stime, 1)
    print("[final] " + json.dumps({k: v for k, v in summary.items()
                                   if k not in ("bone_names", "jobs")}), flush=True)
    if args.summary:
        with open(args.summary, "w") as f:
            json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
