"""set9 问题区域 montage"""
import json, re
from PIL import Image, ImageDraw

W = "/home/hatch/workspace/quizapp/ocr_work"
ocr = json.load(open("ocr_lines.json"))

def find_line(prefix, pred):
    for t in sorted([t for t in ocr if t.startswith(prefix)], key=lambda t: int(t.rsplit("_p", 1)[1])):
        for i, l in enumerate(ocr[t]):
            if pred(l["t"]):
                return t, i, l
    return None, None, None

jobs = [
    ("s9-Q2Q3", "slq2", lambda s: s.startswith("D、80Hz"), 10, 260),
    ("s9-Q10AB", "slq2", lambda s: "超线方向" in s, 80, 80),
    ("s9-Q11-Q12", "slq2", lambda s: s.startswith("D、80°"), 10, 240),
    ("s9-Q18AB", "slq2", lambda s: s.startswith("MPa，保压时间为30min"), 60, 100),
    ("s9-dup18", "slq2", lambda s: s == "1、8", 60, 60),
    ("s9-Q43AB", "slq2", lambda s: "虽钩应位于" in s, 40, 80),
    ("s9-Q52BD", "slq2", lambda s: s.startswith("混燃烧，又称混合燃烧"), 60, 160),
    ("s9-Q53", "slq2", lambda s: re.match(r"^52、", s), 200, 420),
    ("s9-Q61A", "slq2", lambda s: "刀在生产工艺方面" in s, 40, 120),
    ("s9-Q62C", "slq2", lambda s: s.startswith("B、离子感烟"), 20, 120),
    ("s9-Q69-Q70", "slq2", lambda s: s.startswith("D、企业业务经营人员"), 10, 260),
    ("s9-Q75num", "slq2", lambda s: s.startswith("5、，（多）"), 20, 120),
    ("s9-Q85", "slq2", lambda s: re.match(r"^84、", s), 150, 400),
    ("s9-A11", "sla2", lambda s: re.match(r"^10\.答案", s), 80, 260),
    ("s9-A33", "sla2", lambda s: re.match(r"^32\.答案", s), 80, 260),
    ("s9-A40", "sla2", lambda s: re.match(r"^39\.答案", s), 80, 260),
    ("s9-A69", "sla2", lambda s: re.match(r"^68\.答案", s), 80, 260),
    ("s9-A77", "sla2", lambda s: re.match(r"^76\.答案", s), 80, 260),
    ("s9-A82", "sla2", lambda s: re.match(r"^81\.答案", s), 80, 260),
]

crops = []
for label, prefix, pred, up, down in jobs:
    t, i, l = find_line(prefix, pred)
    if t is None:
        print("NOT FOUND:", label); continue
    img = Image.open(f"{W}/{t}.png")
    y0 = max(0, int(l["y"]) - up); y1 = min(img.height, int(l["y"]) + down)
    crops.append((label, img.crop((0, y0, img.width, y1))))
    print(label, t, f"y={int(l['y'])}")

for mi, chunk in enumerate([crops[:7], crops[7:13], crops[13:]]):
    maxw = max(c[1].width for c in chunk)
    total_h = sum(c[1].height for c in chunk) + 30 * len(chunk)
    m = Image.new("RGB", (maxw, total_h), "white")
    y = 0
    d = ImageDraw.Draw(m)
    for label, c in chunk:
        d.text((10, y + 4), label, fill="red")
        m.paste(c, (0, y + 28))
        y += c.height + 30
    m.save(f"{W}/fix_s9_{mi+1}.png")
    print("saved fix_s9_%d.png" % (mi + 1), m.size)
