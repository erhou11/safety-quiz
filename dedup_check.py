#!/usr/bin/env python3
"""
查重脚本：新题入库前跑一遍，防止重复题/重复套混入。

用法：
    python3 dedup_check.py questions_full.json            # 查全库
    python3 dedup_check.py questions_full.json new_set.json # 新套入库前查重（new_set.json 为待入库套题 JSON）

规则：
  1) 题级查重：题干+选项归一化（去空白、去题号前缀）后完全相同的题，跨套分组报告（仅报告，不拦）。
  2) 套级查重：某套题 80% 以上的题目与另一套逐题相同（顺序无关）即判为"整套照搬"，告警并拦。
  3) 括号配对检查：题干+选项+解析里（　）/() 不配对的题逐题报告（早期 s8/s9 曾系统性丢"）"导致题干截断）。
退出码：0=干净；1=发现套级重复或括号不配对（并打印报告）。
"""
import json, re, sys
from collections import defaultdict


def norm_stem(stem: str) -> str:
    t = stem or ""
    t = re.sub(r"^[\d．.、\s]+", "", t)          # 剃掉题干自带题号
    t = re.sub(r"\s+", "", t)                   # 去所有空白
    t = t.replace("（　　）", "").replace("（）", "")
    return t


def norm_options(opts) -> str:
    parts = []
    for o in (opts or []):
        t = o.get("text", "") if isinstance(o, dict) else str(o)
        t = re.sub(r"^[A-ZＡ-Ｚ][.．、\s]+", "", t)  # 剃掉选项字母前缀
        parts.append(re.sub(r"\s+", "", t))
    return "|".join(parts)


def fingerprint(q) -> str:
    return norm_stem(q.get("stem", "")) + "‖" + norm_options(q.get("options", [])) \
        + "‖" + re.sub(r"\s+", "", q.get("case_bg", "") or "")


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict) and "questions" in d:
        return d["questions"], {s["id"]: s.get("title", s["id"]) for s in d.get("sets", [])}
    if isinstance(d, list):
        return d, {}
    raise ValueError("unrecognized question file format: " + path)


def main():
    lib_path = sys.argv[1]
    new_path = sys.argv[2] if len(sys.argv) > 2 else None

    questions, titles = load(lib_path)
    by_set = defaultdict(list)
    for q in questions:
        by_set[q["set"]].append(q)

    new_qs = []
    if new_path:
        nq, nt = load(new_path)
        new_qs = nq
        titles.update(nt)

    def label(sid):
        return f"{sid}《{titles.get(sid, sid)}》"

    # ---- 1) 题级查重 ----
    fp_map = defaultdict(list)
    for q in questions:
        fp_map[fingerprint(q)].append((q["set"], q["n"]))
    if new_qs:
        new_fps = {fingerprint(q) for q in new_qs}

    dup_groups = [v for v in fp_map.values() if len({s for s, _ in v}) > 1]
    cross_new = []
    if new_qs:
        for fp in new_fps:
            if fp in fp_map:
                cross_new.append((fp, fp_map[fp]))

    # ---- 2) 套级查重（整套照搬）----
    set_fps = {sid: {fingerprint(q) for q in qs} for sid, qs in by_set.items()}
    set_level = []
    sids = sorted(set_fps)
    for i in range(len(sids)):
        for j in range(i + 1, len(sids)):
            a, b = sids[i], sids[j]
            fa, fb = set_fps[a], set_fps[b]
            if not fa or not fb:
                continue
            inter = len(fa & fb)
            ratio_a, ratio_b = inter / len(fa), inter / len(fb)
            if ratio_a >= 0.8 or ratio_b >= 0.8:
                set_level.append((a, b, inter, ratio_a, ratio_b))

    # ---- 报告 ----
    problems = 0
    print("=" * 60)
    print("题级重复（跨套）：共 %d 组" % len(dup_groups))
    for g in sorted(dup_groups, key=lambda g: (g[0][0], g[0][1]))[:50]:
        locs = ", ".join(f"{sid}#{n}" for sid, n in g)
        print(f"  - {locs}")
    if len(dup_groups) > 50:
        print(f"  …另有 {len(dup_groups) - 50} 组未列出")
    # 题级跨套重复仅报告（同系列卷子撞单题属正常），不计入问题、不影响退出码

    print("=" * 60)
    print(f"套级重复（80%以上题目相同，即整套照搬）：共 {len(set_level)} 对")
    for a, b, inter, ra, rb in set_level:
        print(f"  - {label(a)} × {label(b)}：{inter} 题相同（{ra:.0%}/{rb:.0%}）")
    if set_level:
        problems += 1

    if new_qs:
        print("=" * 60)
        print("新套与库内重复：共 %d 题" % len(cross_new))
        for _, locs in cross_new[:30]:
            print("  - 库内已有：%s" % ", ".join(f"{sid}#{n}" for sid, n in locs))
        if cross_new:
            problems += 1

    # ---- 3) 括号配对检查 ----
    def paren_ok(text):
        stack = []
        pairs = {")": "(", "）": "（"}
        for ch in text or "":
            if ch in "(（":
                stack.append(ch)
            elif ch in pairs:
                if not stack or stack[-1] != pairs[ch]:
                    return False
                stack.pop()
        return not stack

    bad_paren = []
    check_qs = questions + (new_qs if new_qs else [])
    for q in check_qs:
        blob = (q.get("stem", "") or "") + "\n".join(
            (o.get("text", "") if isinstance(o, dict) else str(o)) for o in (q.get("options") or [])
        ) + (q.get("explanation", "") or "")
        if not paren_ok(blob):
            bad_paren.append((q["set"], q["n"]))

    print("=" * 60)
    print(f"括号不配对：共 {len(bad_paren)} 题")
    for sid, n in bad_paren[:30]:
        print(f"  - {sid}#{n}")
    if len(bad_paren) > 30:
        print(f"  …另有 {len(bad_paren) - 30} 题未列出")
    if bad_paren:
        problems += 1

    print("=" * 60)
    if problems == 0:
        print("结论：干净，无跨套重复。")
    else:
        print("结论：发现重复，入库前请先处理。")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
