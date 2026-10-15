#!/usr/bin/env python3
"""Read-only recursive local-import closure walk from an entry script.

BFS over `import X` / `from X import ...` statements. A name counts as LOCAL
only if <root>/X.py, <root>/X/__init__.py or <root>/official_refs/X.py exists.
`pydeps/` (vendored onnxruntime + yaml) is deliberately NOT walked; it is
reported as vendored-external and checked for presence separately.

Prints the closure, unresolved top-level names, and which top-level .py files
are NOT reachable from the entry. Never writes anything. Exit 1 if a closure
module file is missing.
"""
import ast
import os
import sys

SEARCH_SUBDIRS = ('.', 'official_refs')


def resolve(root, name):
    top = name.split('.')[0]
    if not top or not top.isidentifier():
        return None, None
    for sub in SEARCH_SUBDIRS:
        base = root if sub == '.' else os.path.join(root, sub)
        py = os.path.join(base, top + '.py')
        pkg = os.path.join(base, top, '__init__.py')
        if os.path.isfile(py):
            return top, py
        if os.path.isfile(pkg):
            return top, pkg
    return None, None


def main():
    root = os.path.abspath(sys.argv[1])
    entry = sys.argv[2]
    seen = {}
    external = {}
    queue = [entry]
    while queue:
        mod = queue.pop(0)
        if mod in seen:
            continue
        _, path = resolve(root, mod)
        if path is None:
            continue
        seen[mod] = path
        try:
            tree = ast.parse(open(path, 'rb').read(), filename=path)
        except SyntaxError as exc:
            print('SYNTAX_ERROR %s: %s' % (mod, exc))
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                names = [node.module or '']
                names += ['%s.%s' % (node.module or '', a.name) for a in node.names]
            for name in names:
                top = name.split('.')[0]
                loc, locpath = resolve(root, name)
                if loc is not None:
                    if loc not in seen:
                        queue.append(loc)
                else:
                    external.setdefault(top, set()).add(mod)
    allpy = sorted(f[:-3] for f in os.listdir(root)
                   if f.endswith('.py') and os.path.isfile(os.path.join(root, f)))
    print('ROOT=%s' % root)
    print('ENTRY=%s' % entry)
    print('CLOSURE_LOCAL_MODULES(%d):' % len(seen))
    for mod in sorted(seen):
        rel = os.path.relpath(seen[mod], root).replace(os.sep, '/')
        print('   %-28s %8d B  %s' % (mod, os.path.getsize(seen[mod]), rel))
    print('EXTERNAL_TOPLEVEL(%d): %s' % (len(external), ' '.join(sorted(external))))
    for vend in ('pydeps/onnxruntime/__init__.py', 'pydeps/yaml/__init__.py',
                 'sonic_v11/model_encoder.onnx', 'sonic_v11/model_decoder.onnx',
                 'sonic_v11/observation_config.yaml'):
        p = os.path.join(root, vend)
        print('VENDORED %-42s %s %d B' % (vend, 'OK' if os.path.isfile(p) else 'MISSING',
                                          os.path.getsize(p) if os.path.isfile(p) else -1))
    unreach = [m for m in allpy if m not in seen]
    print('TOPLEVEL_PY_TOTAL=%d REACHABLE=%d UNREACHABLE_FROM_ENTRY=%d'
          % (len(allpy), len([m for m in allpy if m in seen]), len(unreach)))
    print('UNREACHABLE: %s' % ' '.join(unreach))
    return 0


if __name__ == '__main__':
    sys.exit(main())
