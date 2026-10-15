"""ws1b scene generator: pads-only variant model + floor + desk + cube.

Same template as W1's ws1_make_scene.py (byte-identical geometry parameters),
except it includes the pads-only variant model (ws1b_scene_model.xml) and writes
ws1b_scene_<edge>mm.xml into this sandbox's model dir.

The cube is spawned at the grasp spot (placement.json chosen P) and held there
by the temporary weld 'cube_holder' until the fingers close (same protocol).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

SCENE_TMPL = '''<mujoco model="g1_ws1b_scene_e{edge_mm}">
  <include file="ws1b_scene_model.xml"/>

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
    <light name="ws1b_lamp" pos="{lx:.3f} {ly:.3f} {lz:.3f}" dir="{ldx:.2f} {ldy:.2f} {ldz:.2f}" directional="false"
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


def write_scene(edge_mm, cube_xyz, out_path):
    s2 = edge_mm / 1000.0 / 2.0
    xml = SCENE_TMPL.format(
        edge_mm=edge_mm,
        cx=cube_xyz[0], cy=cube_xyz[1], cz=cube_xyz[2], s2=s2,
        px=cube_xyz[0], py=cube_xyz[1],
        hx=0.18, hy=0.15, th=0.80 / 2.0,
        lx=cube_xyz[0] + 0.6, ly=cube_xyz[1] - 0.6, lz=1.7,
        ldx=-0.5, ldy=0.45, ldz=-0.9)
    with open(out_path, "w", newline="\n") as f:
        f.write(xml)
    return out_path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", default=os.path.join(L.PROBE_DIR, "placement.json"))
    ap.add_argument("--suffix", default=None, help="scene name suffix: ws1b_scene_<edge>mm_<suffix>.xml")
    args = ap.parse_args()
    pl = L.jload(args.placement)
    for k, v in sorted(pl["sizes"].items(), key=lambda kv: int(kv[0])):
        ch = v.get("chosen")
        if not ch:
            print("size", k, "no chosen placement - skipped")
            continue
        name = "ws1b_scene_%dmm%s.xml" % (int(k), ("_" + args.suffix) if args.suffix else "")
        p = write_scene(int(k), ch["P"], os.path.join(L.MODEL_DIR, name))
        print("wrote", p, "cube@", ch["P"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
