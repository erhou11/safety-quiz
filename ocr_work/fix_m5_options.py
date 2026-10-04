"""step3: 对 questions_m5_{1..5}.json 做定向修复(逐题原图核对过)."""
import json, os, copy

W = os.path.expanduser("~/workspace/quizapp/ocr_work")

def load(k):
    return json.load(open(W + "/questions_m5_%d.json" % k, encoding="utf-8"))

def save(k, qs):
    json.dump(qs, open(W + "/questions_m5_%d.json" % k, "w", encoding="utf-8"),
              ensure_ascii=False)

def get(qs, n):
    for q in qs:
        if q["n"] == n:
            return q
    raise ValueError("Q%d not found" % n)

def set_opts(q, texts):
    q["options"] = [{"text": t} for t in texts]

# ---------- set1 ----------
qs = load(1)
q = get(qs, 1)
set_opts(q, [q["options"][0]["text"], q["options"][1]["text"],
             "交通运输主管部门负责核发剧毒化学品道路运输通行证",
             q["options"][2]["text"]])
q = get(qs, 3)
# "、化工园区..." 是误读的 A 选项(目前粘在题干尾)
a3 = "化工园区应当由设区的市级人民政府或者其授权的部门认定公布并定期复核"
i = q["stem"].rfind("、" + a3[:6])
assert i > 0, q["stem"][-30:]
q["stem"] = q["stem"][:i]
set_opts(q, [a3] + [o["text"] for o in q["options"]])
q = get(qs, 6)
set_opts(q, [o["text"] for o in q["options"]] +
         ["申请人持危险化学品经营许可证即可从事危险化学品经营活动"])
q = get(qs, 26)
set_opts(q, ["用人单位的工作人员因执行工作任务造成他人损害的，由用人单位承担侵权责任"] +
         [o["text"] for o in q["options"]])
save(1, qs)

# ---------- set2 ----------
qs = load(2)
q = get(qs, 21)
frag = "督检查职责，应当停工配合，不得拒绝、阻挠"
assert frag in q["stem"], q["stem"][-40:]
q["stem"] = q["stem"].replace(frag, "")
a21 = "生产经营单位对负有安全生产监督管理职责的部门的监督检查人员依法履行监督检查职责，应当停工配合，不得拒绝、阻挠"
set_opts(q, [a21] + [o["text"] for o in q["options"]])
q = get(qs, 49)
d49 = "具备相应资质的培训机构培训合格后，由培训机构发给相应的培训合格证书"
c = q["options"][2]["text"]
assert c.endswith(d49), c[-30:]
q["options"][2]["text"] = c[: -len(d49)]
set_opts(q, [o["text"] for o in q["options"]] + [d49])
q = get(qs, 53)
tail53 = "理情况统计分析表，并由本单位安全生产管理人员签字"
b = q["options"][1]["text"]
assert b.endswith(tail53), b[-30:]
q["options"][1]["text"] = b[: -len(tail53)]
c53 = "生产经营单位应当向安全监管监察部门和有关部门报送书面的事故隐患排查治理情况统计分析表，并由本单位安全生产管理人员签字"
opts = [o["text"] for o in q["options"]]
set_opts(q, opts[:2] + [c53] + opts[2:])
q = get(qs, 69)
tail69 = "工作业”证书"
c = q["options"][2]["text"]
assert c.endswith(tail69), c[-20:]
q["options"][2]["text"] = c[: -len(tail69)]
d69 = "取得有效“高压电工作业”证书的人员，从事低压电工作业需要取得“低压电工作业”证书"
set_opts(q, [o["text"] for o in q["options"]] + [d69])
q = get(qs, 77)
opts = [o["text"] for o in q["options"]]
set_opts(q, opts[:3] + ["社会保险行政部门应当自受理工伤认定申请之日起60日内作出工伤认定的决定"] + opts[3:])
q = get(qs, 81)
opts = [o["text"] for o in q["options"]]
set_opts(q, opts[:2] + ["工贸企业应当每年至少组织一次有限空间作业专题安全培训"] + opts[2:])
save(2, qs)

# ---------- set3 ----------
qs = load(3)
q = get(qs, 26)
set_opts(q, [o["text"] for o in q["options"]] +
         ["负责特种设备安全监督管理的部门的安全监察人员必须取得特种设备安全行政执法证件"])
q = get(qs, 70)
opts = [o["text"] for o in q["options"]]
assert len(opts) == 3, opts
set_opts(q, opts[:2] + ["对非高危行业领域安全生产标准化一级企业年度内累计执法检查不超过2次"] + opts[2:])
save(3, qs)

# ---------- set4 ----------
qs = load(4)
q = get(qs, 6)
set_opts(q, ["个人不得购买剧毒化学品（包括剧毒化学品的农药）"] +
         [o["text"] for o in q["options"]])
q = get(qs, 14)
assert q["stem"].endswith("成绩"), q["stem"][-20:]
q["stem"] = q["stem"][: -len("成绩")]
a14 = "考核发证机关或者其委托的考试机构应当在考试结束后10个工作日内公布考试成绩"
set_opts(q, [a14] + [o["text"] for o in q["options"]])
q = get(qs, 53)
tail = "统计分析表报国家安全生产监督管理总局备案"
b = q["options"][1]["text"]
assert b.endswith(tail), b[-30:]
q["options"][1]["text"] = b[: -len(tail)]
c53 = "省级安全监管监察部门应当每年将本行政区域重大事故隐患的排查治理情况和统计分析表报国家安全生产监督管理总局备案"
opts = [o["text"] for o in q["options"]]
set_opts(q, opts[:2] + [c53] + opts[2:])
q = get(qs, 59)
set_opts(q, [o["text"] for o in q["options"]] +
         ["可燃性粉尘不得与可燃气体等易加剧爆炸危险的介质共用一套除尘系统"])
q = get(qs, 73)
opts = [o["text"] for o in q["options"]]
assert len(opts) == 4, [o[:15] for o in opts]
assert opts[0].startswith("生产经营单位应当投保"), opts[0][:15]
b73 = opts[1]
assert b73.endswith("或者个人"), b73[-10:]
opts[1] = b73[: -len("或者个人")]
assert opts[2].startswith("生产经营单位必须依法参加工伤保险"), opts[2][:15]
assert opts[3].startswith("生产经营单位通过市场调研"), opts[3][:15]
c73 = "发包人在任何情况下都不得将生产经营项目发包给不具备安全生产条件的单位或者个人"
set_opts(q, opts[:2] + [c73] + opts[2:])
save(4, qs)

# ---------- set5 ----------
qs = load(5)
q = get(qs, 18)
opts = [o["text"] for o in q["options"]]
set_opts(q, opts[:2] + ["对在检查中发现重大事故隐患，应当告知负有安全生产监督管理职责的部门"] + opts[2:])
q = get(qs, 19)
opts = [o["text"] for o in q["options"]]
assert len(opts) == 5, [o[:20] for o in opts]
fake = opts[0]
assert fake.startswith("B两区相邻"), fake[:20]
q["stem"] = q["stem"] + "A、" + fake
assert q["stem"].endswith("正确的是（）"), q["stem"][-15:]
set_opts(q, opts[1:])
q = get(qs, 51)
set_opts(q, ["施工单位项目负责人、总监理工程师"] +
         [o["text"] for o in q["options"]])
save(5, qs)

print("all targeted fixes applied")
