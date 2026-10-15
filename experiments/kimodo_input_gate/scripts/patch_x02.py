from pathlib import Path
NL = chr(10)
Q = chr(34)
B = Path('/data/group4/20261006-042506-qoder-x02eval/bridge')
s = (B / 'runners/run_grasp.py').read_text()
imp = 'from adapters.sonic_action_adapter import (' + NL + '    DEFAULT_ANGLES,'
assert imp in s, 'A1 import anchor'
s = s.replace(imp, imp + NL + '    M2I,')
arg_old = '    parser.add_argument(' + Q + '--no-cube-tracking' + Q + ', action=' + Q + 'store_true' + Q + ')'
assert arg_old in s, 'A2 arg anchor'
s = s.replace(
    arg_old,
    arg_old + NL + '    parser.add_argument(' + NL + '        ' + Q + '--trace-csv' + Q + ','
    + NL + '        default=None,' + NL + '        help=' + Q + 'x02eval trace dump' + Q + ','
    + NL + '    )',
)
assert 'trace_rows = []' not in s
s = s.replace('    baseline_frames = []', '    baseline_frames = []' + NL + '    trace_rows = []')
loop_anchor = '        if renderer is not None and step % args.render_every == 0:'
assert loop_anchor in s, 'A3 loop anchor'
tb = Path('/data/group4/20261006-042506-qoder-x02eval/scripts/trace_block.txt').read_text().rstrip(NL)
s = s.replace(loop_anchor, NL + tb + NL + NL + loop_anchor)
write_anchor = '    if args.no_grip and success:'
assert write_anchor in s, 'A4 write anchor'
wb = Path('/data/group4/20261006-042506-qoder-x02eval/scripts/write_block.txt').read_text().lstrip(NL)
s = s.replace(write_anchor, wb + NL + NL + write_anchor)
out = B / 'runners/run_grasp_x02.py'
out.write_text(s)
print('OK lines=', s.count(NL) + 1, 'bytes=', len(s))
