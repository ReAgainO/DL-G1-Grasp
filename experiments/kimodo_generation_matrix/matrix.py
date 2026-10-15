#!/usr/bin/env python3
"""x04_matrix.py -- KIMODO generation-layer matrix driver.

Runs one official-CLI generation per cell (via runlim.py wrapper) and appends to gen_manifest.csv.
Default device=cpu (MUSA_VISIBLE_DEVICES=-1) because GPU4 is memory-constrained by VLLM.

Cell layout per task card:
  K-M0 x 8 : 4 prompt (P0/P2/P3/P5) x 2 seed (0/1), arm C, cfg_type separated 2.0/2.0, dur 4.0, steps 100
  K-M1 x 4 : 4 prompt x seed 0, arm U (no constraint), same cfg
  K-cfg0 x 2 : P0/P3 x seed 0, cfg_type separated 0.0/2.0 (text weight ablated), arm C
  K-HIST x 1 : historical v5_f83_87_cw15 (dur 7.0, seed 0, text_weight 2.0, constraint_weight 1.5)
  K-C1 x 1   : re-run of K_M0_P0_s0 same params for determinism check
  K-DS10 x 1 : P0/s0/arm C at diffusion_steps=10 (KIMODO step-diff sample)
Total: 16 cells.
"""
import argparse, csv, hashlib, json, os, re, shutil, subprocess, sys, time

B = "/home/group4/group4_dasc7606c"
T = "20261006-045000-qoder-x04kimodo"
D = "/data/group4/" + T
PROTOCOL = B + "/work/" + T + "/EXP_PROTOCOL.md"
PY = B + "/envs/kimodo/bin/python"
GEN = B + "/repos/kimodo/kimodo/scripts/generate.py"
RUNLIM = D + "/scripts_runlim.py"
KIMODO_REPO = B + "/repos/kimodo"
GEN_DIR = D + "/gen"
CSTR_DIR = D + "/constraints"
EX_DIR = D + "/save_example"
LOG_DIR = D + "/logs"
MANIFEST = D + "/gen_manifest.csv"

CUBE = (0.267, -0.118, 0.7745)
FPS_K = 30.0
DUR = 4.0
STEPS = 100
CFRAME = 40
MODEL = "kimodo-g1-rp"

COLS = ["cell_id","model","prompt_id","prompt_text","prompt_sha256","seed","arm",
        "cfg_type","cfg_text","cfg_constr","diffusion_steps","duration_s","device","threads",
        "fps","frames","cols","csv_sha256","wall_s","maxrss_kb","constraint_sha256",
        "print_cmd","root_z_lo","root_z_hi","lim_cells_beyond_tol","base_table_overlap_frames",
        "loader","save_example_dir","notes"]

def sha256_file(p, chunk=1<<20):
    h = hashlib.sha256()
    with open(p,"rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def sha256_text(s):
    return hashlib.sha256(s.encode()).hexdigest()

def load_prompts():
    with open(PROTOCOL, encoding="utf-8") as fh:
        txt = fh.read()
    out = {}
    for m in re.finditer(r"^\|\s*(P[0-5])\s*\|\s*`([^`]+)`\s*\|", txt, re.M):
        out[m.group(1)] = m.group(2)
    for p in ["P0","P2","P3","P5"]:
        if p not in out:
            raise RuntimeError("protocol missing prompt " + p)
    return out

def env_for(device="cpu", nthreads=32):
    e = dict(os.environ)
    rootfs = B + "/musa_rootfs"
    dp = rootfs + "/usr/local/lib/python3.10/dist-packages"
    musa_home = rootfs + "/usr/local/musa"
    e["MUSA_HOME"] = musa_home
    e["TORCH_MUSA_ARCH_LIST"] = "22"
    e["LD_LIBRARY_PATH"] = ":".join([musa_home+"/lib", dp+"/torch_musa/lib", dp+"/torch/lib",
                                     rootfs+"/usr/local/openmpi/lib",
                                     rootfs+"/opt/intel/oneapi/mkl/lib/intel64"])
    e["PATH"] = ":".join([musa_home+"/bin", musa_home+"/mudnn/bin", rootfs+"/usr/local/bin",
                          rootfs+"/usr/local/openmpi/bin", "/usr/bin", "/bin"])
    e["PYTHONPATH"] = B + "/envs/kimodo/lib/python3.10/site-packages:" + dp + ":" + KIMODO_REPO
    e["CHECKPOINT_DIR"] = B + "/weights/kimodo"
    e["TEXT_ENCODERS_DIR"] = B + "/work/kimodo/textenc"
    e["TEXT_ENCODER_MODE"] = "local"
    e["HF_HUB_OFFLINE"] = "1"
    e["TRANSFORMERS_OFFLINE"] = "1"
    e["TOKENIZERS_PARALLELISM"] = "false"
    e["HOME"] = D + "/tmp"
    e["TMPDIR"] = D + "/tmp"
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e["X04_RLIMIT_AS_GIB"] = "48"
    if device == "cpu":
        e["MUSA_VISIBLE_DEVICES"] = "-1"
        for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS"):
            e[k] = str(nthreads)
    else:
        e["MUSA_VISIBLE_DEVICES"] = os.environ.get("X04_MUSA_DEVICE","4")
        for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS"):
            e[k] = "8"
    return e

def q(s):
    """Quote a shell argument by wrapping in single quotes; escape inner single quotes as '\\'.'\\'"""
    return "'" + s.replace("'","'\\''") + "'"

def build_argv(prompt, output_stem, seed, cfg_type, cfg_text, cfg_constr, steps, dur,
               constraints_path=None, use_input_folder=False):
    argv = [PY, GEN]
    if use_input_folder:
        argv += ["ignored", "--model", MODEL, "--input_folder",
                 os.path.dirname(constraints_path), "--output", output_stem]
    else:
        argv += [prompt, "--model", MODEL, "--duration", str(dur), "--num_samples", "1",
                 "--seed", str(seed), "--diffusion_steps", str(steps),
                 "--save_example_dir",
                 "--output", output_stem]
        if constraints_path:
            argv += ["--constraints", constraints_path]
        if cfg_type == "nocfg":
            argv += ["--cfg_type", "nocfg"]
        elif cfg_type == "regular":
            argv += ["--cfg_type", "regular", "--cfg_weight", str(cfg_text)]
        elif cfg_type == "separated":
            argv += ["--cfg_type", "separated", "--cfg_weight", str(cfg_text), str(cfg_constr)]
    return argv

def run_cell(cell_id, prompt_id, prompt_text, seed, arm, cfg_type, cfg_text, cfg_constr,
             steps, dur, device, threads, constraints_path=None, use_input_folder=False):
    os.makedirs(GEN_DIR, exist_ok=True)
    os.makedirs(EX_DIR, exist_ok=True)
    stem = GEN_DIR + "/" + cell_id
    for suffix in [".npz", ".csv"]:
        p = stem + suffix
        if os.path.exists(p):
            os.remove(p)
    exd = stem + "_example"
    if os.path.isdir(exd):
        shutil.rmtree(exd)
    argv = build_argv(prompt_text, stem, seed, cfg_type, cfg_text, cfg_constr, steps, dur,
                      constraints_path, use_input_folder)
    printable = "X04_RLIMIT_AS_GIB=48 " + " ".join(q(x) for x in argv)
    logp = LOG_DIR + "/" + cell_id + ".log"
    env = env_for(device, threads)
    full = [PY, RUNLIM, logp] + argv
    t0 = time.time()
    try:
        p = subprocess.run(full, env=env, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        p = None
    wall = round(time.time() - t0, 2)
    if p is None:
        info = {"rc":124,"wall_s":wall,"maxrss_kb":-1,"rlimit_as_gib":48.0}
    else:
        try:
            info = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            info = {"rc":p.returncode,"wall_s":wall,"maxrss_kb":-1,"rlimit_as_gib":48.0}
    row = {"cell_id":cell_id,"model":"kimodo","prompt_id":prompt_id,
           "prompt_text":prompt_text,"prompt_sha256":sha256_text(prompt_text),
           "seed":seed,"arm":arm,"cfg_type":cfg_type,"cfg_text":cfg_text,"cfg_constr":cfg_constr,
           "diffusion_steps":steps,"duration_s":dur,"device":device,"threads":threads,
           "fps":FPS_K,
           "frames":"NA","cols":"NA","csv_sha256":"NA",
           "wall_s":info.get("wall_s",wall),"maxrss_kb":info.get("maxrss_kb","NA"),
           "constraint_sha256":sha256_file(constraints_path) if constraints_path else "NA",
           "print_cmd":printable,"root_z_lo":"NA","root_z_hi":"NA",
           "lim_cells_beyond_tol":"NA","base_table_overlap_frames":"NA",
           "loader":"official_cli",
           "save_example_dir": exd if not use_input_folder else
                               (os.path.dirname(constraints_path) if constraints_path else "NA"),
           "notes":"rc=" + str(info.get("rc")) + "; rlimit_as_gib=" + str(info.get("rlimit_as_gib"))}
    csvp = stem + ".csv"
    if os.path.exists(csvp):
        row["csv_sha256"] = sha256_file(csvp)
        with open(csvp) as fh:
            lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
        row["frames"] = len(lines)
        row["cols"] = len(lines[0].split(",")) if lines else 0
        try:
            z = [float(ln.split(",")[2]) for ln in lines]
            row["root_z_lo"] = round(min(z),4)
            row["root_z_hi"] = round(max(z),4)
        except Exception:
            pass
        expected = int(dur*FPS_K)
        if row["frames"] != expected:
            row["notes"] += "; FRAMES_DIFF expected=" + str(expected) + " got=" + str(row["frames"])
        if row["cols"] != 36:
            row["notes"] += "; COLS_DIFF expected=36 got=" + str(row["cols"])
        if os.path.isdir(exd):
            target = EX_DIR + "/" + cell_id
            if os.path.isdir(target):
                shutil.rmtree(target)
            shutil.copytree(exd, target)
            row["save_example_dir"] = target
    else:
        row["notes"] += "; NO_CSV"
        try:
            errtail = open(logp).read()[-800:]
            row["notes"] += "; log_tail=" + errtail[:400].replace("\n"," ")
        except Exception:
            pass
    return row

def append_manifest(row):
    newfile = not os.path.exists(MANIFEST)
    with open(MANIFEST,"a",newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
        if newfile:
            w.writeheader()
        w.writerow(row)

HIST_TXT = "A person walks forward, squats down and grabs an object from the ground with their right hand, then stands up and lifts it high."

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", default="all")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    prompts = load_prompts()
    P0,P2,P3,P5 = prompts["P0"],prompts["P2"],prompts["P3"],prompts["P5"]
    cells = []
    if a.cell in ("all","K_HIST"):
        cells.append(("K_HIST","HIST",HIST_TXT,0,"C","separated",2.0,1.5,100,7.0,
                      D+"/save_example/K_HIST/constraints.json",True))
    if a.cell in ("all","K_M1"):
        for pid,p in [("P0",P0),("P2",P2),("P3",P3),("P5",P5)]:
            cells.append(("K_M1_"+pid+"_s0",pid,p,0,"U","separated",2.0,2.0,100,4.0,None,False))
    if a.cell in ("all","K_M0"):
        for pid,p in [("P0",P0),("P2",P2),("P3",P3),("P5",P5)]:
            for s in (0,1):
                cid = "K_M0_"+pid+"_s"+str(s)
                cells.append((cid,pid,p,s,"C","separated",2.0,2.0,100,4.0,
                              D+"/constraints/"+pid+"_s"+str(s)+"_c.json",False))
    if a.cell in ("all","K_CFG0"):
        for pid,p in [("P0",P0),("P3",P3)]:
            cells.append(("K_CFG0_"+pid+"_s0",pid,p,0,"C","separated",0.0,2.0,100,4.0,
                          D+"/constraints/"+pid+"_s0_c.json",False))
    if a.cell in ("all","K_C1"):
        cells.append(("K_C1","P0",P0,0,"C","separated",2.0,2.0,100,4.0,
                      D+"/constraints/P0_s0_c.json",False))
    if a.cell in ("all","K_DS10"):
        cells.append(("K_DS10","P0",P0,0,"C","separated",2.0,2.0,10,4.0,
                      D+"/constraints/P0_s0_c.json",False))
    for tup in cells:
        cid,pid,p,seed,arm,ct,ctw,csw,steps,dur,cpath,use_if = tup
        if a.only and a.only != cid: continue
        if cpath and not use_if and not os.path.exists(cpath):
            print("[SKIP] "+cid+": constraint missing "+cpath, flush=True)
            row = dict.fromkeys(COLS,"NA")
            row["cell_id"]=cid; row["model"]="kimodo"; row["prompt_id"]=pid
            row["prompt_text"]=p; row["prompt_sha256"]=sha256_text(p)
            row["seed"]=seed; row["arm"]=arm; row["duration_s"]=dur
            row["diffusion_steps"]=steps; row["device"]=a.device
            row["threads"]=a.threads; row["fps"]=FPS_K
            row["notes"] = "SKIP no constraint file "+cpath
            append_manifest(row); continue
        if use_if and not os.path.exists(cpath):
            print("[SKIP] "+cid+": input_folder constraints missing "+cpath, flush=True); continue
        print("[RUN] "+cid, flush=True)
        row = run_cell(cid,pid,p,seed,arm,ct,ctw,csw,steps,dur,a.device,a.threads,
                       constraints_path=cpath, use_input_folder=use_if)
        append_manifest(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
