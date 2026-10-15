import json, os

B = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/rep/out"

for c in ["wb_kimo_p1", "wb_kimo_p6", "wb_kimo_p6l1", "wb_base_tpl", "wb_iso_lift"]:
    f = os.path.join(B, c, "result.json")
    if not os.path.exists(f):
        print(c, "NO_RESULT"); continue
    r = json.load(open(f))
    ba = r.get("balance_audit_summary") or {}
    print("=== %s ===" % c)
    print("   robot_table_all_max_normal_N =", ba.get("robot_table_all_max_normal_N"))
    print("   balance keys:", sorted(ba.keys()))
    gas = r.get("gates", {}) or {}
    print("   gates total=%d pass=%d" % (len(gas), sum(1 for v in gas.values() if v)))
    print()
