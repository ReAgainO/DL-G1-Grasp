import json, glob, os

B = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/rep/out"

KEYS = [
    "success", "max_lift_m", "hold_min_lift_m", "hold_min_contact_bodies",
    "lifted_height", "max_contact_bodies", "max_normal_force",
    "final_clearance", "final_cube_pos", "actual_arm_speed_within_limit",
    "fail_reason", "duration_s", "wall_s", "max_ik_position_error_m",
    "right_arm_tracking_rms_rad", "lock_grip",
]

for cell in ["wb_kimo_p6l1", "wb_kimo_p6", "wb_kimo_p1"]:
    f = os.path.join(B, cell, "result.json")
    if not os.path.exists(f):
        print(cell, "NO_RESULT"); continue
    r = json.load(open(f))
    print("=" * 78)
    print("CELL", cell)
    for k in KEYS:
        v = r.get(k, "<absent>")
        if isinstance(v, float):
            v = "%.6g" % v
        print("   %-28s %s" % (k, v))
    ga = r.get("gates", {}) or {}
    print("   gates pass                   %d/%d" % (sum(1 for x in ga.values() if x), len(ga)))
    # contact audit summary
    cas = r.get("contact_audit_summary")
    if cas:
        print("   contact_audit_summary        %s" % json.dumps(cas)[:300])
    print()

print("=" * 78)
print("KIMODO clip inventory in rep/src/original_motions/")
D = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/rep/src/original_motions"
for p in sorted(glob.glob(D + "/*.npz")):
    print("   %-24s %10d B" % (os.path.basename(p), os.path.getsize(p)))

print()
print("=" * 78)
print("conv clip inventory")
for D2 in ["/data/group4/20261008-232029-workbuddy-34e89f61/kimodo_conv"]:
    if os.path.isdir(D2):
        for p in sorted(glob.glob(D2 + "/*")):
            print("   %-24s %10d B" % (os.path.basename(p), os.path.getsize(p)))
