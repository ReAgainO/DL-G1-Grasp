#!/usr/bin/env python3
"""Print a compact summary of an official sonic_grasp.py result.json.

Usage: read_result.py <path/to/result.json> [--gates] [--audit]
"""
import json
import sys

path = sys.argv[1]
r = json.load(open(path))

print("path      :", path)
print("SUCCESS   :", r.get("success"))
print("legacy    :", r.get("legacy_success"))
print("gate_ver  :", r.get("gate_definition_version"))
print("strict    :", r.get("strict_execution_gate_enabled"))

cg = r.get("cube_geometry_entry", {})
print("cube req  :", cg.get("requested_xy_m"), "live_size", cg.get("live_size_xyz_m"),
      "mass", cg.get("mass_kg"))
print("cube init :", cg.get("initial_body_xyz_m"))

gates = r.get("gates", {})
npass = sum(1 for v in gates.values() if v)
print("gates     : %d/%d pass" % (npass, len(gates)))
for k, v in gates.items():
    print("   %-4s %s" % ("OK" if v else "FAIL", k))

if "--audit" in sys.argv:
    print("contacts  :", json.dumps(r.get("contact_audit_summary", {})))
    ba = r.get("balance_audit_summary", {})
    print("balance   :", json.dumps({k: ba[k] for k in list(ba)[:12]}, default=str))
    print("exec      :", json.dumps(r.get("execution_audit", {}), default=str)[:600])
    print("events    :", json.dumps(r.get("events", []))[:600])
    print("kind      :", r.get("kind"))
    print("warnings  :", r.get("warnings"))
