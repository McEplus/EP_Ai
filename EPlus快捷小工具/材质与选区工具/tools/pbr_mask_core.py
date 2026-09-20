"""Offline detail-mask math shared by batch conversion and tests."""
import math
import statistics
from PIL import Image

COLORS = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1))


def region(rgb):
    length = math.sqrt(sum(v*v for v in rgb))
    if not length:
        return -1
    for index, direction in enumerate(COLORS):
        score = sum(a*b for a, b in zip(rgb, direction)) / (length * math.sqrt(sum(direction)))
        if score >= 0.9999:
            return index
    return -1


def smooth(a, b, x):
    t = max(0, min(1, (x-a)/(b-a)))
    return t*t*(3-2*t)


def legacy_tint(rgb, target):
    luma = sum(a*b for a, b in zip(rgb, (0.299, 0.587, 0.114)))
    blend = smooth(0.35, 0.95, max(target))
    detail = (0.04 + 0.90*luma + 0.24*luma*(1-luma)) * (1-blend)
    detail += (0.08 + 0.70*luma/(luma+0.05) + 0.22*luma) * blend
    white = smooth(0.75, 0.98, min(target)) * smooth(0.65, 1, luma)
    return tuple(t*detail*(1+0.12*(s-luma))*(1-white*c)
                 for t, s, c in zip(target, rgb, (0.05, 0.025, 0)))


def build(source, mask):
    # Sample the base at mask texel UV centers; never resize the authored mask.
    if source.size != mask.size:
        source = source.resize(mask.size, Image.Resampling.NEAREST)
    width, height = source.size
    pixels, masks = list(source.convert('RGBA').getdata()), list(mask.convert('RGBA').getdata())
    ids = [region(p[:3]) for p in masks]
    logs = [math.log(max(sum(a*b for a, b in zip(p[:3], (0.299, 0.587, 0.114)))/255, 1/255)) for p in pixels]
    medians = {i: statistics.median([v for v, r, p in zip(logs, ids, pixels) if r == i and p[3]])
               for i in set(ids) if i >= 0 and any(r == i and p[3] for r, p in zip(ids, pixels))}
    # Connected components prevent averaging across disconnected atlas islands.
    labels, label = [-1]*len(ids), 0
    for start, rid in enumerate(ids):
        if rid < 0 or not pixels[start][3] or labels[start] >= 0:
            continue
        labels[start] = label
        stack = [start]
        while stack:
            p = stack.pop()
            x, y = p % width, p // width
            for nx, ny in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
                if 0 <= nx < width and 0 <= ny < height:
                    q = ny*width+nx
                    if labels[q] < 0 and ids[q] == rid and pixels[q][3]:
                        labels[q] = label
                        stack.append(q)
        label += 1
    kernel = [(dx, dy, math.exp(-(dx*dx+dy*dy)/8.0))
              for dy in range(-6, 7) for dx in range(-6, 7)]
    encoded, factors = [], []
    for p, (rid, rgba) in enumerate(zip(ids, masks)):
        if rid < 0:
            encoded.append(rgba)
            factors.append(1.0)
            continue
        x, y = p % width, p // width
        total, weight = 0.0, 0.0
        if labels[p] >= 0:
            for dx, dy, w in kernel:
                nx, ny = x+dx, y+dy
                if 0 <= nx < width and 0 <= ny < height:
                    q = ny*width+nx
                    if labels[q] == labels[p]:
                        total += logs[q]*w
                        weight += w
        local = total/weight if weight else logs[p]
        # Keep a little broad variation; do not mistake all dark areas for pigment.
        residual = logs[p] - (0.8*local + 0.2*medians.get(rid, local))
        ratio = math.exp(residual)
        detail = 0.90*ratio if ratio <= 1 else 0.90 + 0.09*(1-math.exp(-3*(ratio-1)))
        level = max(8, min(252, round(detail*255)))
        encoded.append(tuple(level*c for c in COLORS[rid]) + (rgba[3],))
        factors.append(level/255)
    result = Image.new('RGBA', source.size)
    result.putdata(encoded)
    assert [p[3] for p in encoded] == [p[3] for p in masks], 'Metallicity changed'
    assert [region(p[:3]) for p in encoded] == ids, 'Region identity changed'
    return result, ids, factors, pixels


