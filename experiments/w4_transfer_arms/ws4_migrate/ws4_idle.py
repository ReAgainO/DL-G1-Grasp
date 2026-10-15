import time

def load():
    d = {}
    for ln in open("/proc/stat"):
        f = ln.split()
        if f[0].startswith("cpu") and f[0] != "cpu":
            d[f[0]] = (int(f[4]), sum(int(x) for x in f[1:]))
    return d

a = load()
time.sleep(2.0)
b = load()
res = []
for k in b:
    if k in a:
        di = b[k][0] - a[k][0]
        dt = b[k][1] - a[k][1]
        res.append((100.0 * di / dt if dt else 100.0, k))
res.sort(reverse=True)
print("idle%   cpu   (most idle 10)")
for v, k in res[:10]:
    print("%6.1f  %s" % (v, k))
print("busiest 3:", ", ".join("%s=%.0f%%" % (k, v) for v, k in res[-3:]))
print("n_cpu_total=%d  n_idle_gt50=%d" % (len(res), sum(1 for v, _ in res if v > 50)))
