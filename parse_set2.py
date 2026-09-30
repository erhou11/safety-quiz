#!/usr/bin/env python3
"""解析《安全技术基础》阶段评测一（去水印 PDF）-> questions_set2.json"""
import pymupdf, re, json, hashlib, io, os

SRC = "/home/hatch/workspace/user/files/___8____1_2026______________________1789480557728_0_vtmb_去水印.pdf"
OUT = "/home/hatch/workspace/quizapp/questions_set2.json"
IMGDIR = "/tmp/set2_img"

MARK_RE = re.compile(r"【([^】]*选择题[^】]*)】")
ANS_RE = re.compile(r"【答案】([A-E]+)")
EXP_RE = re.compile(r"【解析】")
OPT_RE = re.compile(r"([A-E])．")

d = pymupdf.open(SRC)

# 1. 逐页提取文本块（阅读顺序），过滤页码
pages = []
for p in d:
    blocks = []
    for b in p.get_text("blocks"):
        t = b[4].strip()
        if not t or re.fullmatch(r"\d+ / 24", t):
            continue
        blocks.append({"y": b[1], "x": b[0], "rect": pymupdf.Rect(b[:4]), "text": t})
    blocks.sort(key=lambda b: (b["y"], b["x"]))
    pages.append({"page": p, "blocks": blocks})

# 2. 定位所有题目
markers = []
for pi, pg in enumerate(pages):
    for bi, b in enumerate(pg["blocks"]):
        m = MARK_RE.search(b["text"])
        if m:
            markers.append((pi, bi, m.group(1)))
print("题目数:", len(markers))

# 3. 第5页矢量表格 bbox
p5 = d[5]
tab_draws = [dr for dr in p5.get_drawings()
             if 115 < dr["rect"].y0 < 250 and 30 < dr["rect"].x0 and dr["rect"].x1 < 575]
tx0 = min(dr["rect"].x0 for dr in tab_draws) - 4
ty0 = min(dr["rect"].y0 for dr in tab_draws) - 4
tx1 = max(dr["rect"].x1 for dr in tab_draws) + 4
ty1 = max(dr["rect"].y1 for dr in tab_draws) + 4
TABLE_BBOX = pymupdf.Rect(tx0, ty0, tx1, ty1)
print("表格 bbox:", [round(v, 1) for v in TABLE_BBOX])

def in_table(pi, blk):
    if pi != 5:
        return False
    r = blk["rect"]
    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
    return TABLE_BBOX.x0 < cx < TABLE_BBOX.x1 and TABLE_BBOX.y0 < cy < TABLE_BBOX.y1

# 4. 逐题解析
questions = []
for qi, (pi, bi, label) in enumerate(markers):
    end_pi, end_bi = markers[qi + 1][:2] if qi + 1 < len(markers) else (len(pages), 0)
    chunks = []
    first = True
    for pj in range(pi, end_pi + 1):
        if pj >= len(pages):
            break
        for bj, b in enumerate(pages[pj]["blocks"]):
            if pj == pi and bj < bi:
                continue
            if pj == end_pi and bj >= end_bi:
                break
            if in_table(pj, b):
                continue
            t = b["text"]
            if re.fullmatch(r"第\d+讲\s+阶段测评一（[一二三四五六七八九十]+）", t):
                continue
            if first:
                mm = MARK_RE.search(t)
                t = t[mm.end():].strip()
                first = False
            if t:
                chunks.append(t)
    raw = "\n".join(chunks)

    m_ans = ANS_RE.search(raw)
    assert m_ans, "Q%d 无答案" % (qi + 1)
    answer = list(m_ans.group(1))
    qpart = raw[:m_ans.start()].strip()
    expart = raw[m_ans.end():].strip()
    explanation = EXP_RE.sub("", expart, count=1).strip()

    matches = list(OPT_RE.finditer(qpart))
    seq = None
    for i, m in enumerate(matches):
        if m.group(1) == "A":
            letters = [mm.group(1) for mm in matches[i:]]
            if letters[:4] == ["A", "B", "C", "D"]:
                n = 5 if len(letters) > 4 and letters[4] == "E" else 4
                seq = matches[i:i + n]
                break
    assert seq, "Q%d 选项序列异常" % (qi + 1)
    stem = qpart[:seq[0].start()].strip()
    options = []
    for j, m in enumerate(seq):
        end = seq[j + 1].start() if j + 1 < len(seq) else len(qpart)
        options.append({"letter": m.group(1), "text": qpart[m.end():end].strip()})
    assert len(options) >= 2, "Q%d 选项不足" % (qi + 1)
    assert all(a in [o["letter"] for o in options] for a in answer), "Q%d 答案超出选项" % (qi + 1)

    mcat = re.match(r"(\d+\.\d+)", label)
    cat = mcat.group(1) if mcat else label.split("—")[0]
    qtype = "multi" if "多项" in label else "single"

    questions.append({
        "n": qi + 1, "cat": cat, "type": qtype,
        "stem": stem, "options": options,
        "images": [], "answer": answer, "explanation": explanation,
        "exp_images": [], "_page": pi, "_y": pages[pi]["blocks"][bi]["y"],
    })

print("单选:", sum(1 for q in questions if q["type"] == "single"),
      "多选:", sum(1 for q in questions if q["type"] == "multi"))

# 5. 配图关联
os.makedirs(IMGDIR, exist_ok=True)
seen_hash = {}

def add_image(q, png_bytes, tag):
    h = hashlib.md5(png_bytes).hexdigest()
    if h in seen_hash:
        return
    seen_hash[h] = True
    fn = "%s/%s_%s.png" % (IMGDIR, tag, h[:12])
    open(fn, "wb").write(png_bytes)
    q["images"].append(fn)

for pi, pg in enumerate(pages):
    p = pg["page"]
    for im in p.get_images(full=True):
        xref = im[0]
        if (im[2], im[3]) in ((112, 30), (270, 19)):
            continue
        for r in p.get_image_rects(xref):
            yc = (r.y0 + r.y1) / 2
            owner = None
            for q in questions:
                if (q["_page"], q["_y"]) <= (pi, yc):
                    owner = q
            if owner:
                pix = pymupdf.Pixmap(d, xref)
                if pix.n > 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                add_image(owner, pix.tobytes("png"), "p%d" % pi)
                print("图 p%d/x%d -> Q%d (%s)" % (pi, xref, owner["n"], owner["cat"]))

tq = next(q for q in questions if q["_page"] == 5)
pix = p5.get_pixmap(dpi=150, clip=TABLE_BBOX)
tfn = "%s/table_p5.png" % IMGDIR
open(tfn, "wb").write(pix.tobytes("png"))
tq["images"].insert(0, tfn)
print("表格图 -> Q%d (%s)" % (tq["n"], tq["cat"]))

for q in questions:
    q.pop("_page")
    q.pop("_y")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=1)
print("写入", OUT, "共", len(questions), "题")
