# Step1: 解析题目（PDF pp 1,2,4,5,6,7,8,9,10,11）
import json, re

out = json.load(open('ocr_hg.json', encoding='utf-8'))
# PDF页(跳过广告p3)
QPAGES = [1,2,4,5,6,7,8,9,10,11]

def clean_lines(pg):
    res = []
    for e in out[str(pg)]:
        t = e['t'].strip()
        if not t: continue
        if '最顶级VIP' in t or '注安、初会' in t: continue
        if re.match(r'^\d+\s*/\s*17$', t): continue
        if t in ('微信：872117', '233网校', 'www.233.com'): continue
        if t.startswith('全真机考'): continue
        if '加微信' in t and len(t) < 30: continue  # 水印行
        if re.match(r'^8721?17?$', t): continue
        res.append(t)
    return res

full = []
for pg in QPAGES:
    full.extend([(pg, t) for t in clean_lines(pg)])

text = '\n'.join(t for _, t in full)
# print(text[:2000])

questions = {}  # n -> dict

# ---------- Q1-20 单选 ----------
# 题号模式: 行首 "N、"
qpat = re.compile(r'^(\d{1,2})、')
cur = None
buf = []
def flush():
    global cur, buf
    if cur and buf:
        questions[cur] = '\n'.join(buf)
    cur, buf = None, []

for pg, t in full:
    m = qpat.match(t)
    if m and int(m.group(1)) <= 20:
        flush(); cur = int(m.group(1)); buf = [t]
    elif cur:
        # 遇到第2题/第3题标题则结束
        if t.startswith('第2题') or t.startswith('第3题'):
            flush(); break
        buf.append(t)
flush()

print('Q1-20 parsed:', sorted(questions.keys()))

# 选项切分
def split_options(qtext):
    # 按行首 A. B. C. D. (E.) 切分
    lines = qtext.split('\n')
    stem_lines, opts, cur_o = [], [], None
    for ln in lines:
        m = re.match(r'^([A-E])\s*[.．、]\s*(.*)$', ln)
        if m and not (len(ln) < 6 and not m.group(2)):
            if cur_o: opts.append(cur_o)
            cur_o = [m.group(1), m.group(2)]
        elif cur_o:
            # 选项续行：短行且像选项
            cur_o[1] += ln
        else:
            stem_lines.append(ln)
    if cur_o: opts.append(cur_o)
    # 清理题干首行题号
    stem = '\n'.join(stem_lines)
    stem = re.sub(r'^\d{1,2}、', '', stem)
    return stem, [(l, x) for l, x in opts]

for n in range(1, 21):
    stem, opts = split_options(questions[n])
    questions[n] = {'stem': stem, 'opts': opts}

for n in (1, 3, 9):
    print(f'--- Q{n} stem: {questions[n]["stem"][:60]}... opts={len(questions[n]["opts"])}')

json.dump({str(k): v for k, v in questions.items()},
          open('hg_q1_20.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved hg_q1_20.json')
