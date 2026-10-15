#!/usr/bin/env python3
"""W4c patch: add optional official-physics-recipe knobs to rep_ext_phys.

Default behaviour MUST be bit-identical: every insertion is guarded by
"if <knob> is set" and the disabled path executes the original statements.
Applies to rep/sonic_grasp.py and run_fixE.sh of the caller's own copy.
"""
import hashlib, sys
from pathlib import Path

ROOT = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys')
SG = ROOT / 'rep/sonic_grasp.py'
RUN = ROOT / 'run_fixE.sh'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def sub(text, old, new, tag, count=1):
    n = text.count(old)
    if n != count:
        raise SystemExit(f'FATAL {tag}: found {n} occurrences, expected {count}\n---{old[:200]}')
    return text.replace(old, new)

sg = SG.read_text()
run = RUN.read_text()
sg_before, run_before = sha(SG), sha(RUN)

# ---- R1: run() signature tail -------------------------------------------
sg = sub(sg,
    'cube_edge_mm=35.,cube_x=.267,cube_y=-.118,branch_coverage=False):',
    'cube_edge_mm=35.,cube_x=.267,cube_y=-.118,branch_coverage=False,substep=1,contact_margin=0.,solref=None,impratio=0.):',
    'R1-signature')

# ---- R2: model/dataset construction + optional overrides -----------------
sg = sub(sg,
    ' m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)\n'
    ' assert m.nu==43 and m.nq==57',
    ' m=mujoco.MjModel.from_xml_path(str(scene))\n'
    ' # W4c: optional translation of the official small-object physics recipe (isaaclab\n'
    ' # e30c25b1 pick_place_redblock: sim.dt=0.005 + 4 substeps, contact_offset 0.01,\n'
    ' # num_position_iterations 16, CCD) into MuJoCo equivalents. Default OFF: the four\n'
    ' # knobs below are all neutral and the code path is the original one.\n'
    ' phys_recipe=None\n'
    ' if substep!=1 or contact_margin>0 or solref is not None or impratio>0:\n'
    '  assert isinstance(substep,int) and 1<=substep<=8,"W4c substep must be 1..8"\n'
    '  assert 0.<=contact_margin<=.005,"W4c contact margin 0..5mm"\n'
    '  assert 0.<=impratio<=100.,"W4c impratio 0..100"\n'
    '  if substep!=1:m.opt.timestep=float(m.opt.timestep)/substep\n'
    '  if impratio>0:m.opt.impratio=float(impratio)\n'
    '  phys_geoms=[m.geom("red_cube_geom").id]+[m.geom(n).id for n in core.PADS]\n'
    '  if contact_margin>0:\n'
    '   for _g in phys_geoms:m.geom_margin[_g]=float(contact_margin)\n'
    '  if solref is not None:\n'
    '   assert len(solref)==2 and solref[0]>0 and solref[1]>=0,"W4c solref (timeconst dampratio)"\n'
    '   for _g in phys_geoms:m.geom_solref[_g]=[float(solref[0]),float(solref[1])]\n'
    '  phys_recipe=dict(requested=dict(substep=int(substep),contact_margin_m=float(contact_margin),\n'
    '      solref=None if solref is None else [float(solref[0]),float(solref[1])],impratio=float(impratio)),\n'
    '      control_hz=500.,physics_timestep_s=float(m.opt.timestep),physics_hz=1./float(m.opt.timestep),\n'
    '      model_impratio=float(m.opt.impratio),geom_names=[m.geom(_g).name for _g in phys_geoms],\n'
    '      geom_margin_m=[float(m.geom_margin[_g]) for _g in phys_geoms],\n'
    '      geom_solref=[[float(x) for x in m.geom_solref[_g]] for _g in phys_geoms],\n'
    '      scope="cube geom + three fingertip pads; nothing else in the model is touched",\n'
    '      source="isaaclab @e30c25b1 pick_place_redblock_g1_29dof_dex3: sim.dt .005 x num_substeps 4 / num_position_iterations 16 / enable_ccd / object contact_offset .01 rest 0.0 -> MuJoCo equivalents: timestep/substep subdivision, geom margin, solver impratio; the model already carries <flag multiccd=enable>")\n'
    '  print("W4C_PHYSICS "+json.dumps(phys_recipe),flush=True)\n'
    ' d=mujoco.MjData(m)\n'
    ' assert m.nu==43 and m.nq==57',
    'R2-model')

# ---- R3: substep the physics inside the 500Hz control tick ---------------
sg = sub(sg,
    '  ext=max(ext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()));mujoco.mj_step(m,d)',
    '  ext=max(ext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()))\n'
    '  if substep==1:mujoco.mj_step(m,d)\n'
    '  else:\n'
    '   for _w4c_sub in range(substep):mujoco.mj_step(m,d)',
    'R3-step')

# ---- R4: record the recipe in result.json (only when enabled) ------------
sg = sub(sg,
    " result['branch_face_alignment_enabled']=branch_face_alignment",
    " if phys_recipe is not None:result['physics_recipe_w4c']=phys_recipe\n"
    " result['branch_face_alignment_enabled']=branch_face_alignment",
    'R4-result')

# ---- R5: CLI knobs -------------------------------------------------------
sg = sub(sg,
    " p.add_argument('--cube-y',type=float,default=-.118,help='A3: red cube body y in m; -.118 reproduces the template')",
    " p.add_argument('--cube-y',type=float,default=-.118,help='A3: red cube body y in m; -.118 reproduces the template')\n"
    " p.add_argument('--substep',type=int,default=1,help='W4c M2 translation: physics sub-steps per 500Hz control tick (timestep = 0.002/substep); 1 reproduces the baseline exactly')\n"
    " p.add_argument('--contact-margin',type=float,default=0.,help='W4c M2 translation: geom margin [m] on cube+pads (isaaclab contact_offset); 0 reproduces the baseline exactly')\n"
    " p.add_argument('--solref',nargs=2,type=float,default=None,metavar=('TIMECONST','DAMPRATIO'),help='W4c M2 translation: geom solref on cube+pads; default None keeps the XML values (cube .006 1 / pads .008 1)')\n"
    " p.add_argument('--impratio',type=float,default=0.,help='W4c M2 translation: model.opt.impratio; 0 keeps the model default 1')",
    'R5-cli')

# ---- R6: run_fixE.sh arm injection + provenance --------------------------
run = sub(run,
    '[ "$FACE" != "0" ] && EXTRA+=("--grip-face-half-mm=$FACE")',
    '[ "$FACE" != "0" ] && EXTRA+=("--grip-face-half-mm=$FACE")\n'
    '# W4c: optional physics-recipe arm, e.g. W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10"\n'
    'if [ -n "${W4C_PHYS:-}" ]; then read -r -a _W4C <<< "$W4C_PHYS"; EXTRA+=("${_W4C[@]}"); fi',
    'R6-run-extras')

run = sub(run,
    """  printf 'sonic_grasp_args=%s\\n' "$NAME ${EXTRA[*]}\"""",
    """  printf 'sonic_grasp_args=%s\\n' "$NAME ${EXTRA[*]}"
  printf 'w4c_phys_args=%s\\n' "${W4C_PHYS:-<none>}\"""",
    'R7-run-meta')

SG.write_text(sg)
RUN.write_text(run)
print('sonic_grasp.py', sg_before, '->', sha(SG))
print('run_fixE.sh  ', run_before, '->', sha(RUN))
