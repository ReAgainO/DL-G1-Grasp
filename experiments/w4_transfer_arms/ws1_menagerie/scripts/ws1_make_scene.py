"""ws1 scene generator: menagerie g1_with_hands + floor + pedestal + cube.

Writes scene XMLs into model/unitree_g1/ (same dir as g1_with_hands.xml so
meshdir="assets" resolves). Cube / pedestal parameters come from
out/probe/grasp_specs.json (nominal) or explicit CLI overrides.

The official g1_with_hands.xml carries a "stand" keyframe whose qpos has 50
values; adding a cube freejoint makes nq=57 and MuJoCo refuses to compile such
keyframes. ws1_scene_model.xml is therefore an otherwise byte-identical copy of
the official file whose keyframe qpos is padded with 7 tokens
"0 0 0.5 1 0 0 0" (dummy cube pose; the real cube pose is always set by the
runner at runtime). Robot physics/dynamics are untouched; both hashes and the
diff are recorded in out/scene_model_record.json.

CLI:
  python ws1_make_scene.py      # scene model copy + one scene per size at spec spot
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L

PAD = " 0 0 0.5 1 0 0 0"

SCENE_TMPL = '''<mujoco model="g1_ws1_scene_e{edge_mm}">
  <include file="ws1_scene_model.xml"/>

  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.1 0.1 0.1" specular="0.9 0.9 0.9"/>
    <rgba haze="0.15 0.25 0.35 1"/>
    <global azimuth="140" elevation="-20"/>
  </visual>

  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>

  <worldbody>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane" friction="1 0.005 0.0001" condim="3"/>
    <light name="ws1_lamp" pos="{lx:.3f} {ly:.3f} {lz:.3f}" dir="{ldx:.2f} {ldy:.2f} {ldz:.2f}" directional="false"
      diffuse="0.5 0.5 0.5" specular="0.3 0.3 0.3"/>
    <body name="desk" pos="{px:.5f} {py:.5f} 0">
      <geom name="desk_top" type="box" size="{hx:.3f} {hy:.3f} {th:.5f}" pos="0 0 {th:.5f}"
        rgba="0.55 0.36 0.22 1" friction="1 0.005 0.0001" condim="3"/>
    </body>
    <body name="cube" pos="{cx:.5f} {cy:.5f} {cz:.5f}">
      <freejoint name="cube_free"/>
      <geom name="cube_geom" type="box" size="{s2:.5f} {s2:.5f} {s2:.5f}" rgba="0.85 0.15 0.12 1"
        friction="1 0.005 0.0001" condim="4" solref="0.004 1"/>
    </body>
  </worldbody>

  <equality>
    <weld name="cube_holder" body1="world" body2="cube" active="true"/>
  </equality>
</mujoco>
'''


SCENE_MODEL = os.path.join(L.MODEL_DIR, "ws1_scene_model.xml")


def make_scene_model():
    """official xml + keyframe qpos padded with 7 cube qpos tokens."""
    with open(L.MODEL_XML, "r", newline="") as f:
        src = f.read()
    pat = re.compile(r'(qpos="[^"]*)(")')
    hits = pat.findall(src)
    if len(hits) != 1:
        raise RuntimeError("expected exactly 1 qpos= in official xml, got %d" % len(hits))
    dst = pat.sub(lambda mo: mo.group(1) + PAD + mo.group(2), src)
    with open(SCENE_MODEL, "w", newline="\n") as f:
        f.write(dst)
    rec = {
        "official_xml": L.MODEL_XML,
        "official_sha256": L.sha256_file(L.MODEL_XML),
        "scene_model_xml": SCENE_MODEL,
        "scene_model_sha256": L.sha256_file(SCENE_MODEL),
        "diff": ["keyframe 'stand' qpos : official 50 values + appended '%s' (cube freejoint dummy pose)" % PAD.strip()],
        "note": "only this keyframe line differs; robot bodies/joints/actuators/geoms byte-identical",
    }
    L.jdump(rec, os.path.join(L.OUT, "scene_model_record.json"))
    return rec


def write_scene(edge_mm, cube_xyz, ped_center_xy, ped_half_xy, ped_top,
                light_pos, light_dir, out_path):
    s2 = edge_mm / 1000.0 / 2.0
    xml = SCENE_TMPL.format(
        edge_mm=edge_mm,
        cx=cube_xyz[0], cy=cube_xyz[1], cz=cube_xyz[2], s2=s2,
        px=ped_center_xy[0], py=ped_center_xy[1],
        hx=ped_half_xy[0], hy=ped_half_xy[1], th=ped_top / 2.0,
        lx=light_pos[0], ly=light_pos[1], lz=light_pos[2],
        ldx=light_dir[0], ldy=light_dir[1], ldz=light_dir[2])
    with open(out_path, "w", newline="\n") as f:
        f.write(xml)
    return out_path


def nominal_from_specs(edge_mm, mid_xyz, out_dir=None):
    """cube centre = jaw midpoint at spawn lambda, floating at the grasp spot and
    held by the temporary weld 'cube_holder' (released by the runner after the
    fingers close, before the lift). Wide low desk at top 0.80 m sits >50 mm
    below the hand's lowest sweep (only scenery + landing surface; the fingers
    physically cannot wrap a cube that stands on any support -- measured)."""
    out_dir = out_dir or L.MODEL_DIR
    mid_xyz = [float(v) for v in mid_xyz]
    light = (mid_xyz[0] + 0.6, mid_xyz[1] - 0.6, 1.7)
    ldir = (-0.5, 0.45, -0.9)
    out_path = os.path.join(out_dir, "ws1_scene_%dmm.xml" % edge_mm)
    return write_scene(edge_mm, mid_xyz, (mid_xyz[0], mid_xyz[1]), (0.18, 0.15),
                       0.80, light, ldir, out_path)


def main():
    rec = make_scene_model()
    print("scene model:", rec["scene_model_sha256"][:16], "(official", rec["official_sha256"][:16] + ")")
    specs = L.jload(os.path.join(L.PROBE_DIR, "grasp_specs.json"))
    for k, v in sorted(specs["sizes"].items()):
        mid = v.get("spawn_mid")
        if mid is None:
            print("size", k, "no spawn_mid (infeasible) - skipped")
            continue
        p = nominal_from_specs(int(k), mid)
        print("wrote", p)


if __name__ == "__main__":
    main()
