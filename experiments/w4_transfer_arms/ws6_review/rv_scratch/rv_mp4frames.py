#!/usr/bin/env python3
"""RV: minimal MP4 (ISOBMFF) parser to count video samples/frames without ffmpeg.
Walks top-level boxes -> moov -> trak -> mdia -> minf -> stbl -> stsz/stts, prints sample counts.
Usage: rv_mp4frames.py file.mp4 [file2.mp4 ...]
"""
import struct, sys

def boxes(buf, start, end):
    p = start
    while p + 8 <= end:
        size, typ = struct.unpack('>I4s', buf[p:p + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack('>Q', buf[p + 8:p + 16])[0]; hdr = 16
        elif size == 0:
            size = end - p
        if size < hdr or p + size > end:
            return
        yield typ.decode('latin1'), p + hdr, p + size
        p += size

def find(buf, start, end, path):
    cur = [(start, end)]
    for want in path:
        nxt = []
        for s, e in cur:
            for typ, bs, be in boxes(buf, s, e):
                if typ == want:
                    nxt.append((bs, be))
        cur = nxt
        if not cur:
            return []
    return cur

def count(fn):
    buf = open(fn, 'rb').read()
    n_samples = n_trak = 0
    for s, e in find(buf, 0, len(buf), ['moov', 'trak']):
        n_trak += 1
        hs = find(buf, s, e, ['mdia', 'hdlr'])
        handler = None
        for hs2, he2 in hs:
            # version+flags(4) predefined(4) handler_type(4)
            handler = buf[hs2 + 8:hs2 + 12].decode('latin1')
        stsz = find(buf, s, e, ['mdia', 'minf', 'stbl', 'stsz'])
        stts = find(buf, s, e, ['mdia', 'minf', 'stbl', 'stts'])
        stsd = find(buf, s, e, ['mdia', 'minf', 'stbl', 'stsd'])
        cnt = None
        if stsz:
            b = buf[stsz[0][0]:stsz[0][1]]
            if len(b) >= 12:
                sc = struct.unpack('>I', b[8:12])[0]
                cnt = sc if sc else struct.unpack('>I', b[12:16])[0]
        dur = None
        if stts:
            b = buf[stts[0][0]:stts[0][1]]
            n = struct.unpack('>I', b[4:8])[0]
            p = 8; dur = 0
            for _ in range(n):
                c, d = struct.unpack('>II', b[p:p + 8]); p += 8
                dur += c * d
        codec = None
        if stsd:
            b = buf[stsd[0][0]:stsd[0][1]]
            codec = b[12:16].decode('latin1') if len(b) >= 16 else None
        w = h = None
        if stsd:
            b = buf[stsd[0][0]:stsd[0][1]]
            if len(b) >= 16 + 78:
                w, h = struct.unpack('>HH', b[16 + 24:16 + 28])
        print('  trak#%d handler=%s codec=%s %sx%s samples=%s timescale_units_total=%s' % (
            n_trak, handler, codec, w, h, cnt, dur))
        if handler == 'vide':
            n_samples = cnt
    return n_samples

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        print(fn)
        print('  video_samples =', count(fn))
