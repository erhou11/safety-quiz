"""解析顺利法规5套合集: m5/spNN.png OCR -> 按套归属 halves
版式: 每扫描页=左右2个文档页; 题目页单栏, 答案页单栏/双栏混排
关键: 按页眉页脚"模拟卷(一..五)"+是否"参考答案"归属, 题目与答案各自按套隔离
"""
import json, re, os

W = os.path.expanduser("~/workspace/quizapp/ocr_work")
PAGE_W = 2339
ocr = json.load(open(W + "/ocr_m5.json"))

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
SET_PAT = re.compile(r"模拟卷（([一二三四五])）")
HDR_PAT = re.compile(r"顺利中级注安法规")
PGNUM_PAT = re.compile(r"^·\s*\d+\s*·$")
SEC_PAT = re.compile(r"^[一二]、[单多]项选择题")
Q_PAT = re.compile(r"^(\d+)\s*[、.，,．·]\s*(.*)$")


def detect(half):
    sn, ans = None, False
    for l in half:
        t = l["t"]
        m = SET_PAT.search(t)
        if m:
            sn = CN[m.group(1)]
        if "参考答案" in t:
            ans = True
    return sn, ans


def columns(half):
    xs = []
    for l in half:
        t = l["t"].strip()
        m = Q_PAT.match(t)
        if m and m.group(2):
            xs.append(l["x"] - l["w"] / 2)
    if not xs:
        return None
    xs.sort()
    groups = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] < 90:
            groups[-1].append(x)
        else:
            groups.append([x])
    edges = [sum(g) / len(g) for g in groups]
    merged = [edges[0]]
    for e in edges[1:]:
        if e - merged[-1] < 200:
            merged[-1] = (merged[-1] + e) / 2
        else:
            merged.append(e)
    return sorted(merged)


def order_half(half):
    edges = columns(half)
    if not edges or len(edges) == 1:
        ls = sorted(half, key=lambda l: l["y"])
        return [{"x": l["x"], "y": l["y"], "t": l["t"].strip(), "p": -1, "s": ""} for l in ls]
    bounds = []
    for i, e in enumerate(edges):
        hi = (edges[i + 1] + e) / 2 if i + 1 < len(edges) else 1e9
        bounds.append(hi)
    cols = [[] for _ in edges]
    for l in half:
        x0 = l["x"] - l["w"] / 2
        idx = len(edges) - 1
        for i, hi in enumerate(bounds):
            if x0 < hi + 40:
                idx = i
                break
        cols[idx].append(l)
    out = []
    for c in cols:
        for l in sorted(c, key=lambda l: l["y"]):
            out.append({"x": l["x"], "y": l["y"], "t": l["t"].strip(), "p": -1, "s": ""})
    return out


def clean(lines):
    out = []
    for e in lines:
        t = e["t"].strip()
        if not t:
            continue
        if HDR_PAT.search(t):
            continue
        if PGNUM_PAT.match(t):
            continue
        if SEC_PAT.match(t):
            continue
        if t == "参考答案":
            continue
        if re.match(r"^[.·]?\d{1,3}[.·]$", t):
            continue
        if re.match(r"^\d+\s*[、.，,．·]\s*$", t):
            continue
        if re.match(r"^[（(]至少有1个错项", t):
            continue
        e["t"] = t
        out.append(e)
    return out


halves = []
for i in range(1, 90):
    tag = "sp%02d" % i
    ls = ocr.get(tag, [])
    for side, pred in (("L", lambda l: l["x"] < PAGE_W / 2),
                       ("R", lambda l: l["x"] >= PAGE_W / 2)):
        half = [l for l in ls if pred(l)]
        if not half:
            continue
        sn, ans = detect(half)
        cls = clean(order_half(half))
        for e in cls:
            e["p"], e["s"] = i, side
        halves.append((i, side, sn, ans, cls))

# set=None 的半页继承上一个半页的归属(页眉漏检的续页)
fixed = []
for idx, (i, side, sn, ans, lines) in enumerate(halves):
    if sn is None and fixed:
        sn, ans = fixed[-1][2], fixed[-1][3]
    fixed.append((i, side, sn, ans, lines))
halves = fixed

print("page side set answer nlines first-line")
for i, side, sn, ans, lines in halves:
    fl = lines[0]["t"][:30] if lines else ""
    print("%3d %s %s %d %4d %s" % (i, side, sn, int(ans), len(lines), fl))

json.dump([{"page": i, "side": s, "set": sn, "answer": ans, "lines": l}
           for i, s, sn, ans, l in halves],
          open(W + "/m5_halves.json", "w", encoding="utf-8"), ensure_ascii=False)
print("saved m5_halves.json")
