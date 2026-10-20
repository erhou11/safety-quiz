"""解析技术基础最后一套题：带文字层 PDF -> jishu_last.json"""
import fitz
import re
import json

PDF = "/home/hatch/workspace/user/files/________1_p2v7.pdf"
doc = fitz.open(PDF)
full = ""
for p in doc:
    full += p.get_text() + "\n"

# 1) 去整页广告（插在正文中）
full = re.sub(r"【考友之家】[^。\n]*(?:押题|课程)[^。\n]*", "", full)
# 2) 去页码 "17 / 35"
full = re.sub(r"\b\d+\s*/\s*35\b", "", full)
# 3) 去页眉短行
AD = re.compile(r"本质筑安|考注安|更简单|课程咨询请扫码|^\d+$")
lines = []
for l in full.split("\n"):
    l = l.rstrip()
    if not l.strip():
        continue
    if AD.search(l) and len(l) < 30:
        continue
    lines.append(l)
text = "\n".join(lines)

# 切题面区 / 答案区
ai = text.find("参考答案")
qtext = text[:ai]
atext = text[ai:]

QM = re.compile(r"(?m)^(\d+)、\s*")

def parse_questions(t):
    # 找单选/多选分界
    mi = t.find("多选题")
    parts = [(t[:mi], "single"), (t[mi:], "multi")]
    qs = {}
    for seg, typ in parts:
        blocks = QM.split(seg)
        for i in range(1, len(blocks), 2):
            n = int(blocks[i])
            body = blocks[i + 1]
            om = list(re.finditer(r"(?m)^([A-E])[.．]\s*", body))
            if not om:
                qs[n] = {"n": n, "type": typ, "stem": body.strip().replace("\n", ""), "options": []}
                continue
            stem = body[:om[0].start()].strip().replace("\n", "")
            opts = []
            for j, m in enumerate(om):
                end = om[j + 1].start() if j + 1 < len(om) else len(body)
                opts.append({"key": m.group(1),
                             "text": body[m.end():end].strip().replace("\n", "")})
            qs[n] = {"n": n, "type": typ, "stem": stem, "options": opts}
    return qs

AM = re.compile(r"(?m)^(\d+)、\s*([A-E]+)\s*")

def parse_answers(t):
    blocks = AM.split(t)
    ans = {}
    for i in range(1, len(blocks), 3):
        n = int(blocks[i])
        letters = list(blocks[i + 1])
        exp = blocks[i + 2].strip().replace("\n", "")
        ans[n] = {"answer": letters, "explanation": exp}
    return ans

qs = parse_questions(qtext)
ans = parse_answers(atext)
out = []
for n in sorted(qs):
    q = qs[n]
    a = ans.get(n, {})
    q["answer"] = a.get("answer", [])
    q["explanation"] = a.get("explanation", "")
    if len(q["answer"]) > 1:
        q["type"] = "multi"
    out.append(q)

sing = sum(1 for q in out if q["type"] == "single")
mult = sum(1 for q in out if q["type"] == "multi")
noans = [q["n"] for q in out if not q["answer"]]
noexp = [q["n"] for q in out if not q["explanation"]]
badopt = [q["n"] for q in out if len(q["options"]) not in (4, 5)]
print("共%d题 单选%d 多选%d" % (len(out), sing, mult))
print("缺答案:", noans)
print("缺解析:", noexp)
print("选项异常:", badopt)
json.dump(out, open("/home/hatch/workspace/quizapp/ocr_work/jishu_last.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved jishu_last.json")
