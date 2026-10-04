"""按 OCR 行坐标裁出问题区域，拼成 montage 供人工核对"""
import json, re
from PIL import Image

W = "/home/hatch/workspace/quizapp/ocr_work"
ocr = json.load(open("ocr_lines.json"))

def find_line(prefix, pred):
    for t in sorted([t for t in ocr if t.startswith(prefix)], key=lambda t: int(t.rsplit("_p", 1)[1])):
        for i, l in enumerate(ocr[t]):
            if pred(l["t"]):
                return t, i, l
    return None, None, None

# (label, tag_prefix, predicate, 上扩, 下扩)
jobs = [
    ("s8-Q2A", "slq1", lambda s: s.startswith("超押加微信"), 40, 60),
    ("s8-Q10C", "slq1", lambda s: "超力轴组装后" in s, 60, 60),
    ("s8-Q19CD", "slq1", lambda s: s.startswith("B、2~3"), 20, 120),
    ("s8-Q20D", "slq1", lambda s: s.startswith("C、电化学击穿"), 20, 120),
    ("s8-Q27", "slq1", lambda s: s.startswith("27、对于液体"), 10, 130),
    ("s8-Q28", "slq1", lambda s: "做信" in s, 120, 160),
    ("s8-Q45D", "slq1", lambda s: "超神于复杂" in s, 60, 100),
    ("s8-Q54D-Q55", "slq1", lambda s: s == "2.5", 60, 220),
    ("s8-A30", "sla1", lambda s: re.match(r"^29\.答案", s), 100, 260),
    ("s8-A47", "sla1", lambda s: re.match(r"^46\.答案", s), 100, 260),
    ("s8-A54", "sla1", lambda s: re.match(r"^53\.答案", s), 100, 260),
    ("s8-A82", "sla1", lambda s: re.match(r"^81\.答案", s), 100, 260),
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

# 拼成 2 张 montage
for mi, chunk in enumerate([crops[:6], crops[6:]]):
    maxw = max(c[1].width for c in chunk)
    total_h = sum(c[1].height for c in chunk) + 30 * len(chunk)
    m = Image.new("RGB", (maxw, total_h), "white")
    y = 0
    from PIL import ImageDraw
    d = ImageDraw.Draw(m)
    for label, c in chunk:
        d.text((10, y + 4), label, fill="red")
        m.paste(c, (0, y + 28))
        y += c.height + 30
    m.save(f"{W}/fix_s8_{mi+1}.png")
    print("saved fix_s8_%d.png" % (mi + 1), m.size)
