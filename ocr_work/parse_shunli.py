"""解析顺利1/2：扫描版 OCR 文本 -> questions_set8/9.json
题PDF: slq1/slq2 (N、题干 / X、选项)；答案PDF: sla1/slq2 -> sla1/sla2 (N. 答案：X / 解析：)
"""
import json, re, os

W = os.path.expanduser("~/workspace/quizapp/ocr_work")
ocr = json.load(open(f"{W}/ocr_lines.json"))

AD_PAT = re.compile(r"最顶级VIP|小初高|注安技术押题|单选题|多选题|第\d+页")
WM_PAT = re.compile(r"微信|872117")
WM_ONLY = re.compile(r"[微信顺利用押题加：:0-9\s]{1,8}\Z")
Q_PAT = re.compile(r"^(\d+)、(.*)$")
O_PAT = re.compile(r"^([A-E])、(.*)$")
A_PAT = re.compile(r"^(\d+)[.．]\s*答案[:：]\s*([A-E]+)")

def clean_lines(tag_prefix, skip_prefixes=()):
    """合并多页 OCR 行，过滤广告/水印/页眉页脚，返回干净文本行列表"""
    tags = sorted([t for t in ocr if t.startswith(tag_prefix)],
                  key=lambda t: int(t.rsplit("_p", 1)[1]))
    lines = []
    for t in tags:
        for l in ocr[t]:
            s = l["t"].strip()
            if not s:
                continue
            if AD_PAT.search(s):
                continue
            if WM_PAT.search(s) and not Q_PAT.match(s) and not O_PAT.match(s) and not A_PAT.match(s):
                continue
            if WM_ONLY.match(s):
                continue
            lines.append(s)
    return lines

def parse_questions(tag_prefix):
    lines = clean_lines(tag_prefix)
    # 找到多选题起始
    qs, cur, cur_opt = [], None, None
    def flush_opt():
        nonlocal cur_opt
        if cur is not None and cur_opt is not None:
            cur["options"].append(cur_opt); cur_opt = None
    def flush_q():
        nonlocal cur
        flush_opt()
        if cur is not None:
            cur["stem"] = "".join(cur["stem"]).strip()
            cur["options"] = [{"k": k, "t": "".join(v).strip()} for k, v in cur["options"]]
            qs.append(cur); cur = None
    for s in lines:
        m = Q_PAT.match(s)
        if m:
            flush_q()
            cur = {"n": int(m.group(1)), "stem": [m.group(2)], "options": []}
            cur_opt = None
            continue
        m = O_PAT.match(s)
        if m and cur is not None:
            flush_opt()
            cur_opt = [m.group(1), m.group(2)]
            continue
        # 续行
        if cur_opt is not None:
            cur_opt[1] += s
        elif cur is not None:
            cur["stem"].append(s)
    flush_q()
    return qs

def parse_answers(tag_prefix):
    lines = clean_lines(tag_prefix)
    ans, cur = {}, None
    def flush():
        nonlocal cur
        if cur is not None:
            ans[cur["n"]] = cur; cur = None
    for s in lines:
        m = A_PAT.match(s)
        if m:
            flush()
            rest = s[m.end():].strip()
            cur = {"n": int(m.group(1)), "answer": list(m.group(2)),
                   "exp": [rest[3:].strip()] if rest.startswith("解析") else ([rest] if rest else [])}
            # 处理 "答案：C 解析：xxx" 同行
            pm = re.search(r"解析[:：](.*)$", rest)
            if pm:
                cur["exp"] = [pm.group(1).strip()]
            continue
        if cur is not None:
            s2 = re.sub(r"^解析[:：]", "", s)
            cur["exp"].append(s2)
    flush()
    for v in ans.values():
        v["explanation"] = "".join(v.pop("exp")).strip()
    return ans

def build(qtag, atag, out, title, kicker, desc):
    qs = parse_questions(qtag)
    ans = parse_answers(atag)
    out_qs = []
    problems = []
    for q in qs:
        a = ans.get(q["n"])
        if a is None:
            problems.append(f"Q{q['n']}: 无答案")
            continue
        for L in a["answer"]:
            if L not in [o["k"] for o in q["options"]]:
                problems.append(f"Q{q['n']}: 答案{L}不在选项中")
        typ = "multi" if len(a["answer"]) > 1 else "single"
        out_qs.append({
            "n": q["n"], "type": typ, "cat": "",
            "stem": q["stem"],
            "options": [{"key": o["k"], "text": o["t"]} for o in q["options"]],
            "answer": a["answer"], "explanation": a["explanation"],
            "images": [], "exp_images": [],
        })
    # 连续性检查
    nums = [q["n"] for q in qs]
    missing = sorted(set(range(1, 86)) - set(nums))
    dup = sorted(set(n for n in nums if nums.count(n) > 1))
    opt_bad = [(q["n"], len(q["options"])) for q in qs if len(q["options"]) not in (4, 5)]
    print(f"{out}: 题目{len(qs)} 答案{len(ans)} 缺题{missing} 重复{dup}")
    print(f"  选项数异常: {opt_bad[:12]}")
    print(f"  单选{sum(1 for q in out_qs if q['type']=='single')} 多选{sum(1 for q in out_qs if q['type']=='multi')}")
    for p in problems[:12]:
        print("  !!", p)
    fig = [q["n"] for q in out_qs if re.search(r"如图|所示|见图|见下表", q["stem"])]
    print(f"  涉图题(扫描版无图可提): {fig}")
    json.dump(out_qs, open(f"{W}/{out}", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out_qs

if __name__ == "__main__":
    import sys
    build("slq1", "sla1", "questions_set8.json", "技术顺利1套", "注安技术顺利", "注安技术押题1")
    build("slq2", "sla2", "questions_set9.json", "技术顺利2套", "注安技术顺利", "注安技术押题2")
