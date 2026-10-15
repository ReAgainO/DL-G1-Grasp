import numpy as np, os

D = "/data/group4/20261008-232029-workbuddy-34e89f61"
C = os.path.join(D, "kimodo_conv")
M = os.path.join(D, "harness_s1000", "rep", "src", "original_motions")

# The right-arm chain in the 34-point skeleton. We identify it empirically below
# by looking at which points MOVE in a clip whose text is "raises their right arm".
names = ["p1", "p2", "p3", "p4", "p5", "p6", "l1", "l2", "l3", "l4", "l5"]

print("%-5s %-6s %-22s %-22s %s" % ("clip", "T", "argmax_travel j / m", "argmax_vspan j / m", "rp_z_span"))
print("-" * 92)
for n in names:
    z = np.load(os.path.join(C, n + "_conv.npz"), allow_pickle=True)
    pj = np.asarray(z["posed_joints"], float)
    rp = np.asarray(z["root_positions"], float)
    travel = np.linalg.norm(pj[-1] - pj[0], axis=1)
    j = int(np.argmax(travel))
    vspan = pj[:, :, 2].max(axis=0) - pj[:, :, 2].min(axis=0)
    jv = int(np.argmax(vspan))
    print("%-5s %-6d %-22s %-22s %.4f" % (
        n, len(pj),
        "j=%d %.4f" % (j, travel[j]),
        "j=%d %.4f" % (jv, vspan[jv]),
        rp[:, 2].max() - rp[:, 2].min()))

print()
print("=== official near_s42 (for reference) ===")
p = os.path.join(M, "near_s42.npz")
z = np.load(p, allow_pickle=True)
pj = np.asarray(z["posed_joints"], float)
rp = np.asarray(z["root_positions"], float)
travel = np.linalg.norm(pj[-1] - pj[0], axis=1)
j = int(np.argmax(travel))
vspan = pj[:, :, 2].max(axis=0) - pj[:, :, 2].min(axis=0)
jv = int(np.argmax(vspan))
print("near_s42 T=%d argmax_travel j=%d %.4f   argmax_vspan j=%d %.4f  rp_z_span=%.4f" % (
    len(pj), j, travel[j], jv, vspan[jv], rp[:, 2].max() - rp[:, 2].min()))

print()
print("=== per-clip vertical travel of the ARM chain (upper-body points) ===")
print("   using points 15..28 as the arm/torso proxy")
for n in names + ["near_s42"]:
    p = os.path.join(C, n + "_conv.npz") if n != "near_s42" else os.path.join(M, "near_s42.npz")
    z = np.load(p, allow_pickle=True)
    pj = np.asarray(z["posed_joints"], float)
    arm = pj[:, 15:29, :]
    dz = arm[-1, :, 2] - arm[0, :, 2]
    print("   %-9s arm max rise=%+.4f  arm max drop=%+.4f  |dz|max=%.4f" % (
        n, dz.max(), dz.min(), np.abs(dz).max()))
