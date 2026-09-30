#!/usr/bin/env python3
"""解析李天宇8套卷·第6套（模考大赛班）-> questions_set6.json
版式：题目区 1-17 页双栏；答案区 18-27 页双栏（"N、答案：X 解析：…"）。
"""
import pymupdf, re, json, os, hashlib

SRC = "/home/hatch/workspace/user/files/___8____6_2026_______________5_pnd9.pdf"
OUT = "/home/hatch/workspace/quizapp/questions_set6.json"
IMGDIR = "/tmp/set6_img"
os.makedirs(IMGDIR, exist_ok=True)

d = pymupdf.open(SRC)
N_PAGES = len(d)

def blocks_of(pi):
    out = []
    for b in d[pi].get_text("blocks"):
        t = b[4].strip()
        if not t:
            continue
        if re.fullmatch(r"\d+ / 27", t):
            continue
        out.append({"x": b[0], "y": b[1], "rect": pymupdf.Rect(b[:4]), "text": t})
    return out

def skip_block(t):
    return ("233网校" in t or "wx.233.com" in t or "李天宇8套卷" in t
            or (t.startswith("第") and ("单选题" in t or "多选题" in t))
            or t == "答案解析" or "扫码下载" in t or "免费题库" in t
            or "考证就上" in t)

def col_order_text(pi, y_max=None, y_min=None):
    cols = {0: [], 1: []}
    for b in blocks_of(pi):
        if skip_block(b["text"]):
            continue
        if y_max is not None and b["y"] > y_max:
            continue
        if y_min is not None and b["y"] < y_min:
            continue
        cols[0 if b["x"] < 200 else 1].append(b)
    parts = []
    for c in (0, 1):
        for b in sorted(cols[c], key=lambda b: (b["y"], b["x"])):
            parts.append(b["text"])
    return "\n".join(parts)

# ---------- 1. 题目 ----------
qtext = "\n".join(col_order_text(pi) for pi in range(17))
marks = list(re.finditer(r"(?m)^(\d+)、(?:\d+\.)?【([^】]+)】", qtext))
print("题目标记数:", len(marks))

questions = []
for i, m in enumerate(marks):
    n = int(m.group(1))
    cat_raw = m.group(2)
    cat = cat_raw.split("—")[0]
    typ = "multi" if "多项" in cat_raw else "single"
    chunk = qtext[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(qtext)]
    om = list(re.finditer(r"(?m)^([A-E])\.\s*", chunk))
    assert len(om) >= 4, f"Q{n} 选项不足: {len(om)}"
    stem = chunk[:om[0].start()].strip()
    opts = []
    for j, o in enumerate(om):
        t = chunk[o.end():om[j + 1].start() if j + 1 < len(om) else len(chunk)]
        t = re.sub(r"\s+", " ", t).strip()
        opts.append({"letter": o.group(1), "text": t})
    questions.append({"n": n, "cat": cat, "type": typ, "stem": stem,
                      "options": opts, "images": []})
print("题目数:", len(questions), "单选:", sum(1 for q in questions if q["type"] == "single"),
      "多选:", sum(1 for q in questions if q["type"] == "multi"))
assert [q["n"] for q in questions] == list(range(1, 86)), "题号不连续"

# ---------- 2. 图片归属 ----------
qpos = []
for pi in range(17):
    for b in blocks_of(pi):
        if skip_block(b["text"]):
            continue
        m = re.match(r"(\d+)、(?:\d+\.)?【", b["text"])
        if m:
            qpos.append((pi, 0 if b["x"] < 200 else 1, b["y"], int(m.group(1))))
qpos.sort()
img_assign = {}
seen = 0
for pi in range(17):
    p = d[pi]
    for im in p.get_images(full=True):
        if im[2] < 150 or im[3] < 100:
            continue
        try:
            r = p.get_image_bbox(im)
        except ValueError:
            continue
        if r.y0 < 70 and pi == 0:
            continue
        col = 0 if r.x0 < 200 else 1
        key = (pi, col, r.y0)
        owner = None
        for qp in qpos:
            if (qp[0], qp[1], qp[2]) < key:
                owner = qp
            else:
                break
        if owner is None:
            print(f"  警告: p{pi+1} 图片无归属")
            continue
        pix = p.get_pixmap(clip=r, dpi=150)
        fn = f"p{pi+1}_{owner[3]}_{hashlib.sha256(pix.tobytes()).hexdigest()[:8]}.png"
        fp = os.path.join(IMGDIR, fn)
        pix.save(fp)
        img_assign.setdefault(owner[3], []).append(fp)
        seen += 1
        print(f"  图片 p{pi+1} -> Q{owner[3]}")
for q in questions:
    if q["n"] in img_assign:
        q["images"] = img_assign[q["n"]]
print("配图总数:", seen, "带图题数:", len(img_assign))

# ---------- 3. 答案 ----------
atext = "\n".join(col_order_text(pi) for pi in range(17, N_PAGES))
am = list(re.finditer(r"(?m)^(\d+)、\s*\n答案：([A-E，,、\s]+)\s*\n解析：", atext))
print("答案条目数:", len(am))
answers = {}
for i, m in enumerate(am):
    n = int(m.group(1))
    ans = [c for c in m.group(2) if c in "ABCDE"]
    end = am[i + 1].start() if i + 1 < len(am) else len(atext)
    exp = atext[m.end():end].strip()
    exp = re.sub(r"\s*\n答案：[A-E，,、\s]*\n\d+、\s*\n解析：.*$", "", exp, flags=re.S)
    answers[n] = {"answer": ans, "explanation": re.sub(r"\s+", " ", exp).strip()}
# 兜底：翻转排版（答案：X 与 N、在同一块，答案在前）
for m in re.finditer(r"(?m)^答案：([A-E，,、\s]+)\s*\n(\d+)、\s*\n解析：", atext):
    n = int(m.group(2))
    if n in answers:
        continue
    ans = [c for c in m.group(1) if c in "ABCDE"]
    nxt = re.search(r"(?m)^(?:\d+)、", atext[m.end():])
    end = m.end() + nxt.start() if nxt else len(atext)
    answers[n] = {"answer": ans, "explanation": re.sub(r"\s+", " ", atext[m.end():end]).strip()}
    print(f"  兜底解析 Q{n}: 答案={ans}")
# 兜底2："答案：C 47、" 同行翻转
for m in re.finditer(r"答案：([A-E，,、\s]+?)\s+(\d+)、", atext):
    n = int(m.group(2))
    if n in answers:
        continue
    ans = [c for c in m.group(1) if c in "ABCDE"]
    nxt = re.search(r"(?m)^(?:\d+)、", atext[m.end():])
    end = m.end() + nxt.start() if nxt else len(atext)
    exp = atext[m.end():end].strip()
    exp = re.sub(r"^解析：", "", exp)
    answers[n] = {"answer": ans, "explanation": re.sub(r"\s+", " ", exp).strip()}
    print(f"  兜底2解析 Q{n}: 答案={ans}")
missing = sorted(set(range(1, 86)) - set(answers))
print("缺答案:", missing)
assert not missing, f"缺答案: {missing}"

for q in questions:
    a = answers[q["n"]]
    q["answer"] = a["answer"]
    q["explanation"] = a["explanation"]
    letters = [o["letter"] for o in q["options"]]
    assert all(c in letters for c in a["answer"]), f"Q{q['n']} 答案 {a['answer']} 不在选项中"

json.dump(questions, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写入:", OUT)
for n in (1, 2, 10, 46, 71, 85):
    q = questions[n - 1]
    print(f"Q{n} [{q['type']}] cat={q['cat']} 选项={len(q['options'])} 图={len(q['images'])} 答案={q['answer']} 解析={q['explanation'][:28]}")
