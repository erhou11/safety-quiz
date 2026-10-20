"""解析法规徐美丽仿真B卷：带文字层 PDF -> fagui_B.json"""
import fitz
import re
import json

PDF = "/home/hatch/workspace/user/files/______B__0_whwv.pdf"
doc = fitz.open(PDF)
full = ""
for p in doc:
    full += p.get_text() + "\n"

AD = re.compile(r"本质筑安|考注安|更简单|课程咨询请扫码|考友之家|微信[:：]1224487762|提供\s*一二建|^\d+$")
lines = []
for l in full.split("\n"):
    l = l.rstrip()
    if not l.strip():
        continue
    if AD.search(l) and len(l) < 30:
        continue
    lines.append(l)
text = "\n".join(lines)
# 去除插在正文中的整页广告
text = re.sub(r"【考友之家】[^。\n]*?(?:押题|课程)[^。\n]*", "", text)

ai = text.find("答案版")
qtext = text[:ai]
atext = text[ai:]

QM = re.compile(r"【(单选|多选)】\s*(\d+)\s*[.．、]")

def parse_questions(t):
    parts = QM.split(t)
    qs = {}
    for i in range(1, len(parts), 3):
        typ = parts[i]
        n = int(parts[i + 1])
        body = parts[i + 2]
        om = list(re.finditer(r"(?m)^([A-E])[.．]\s*", body))
        if not om:
            qs[n] = {"n": n, "type": "single" if typ == "单选" else "multi",
                     "stem": body.strip(), "options": []}
            continue
        stem = body[:om[0].start()].strip()
        opts = []
        for j, m in enumerate(om):
            end = om[j + 1].start() if j + 1 < len(om) else len(body)
            opts.append({"key": m.group(1),
                         "text": body[m.end():end].strip().replace("\n", "")})
        qs[n] = {"n": n, "type": "single" if typ == "单选" else "multi",
                 "stem": stem.replace("\n", ""), "options": opts}
    return qs

def parse_answers(t):
    parts = QM.split(t)
    ans = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i + 1])
        body = parts[i + 2]
        ma = re.search(r"【(?:参考)?答案】\s*([A-E]+)", body)
        if not ma:
            continue
        letters = list(ma.group(1))
        me = re.search(r"【(?:参考)?解析】", body)
        exp = ""
        if me:
            exp = body[me.end():].strip().replace("\n", "")
            exp = re.sub(r"【考友之家】.*", "", exp)
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
json.dump(out, open("/home/hatch/workspace/quizapp/ocr_work/fagui_B.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved fagui_B.json")
