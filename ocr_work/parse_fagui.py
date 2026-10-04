"""解析法规两套题（233网校阶段测评一/二）：带文字层 PDF -> questions_fagui1/2.json"""
import json, re

W = "/home/hatch/workspace/quizapp/ocr_work"
AD_PAT = re.compile(r"233网校|wx\.233\.com|全真机考")
HEAD_PAT = re.compile(r"唐忍-2026|安勇-2026|第\d+题 (单选|多选)题")

def clean(lines):
    out = []
    for l in lines:
        l = l.rstrip()
        if not l.strip():
            continue
        if AD_PAT.search(l):
            continue
        out.append(l)
    return out

def parse(path):
    lines = clean(open(path, encoding="utf-8").read().splitlines())
    # 分题面 / 答案区
    ai = next(i for i, l in enumerate(lines) if l.strip() == "答案解析")
    qlines, alines = lines[:ai], lines[ai + 1:]

    qs, cur, cur_opt, sect = [], None, None, "single"
    def flush():
        nonlocal cur, cur_opt
        if cur:
            cur["stem"] = cur["stem"].strip()
            qs.append(cur)
        cur, cur_opt = None, None

    for l in qlines:
        m = HEAD_PAT.search(l)
        if m:
            sect = "multi" if "多选" in l else "single"
            continue
        m = re.match(r"^(\d+)、(.*)$", l)
        if m:
            flush()
            cur = {"n": int(m.group(1)), "type": sect, "cat": "", "stem": m.group(2),
                   "options": [], "images": [], "exp_images": []}
            continue
        m = re.match(r"^([A-E])\.(.*)$", l)
        if m and cur:
            cur_opt = {"key": m.group(1), "text": m.group(2).strip()}
            cur["options"].append(cur_opt)
            continue
        if cur_opt:
            cur_opt["text"] += l.strip()
        elif cur:
            cur["stem"] += l.strip()
    flush()

    ans = {}
    cur_n = None
    for l in alines:
        m = re.match(r"^(\d+)、\s*答案：([A-E][A-E，,、\s]*)\s*(.*)$", l)
        if m:
            cur_n = int(m.group(1))
            letters = re.findall(r"[A-E]", m.group(2))
            ans[cur_n] = {"answer": letters, "explanation": m.group(3).strip()}
            continue
        if cur_n is not None and isinstance(ans.get(cur_n), dict):
            ans[cur_n]["explanation"] += l.strip()

    out = []
    for q in qs:
        a = ans.get(q["n"], {})
        answer = a.get("answer", [])
        out.append({**q, "type": "multi" if len(answer) > 1 else q["type"],
                    "answer": answer, "explanation": a.get("explanation", "")})
    return out

for tag, src in [("fagui1", "/tmp/fg1.txt"), ("fagui2", "/tmp/fg2.txt")]:
    qs = parse(src)
    ns = sorted(q["n"] for q in qs)
    sing = sum(1 for q in qs if q["type"] == "single")
    mult = sum(1 for q in qs if q["type"] == "multi")
    noans = [q["n"] for q in qs if not q["answer"] or not q["explanation"]]
    bad = [q["n"] for q in qs if len(q["options"]) not in (4, 5)]
    print(f"{tag}: 共{len(qs)}题 单选{sing} 多选{mult} 题号{ns[0]}..{ns[-1]} 缺答案/解析{noans} 选项异常{bad}")
    json.dump(qs, open(f"{W}/questions_{tag}.json", "w", encoding="utf-8"),
              ensure_ascii=False)
