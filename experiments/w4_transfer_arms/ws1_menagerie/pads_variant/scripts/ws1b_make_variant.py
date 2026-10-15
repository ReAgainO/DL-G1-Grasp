"""ws1b pads-only collision variant generator (menagerie g1_with_hands.xml).

Base: W1's ws1_scene_model.xml (read-only) = official g1_with_hands.xml whose
single 'stand' keyframe qpos is padded with 7 cube tokens so scenes with a cube
freejoint compile. Robot bodies/joints/actuators are byte-identical to official.

Transform (right hand only, i.e. inside <body name="right_wrist_yaw_link">):
  (1) GHOST every right-hand collision geom: contype=0 conaffinity=0
        - right_hand_palm_link mesh
        - right_hand_thumb_0_link mesh
        - right_hand_thumb_1_link BOX  (size 0.01 0.015 0.01 -- a 20x30x20 mm proxy)
        - right_hand_thumb_2_link mesh
        - right_hand_middle_0_link mesh, right_hand_middle_1_link mesh
        - right_hand_index_0_link mesh,  right_hand_index_1_link mesh
      (the wrist link's own collision mesh is NOT touched: it is the forearm end)
  (2) ADD one fingertip pad sphere per finger on the distal body
      (thumb_2 / index_1 / middle_1): type=sphere, r (CLI, default 5 mm),
      density=0 (massless marker, dynamics untouched), condim=4,
      friction (CLI, default = asset default '1 0.005 0.0001'),
      center = tip_vertex - inset_frac * r * dir   (dir = tip direction measured
      from the distal joint anchor = body origin; tip = mesh vertex farthest
      from the anchor)

Result: the right hand's ONLY colliding geoms are the three pad spheres
("pads-only": phalanges + palm are ghosts, only pads can carry load).

Writes <root>/model/unitree_g1/ws1b_scene_model.xml and the full edit record
<root>/out/probe/pads_variant_record.json.
"""
import argparse
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

W1_SCENE_MODEL = os.path.join(L.W1_ROOT, "model", "unitree_g1", "ws1_scene_model.xml")
# ws1_scene_model.xml carries the 'stand' keyframe padded with 7 cube tokens, so it
# only compiles inside a scene that adds the cube freejoint (nq=57). Use W1's dummy
# scene for probing (same tree, read-only).
W1_PROBE_SCENE = os.path.join(L.W1_ROOT, "model", "unitree_g1", "ws1_scene_dummy.xml")
RH_ANCHOR = '<body name="right_wrist_yaw_link"'

VERIFY_TMPL = '''<mujoco model="ws1b_verify_tmp">
  <include file="ws1b_scene_model.xml"/>
  <worldbody>
    <body name="cube" pos="0.5 0 0.5">
      <freejoint name="cube_free"/>
      <geom name="cube_geom" type="box" size="0.01 0.01 0.01"/>
    </body>
  </worldbody>
</mujoco>
'''

GHOST_LINES = [
    '<geom pos="0.0415 -0.003 0" quat="1 0 0 0" class="collision" mesh="right_hand_palm_link"/>',
    '<geom class="collision" mesh="right_hand_thumb_0_link"/>',
    '<geom size="0.01 0.015 0.01" pos="-0.001 0.032 0" type="box" class="collision"/>',
    '<geom class="collision" mesh="right_hand_thumb_2_link"/>',
    '<geom class="collision" mesh="right_hand_middle_0_link"/>',
    '<geom class="collision" mesh="right_hand_middle_1_link"/>',
    '<geom class="collision" mesh="right_hand_index_0_link"/>',
    '<geom class="collision" mesh="right_hand_index_1_link"/>',
]


def quat_rot(q, v):
    w, x, y, z = [float(c) for c in q]
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return R @ np.asarray(v, dtype=float)


def mesh_tip_info(m, body_name):
    """farthest mesh vertex from the body origin (joint anchor), in body frame."""
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body_name)
    gid = -1
    for g in range(m.ngeom):
        if m.geom_bodyid[g] == bid and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
            gid = g
            break
    if gid < 0:
        raise RuntimeError("no mesh geom on body %s" % body_name)
    mid = m.geom_dataid[gid]
    va, n = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
    vs = m.mesh_vert[va:va + n].copy()
    gp, gq = m.geom_pos[gid].copy(), m.geom_quat[gid].copy()
    vs = np.array([quat_rot(gq, v) for v in vs]) + gp  # body frame
    dist = np.linalg.norm(vs, axis=1)
    i = int(np.argmax(dist))
    tip = vs[i]
    dirv = tip / dist[i]
    # tip-region cross-section: verts within 3 mm of the tip vertex
    near = vs[np.linalg.norm(vs - tip, axis=1) < 0.003]
    lat = 0.0
    if len(near):
        d = near - tip
        par = d @ dirv
        perp = np.linalg.norm(d - np.outer(par, dirv), axis=1)
        lat = float(np.max(perp))
    return {
        "body": body_name, "geom_id": gid, "mesh_id": int(mid),
        "tip_body": [round(float(v), 6) for v in tip],
        "tip_dist_from_anchor_m": round(float(dist[i]), 6),
        "dir_body": [round(float(v), 6) for v in dirv],
        "tip_region_max_lateral_m": round(lat, 6),
        "bbox_body": [[round(float(vs[:, k].min()), 6), round(float(vs[:, k].max()), 6)] for k in range(3)],
        "n_verts": int(n),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r", type=float, default=0.005, help="pad sphere radius [m]")
    ap.add_argument("--inset-frac", type=float, default=0.7,
                    help="pad center = tip - inset_frac*r*dir (1.0 => surface touches the tip vertex)")
    ap.add_argument("--friction", default="1 0.005 0.0001")
    ap.add_argument("--condim", type=int, default=4)
    args = ap.parse_args()

    # ---- probe tips on the unmodified variant base -------------------------
    m = mujoco.MjModel.from_xml_path(W1_PROBE_SCENE)
    tips = {k: mesh_tip_info(m, b) for k, b in L.PAD_BODIES.items()}

    # ---- XML surgery on the right-hand section -----------------------------
    with open(W1_SCENE_MODEL, "r", newline="") as f:
        src = f.read()
    k = src.index(RH_ANCHOR)
    head, tail = src[:k], src[k:]

    ghosted = []
    for s in GHOST_LINES:
        if tail.count(s) != 1:
            raise RuntimeError("ghost anchor not unique in right-hand section: %r (%d)" % (s, tail.count(s)))
        tail = tail.replace(s, s[:-2] + ' contype="0" conaffinity="0"/>')
        ghosted.append(s)

    pads = {}
    for key, body in L.PAD_BODIES.items():
        ti = tips[key]
        tip = np.array(ti["tip_body"])
        dirv = np.array(ti["dir_body"])
        center = tip - args.inset_frac * args.r * dirv
        anchor = GHOST_LINES[{"thumb": 3, "middle": 5, "index": 7}[key]]
        ghosted_anchor = anchor[:-2] + ' contype="0" conaffinity="0"/>'
        ls = tail.rfind("\n", 0, tail.index(ghosted_anchor)) + 1
        indent = tail[ls:tail.index(ghosted_anchor)]
        pad_xml = ('%s<geom name="%s" type="sphere" size="%.6f" pos="%.6f %.6f %.6f" '
                   'contype="1" conaffinity="1" condim="%d" density="0" friction="%s" '
                   'rgba="0.15 0.85 0.2 1" group="3"/>'
                   % (indent, L.PAD_GEOM_NAMES[key], args.r, center[0], center[1], center[2],
                      args.condim, args.friction))
        if tail.count(ghosted_anchor) != 1:
            raise RuntimeError("pad anchor not unique: %s" % ghosted_anchor)
        tail = tail.replace(ghosted_anchor, ghosted_anchor + "\n" + pad_xml)
        pads[key] = {
            "geom_name": L.PAD_GEOM_NAMES[key], "body": body,
            "center_body": [round(float(v), 6) for v in center],
            "r": args.r, "inset_frac": args.inset_frac,
            "tip_body": ti["tip_body"], "dir_body": ti["dir_body"],
            "protrusion_beyond_tip_m": round(float((1.0 - args.inset_frac) * args.r), 6),
            "friction": args.friction, "condim": args.condim, "density": 0,
        }

    os.makedirs(os.path.dirname(L.VARIANT_XML), exist_ok=True)
    with open(L.VARIANT_XML, "w", newline="\n") as f:
        f.write(head + tail)

    # ---- verify + record ---------------------------------------------------
    verify_scene = os.path.join(L.MODEL_DIR, "ws1b_verify_tmp.xml")
    with open(verify_scene, "w", newline="\n") as f:
        f.write(VERIFY_TMPL)
    try:
        mv = mujoco.MjModel.from_xml_path(verify_scene)
    finally:
        os.remove(verify_scene)
    pid = {k: mujoco.mj_name2id(mv, mujoco.mjtObj.mjOBJ_GEOM, n) for k, n in L.PAD_GEOM_NAMES.items()}
    assert all(v >= 0 for v in pid.values()), pid
    kept = {}
    for fg, bl in (("thumb", L.RH_BODIES_THUMB), ("index", L.RH_BODIES_INDEX),
                   ("middle", L.RH_BODIES_MIDDLE)):
        names = []
        for b in bl:
            for g in L.body_geom_ids(mv, b):
                if mv.geom_contype[g] or mv.geom_conaffinity[g]:
                    names.append(mujoco.mj_id2name(mv, mujoco.mjtObj.mjOBJ_GEOM, g) or "#%d" % g)
        kept[fg] = names
    palm_kept = []
    for g in L.body_geom_ids(mv, L.HAND_BODY):
        if (mv.geom_contype[g] or mv.geom_conaffinity[g]):
            nm = mujoco.mj_id2name(mv, mujoco.mjtObj.mjOBJ_GEOM, g) or "#%d" % g
            if nm not in L.PAD_GEOM_NAMES.values():
                palm_kept.append(nm)
    rec = {
        "worker": "ws1b", "variant": "pads-only",
        "base_xml": W1_SCENE_MODEL, "base_sha256": L.sha256_file(W1_SCENE_MODEL),
        "official_model_sha256": L.sha256_file(L.MODEL_XML),
        "variant_xml": L.VARIANT_XML, "variant_sha256": L.sha256_file(L.VARIANT_XML),
        "ghosted_collision_geoms_right_hand": ghosted,
        "pads": pads,
        "kept_collision_inventory": {
            "thumb": kept["thumb"], "index": kept["index"], "middle": kept["middle"],
            "palm": [], "note_palm": "palm + phalanges ghosted; wrist link collision mesh untouched (forearm end)",
            "wrist_link_kept": palm_kept,
        },
        "mujoco_version": mujoco.__version__,
        "tip_probe": tips,
        "generated_out": "ws1b_make_variant.py",
    }
    L.jdump(rec, os.path.join(L.PROBE_DIR, "pads_variant_record.json"))
    print("variant xml:", L.VARIANT_XML)
    print("variant sha256:", rec["variant_sha256"])
    for kk in ("thumb", "index", "middle"):
        print("tip[%s] dist=%.4f m lateral=%.4f m | pad r=%.4f center=%s protrude=%.4f m"
              % (kk, tips[kk]["tip_dist_from_anchor_m"], tips[kk]["tip_region_max_lateral_m"],
                 args.r, pads[kk]["center_body"], pads[kk]["protrusion_beyond_tip_m"]))
    print("kept collision geoms:", kept["thumb"], kept["index"], kept["middle"], "| palm [] | wrist:", palm_kept)
    # ghost-distance sanity: confirm disabled geoms are still measured by mj_geomDistance
    return 0


if __name__ == "__main__":
    sys.exit(main())
