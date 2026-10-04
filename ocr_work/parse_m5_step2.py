"""step2: m5_halves.json -> questions_m5_{1..5}.json (题目+答案按套配对, 严格校验)"""
import json, re, os

W = os.path.expanduser("~/workspace/quizapp/ocr_work")
halves = json.load(open(W + "/m5_halves.json"))

Q_PAT = re.compile(r"^(\d+)\s*[、.，,．·]\s*(.*)$")
O_PAT = re.compile(r"^([A-E])\s*[、.，,．·]\s*(.*)$")
A_PAT = re.compile(r"^(\d+)\s*[、.，,．·]\s*答案选\s*[【\[［「]([A-E\s,，、]+)[】\]］」]?\s*(.*)$")
JIE_PAT = re.compile(r"^[解解析]\s*[:：]\s*")
INNER_OPT = re.compile(r"([B-E])\s*[、.，,．·]")


def split_inner_opts(first_letter, text):
    parts, cur_l, pos = [], first_letter, 0
    for m in INNER_OPT.finditer(text):
        l = m.group(1)
        if l > cur_l:
            parts.append((cur_l, text[pos:m.start()].strip()))
            cur_l, pos = l, m.end()
    parts.append((cur_l, text[pos:].strip()))
    return parts


def reorder_options(opts, xys):
    """xys: (page, side, x, y). 只在同一 (page, side) 内按行重排, 不跨页."""
    if len(opts) <= 1:
        return opts
    segs, cur_seg = [], []
    for i in range(len(opts)):
        if cur_seg and (xys[i][0], xys[i][1]) != (xys[cur_seg[0]][0], xys[cur_seg[0]][1]):
            segs.append(cur_seg)
            cur_seg = []
        cur_seg.append(i)
    if cur_seg:
        segs.append(cur_seg)
    order = []
    for seg in segs:
        idx = sorted(seg, key=lambda i: xys[i][3])
        rows, cur_row = [], []
        for i in idx:
            if cur_row and abs(xys[i][3] - xys[cur_row[0]][3]) >= 25:
                rows.append(cur_row)
                cur_row = []
            cur_row.append(i)
        if cur_row:
            rows.append(cur_row)
        for r in rows:
            r.sort(key=lambda i: xys[i][2])
            order.extend(r)
    if order == list(range(len(opts))):
        return opts
    return [opts[i] for i in order]


def parse_questions(lines):
    qs, cur, cur_opt, cur_xy = [], None, None, None
    opt_xys = []

    def flush_opt():
        nonlocal cur_opt, cur_xy
        if cur and cur_opt is not None:
            cur["options"].append({"text": cur_opt.strip()})
            opt_xys.append(cur_xy)
            cur_opt, cur_xy = None, None

    def flush_q():
        nonlocal cur, opt_xys
        flush_opt()
        if cur:
            if opt_xys:
                cur["options"] = reorder_options(cur["options"], opt_xys)
            qs.append(cur)
            cur, opt_xys = None, []

    for e in lines:
        t, x, y = e["t"], e["x"], e["y"]
        pg, sd = e.get("p", -1), e.get("s", "")
        mq = Q_PAT.match(t)
        mo = O_PAT.match(t)
        if mq and not mo:
            flush_q()
            cur = {"n": int(mq.group(1)), "stem": mq.group(2).strip(), "options": []}
            cur_opt, cur_xy = None, None
        elif mo and cur is not None:
            flush_opt()
            parts = split_inner_opts(mo.group(1), mo.group(2).strip())
            for li, (pl, pt) in enumerate(parts):
                if li == 0:
                    cur_opt, cur_xy = pt, (pg, sd, x, y)
                else:
                    cur["options"].append({"text": cur_opt.strip()})
                    opt_xys.append(cur_xy)
                    cur_opt, cur_xy = pt, (pg, sd, x, y)
        else:
            if cur is None:
                continue
            if cur_opt is not None:
                cur_opt += t.strip()
            else:
                cur["stem"] += t.strip()
    flush_q()
    return qs


def parse_answers(lines):
    ans, cur = [], None

    def flush():
        nonlocal cur
        if cur:
            cur["explanation"] = JIE_PAT.sub("", cur["explanation"]).strip()
            ans.append(cur)
            cur = None

    for e in lines:
        t = e["t"]
        m = A_PAT.match(t)
        if m:
            flush()
            letters = sorted(set(re.findall(r"[A-E]", m.group(2))))
            cur = {"n": int(m.group(1)), "answer": letters,
                   "explanation": m.group(3).strip()}
        elif cur is not None:
            cur["explanation"] += t.strip()
    flush()
    return ans


for k in range(1, 6):
    qh = sorted([h for h in halves if h["set"] == k and not h["answer"]],
                key=lambda h: (h["page"], h["side"]))
    ah = sorted([h for h in halves if h["set"] == k and h["answer"]],
                key=lambda h: (h["page"], h["side"]))
    qlines = [l for h in qh for l in h["lines"]]
    alines = [l for h in ah for l in h["lines"]]
    qs = parse_questions(qlines)
    an = parse_answers(alines)
    qnums = [q["n"] for q in qs]
    anums = [a["n"] for a in an]
    ok = (qnums == list(range(1, len(qs) + 1)) and
          anums == list(range(1, len(an) + 1)) and
          len(qs) == 85 and len(an) == 85)
    issues = []
    if qnums != list(range(1, len(qs) + 1)):
        issues.append("Q nums broken: %s" % (qnums,))
    if anums != list(range(1, len(an) + 1)):
        issues.append("A nums broken: %s" % (anums,))
    amap = {a["n"]: a for a in an}
    out = []
    for q in qs:
        a = amap.get(q["n"])
        if not a:
            issues.append("Q%d missing answer" % q["n"])
            continue
        n_opts = len(q["options"])
        typ = "multi" if q["n"] >= 71 else "single"
        if typ == "single" and n_opts != 4:
            issues.append("Q%d single has %d opts" % (q["n"], n_opts))
        if typ == "multi" and n_opts != 5:
            issues.append("Q%d multi has %d opts" % (q["n"], n_opts))
        if typ == "single" and not (len(a["answer"]) == 1 and a["answer"][0] in "ABCD"):
            issues.append("Q%d bad single ans %s" % (q["n"], a["answer"]))
        if typ == "multi" and not (2 <= len(a["answer"]) <= 5):
            issues.append("Q%d bad multi ans %s" % (q["n"], a["answer"]))
        out.append({"n": q["n"], "type": typ, "cat": "", "stem": q["stem"],
                    "options": q["options"], "images": [], "exp_images": [],
                    "answer": a["answer"], "explanation": a["explanation"]})
    for q in out:
        if re.search(r"[图圖表]所示|见下[图表]|如[图圖]所示|下表", q["stem"]):
            issues.append("Q%d stem mentions 图/表: %s" % (q["n"], q["stem"][:40]))
    json.dump(out, open(W + "/questions_m5_%d.json" % k, "w", encoding="utf-8"),
              ensure_ascii=False)
    exp_empty = sum(1 for q in out if not q["explanation"])
    qr = (qh[0]["page"], qh[-1]["page"]) if qh else None
    ar = (ah[0]["page"], ah[-1]["page"]) if ah else None
    print("set%d: Q=%d A=%d emptyExp=%d qPages=%s aPages=%s %s" %
          (k, len(qs), len(an), exp_empty, qr, ar, "OK" if ok and not issues else "ISSUES"))
    for i in issues[:12]:
        print("   -", i)
