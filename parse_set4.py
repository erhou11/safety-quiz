#!/usr/bin/env python3
"""解析《点题锁分一（一）》第01讲 -> questions_set4.json
版式：单栏；题间无数字题号，以【X.X—单/多项选择题】分隔；答案【答案】X【解析】…内联。
"""
import pymupdf, re, json, os, hashlib

SRC = "/home/hatch/workspace/user/files/8-3____8____3_2026______________________3_au4o.pdf"
OUT = "/home/hatch/workspace/quizapp/questions_set4.json"
IMGDIR = "/tmp/set4_img"
os.makedirs(IMGDIR, exist_ok=True)

d = pymupdf.open(SRC)
FW = "ＡＢＣＤＥ"
def norm_letter(c):
    return chr(ord("A") + FW.index(c)) if c in FW else c

# 题目文本：按页顺序拼接，过滤页眉页脚
pages_text = []
for pi, p in enumerate(d):
    parts = []
    for b in p.get_text("blocks"):
        t = b[4].strip()
        if not t:
            continue
        if b[0] > 400 and b[1] < 60:
            continue  # 页眉logo
        if b[1] > 750:
            continue  # 页脚
        parts.append(t)
    pages_text.append("\n".join(parts))
full = "\n".join(pages_text)

marks = list(re.finditer(r"【(\d+\.\d+)[^】]*?([单多])项选择题】", full))
print("标记数:", len(marks))
assert len(marks) == 85, f"标记数异常: {len(marks)}"

questions = []
for i, m in enumerate(marks):
    n = i + 1
    cat, typ_c = m.group(1), m.group(2)
    typ = "multi" if typ_c == "多" else "single"
    chunk = full[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(full)]
    am = re.search(r"【答案】([A-EＡ-Ｅ]+)", chunk)
    assert am, f"Q{n} 无答案"
    ans = [norm_letter(c) for c in am.group(1)]
    em = re.search(r"【解析】", chunk)
    assert em, f"Q{n} 无解析"
    opt_part = chunk[:am.start()]
    exp = chunk[em.end():].strip()
    om = list(re.finditer(r"([A-EＡ-Ｅ])．", opt_part))
    assert len(om) >= 4, f"Q{n} 选项不足: {len(om)}"
    stem = opt_part[:om[0].start()].strip()
    opts = []
    for j, o in enumerate(om):
        t = opt_part[o.end():om[j + 1].start() if j + 1 < len(om) else len(opt_part)]
        opts.append({"letter": norm_letter(o.group(1)), "text": re.sub(r"\s+", " ", t).strip()})
    questions.append({"n": n, "cat": cat, "type": typ, "stem": stem,
                      "options": opts, "images": [],
                      "answer": ans, "explanation": re.sub(r"\s+", " ", exp).strip()})
print("题目:", len(questions), "单选:", sum(1 for q in questions if q["type"] == "single"),
      "多选:", sum(1 for q in questions if q["type"] == "multi"))

# 图片归属：(页, y) 最近的上方标记
mpos = []
for pi, p in enumerate(d):
    for b in p.get_text("blocks"):
        for m in re.finditer(r"【(\d+\.\d+)[^】]*?([单多])项选择题】", b[4]):
            mpos.append((pi, b[1], len(mpos)))
mpos.sort()
img_assign = {}
for pi, p in enumerate(d):
    for im in p.get_images(full=True):
        try:
            r = p.get_image_bbox(im)
        except ValueError:
            continue
        if r.x0 > 400 or r.y0 > 750 or r.y0 < 60:
            continue
        if im[2] < 100 or im[3] < 80:
            continue
        owner = None
        for (mpi, my, idx) in mpos:
            if (mpi, my) < (pi, r.y0):
                owner = idx
            else:
                break
        if owner is None:
            print(f"  警告: p{pi+1} 图片无归属")
            continue
        pix = p.get_pixmap(clip=r, dpi=150)
        fn = f"p{pi+1}_q{owner+1}_{hashlib.sha256(pix.tobytes()).hexdigest()[:8]}.png"
        fp = os.path.join(IMGDIR, fn)
        pix.save(fp)
        img_assign.setdefault(owner + 1, []).append(fp)
        print(f"  图片 p{pi+1} -> Q{owner+1}")
for q in questions:
    if q["n"] in img_assign:
        q["images"] = img_assign[q["n"]]
print("带图题数:", len(img_assign))

# 校验
for q in questions:
    letters = [o["letter"] for o in q["options"]]
    assert letters == ["A", "B", "C", "D"][:len(letters)] or letters == ["A", "B", "C", "D", "E"], f"Q{q['n']} 选项字母异常"
    assert all(c in letters for c in q["answer"]), f"Q{q['n']} 答案不在选项中"
    assert (q["type"] == "single") == (len(q["answer"]) == 1), f"Q{q['n']} 单多不符"
    assert q["explanation"], f"Q{q['n']} 解析为空"
    assert "【答案】" not in q["stem"] and "【解析】" not in q["stem"], f"Q{q['n']} 题干污染"

json.dump(questions, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写入:", OUT)
for n in (1, 2, 26, 71, 85):
    q = questions[n - 1]
    print(f"Q{n} [{q['type']}] cat={q['cat']} 选项={len(q['options'])} 图={len(q['images'])} 答案={q['answer']}")
