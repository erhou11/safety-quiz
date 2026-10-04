# Step1: 解析8-2题目 Q1-20（PDF pp 1,2,4,5）
import json, re
out = json.load(open('ocr_hg2.json', encoding='utf-8'))
QPAGES = [1,2,4,5]

def clean_lines(pg):
    res = []
    for e in out[str(pg)]:
        t = e['t'].strip()
        if not t: continue
        if '最顶级VIP' in t or '注安、初会' in t: continue
        if re.match(r'^\d+\s*/\s*14$', t): continue
        if t in ('微信：872117', '233网校', 'www.233.com'): continue
        if t.startswith('全真机考'): continue
        if '加微信' in t and len(t) < 30: continue
        if re.match(r'^8721?17?$', t): continue
        res.append(t)
    return res

full = []
for pg in QPAGES:
    full.extend([(pg, t) for t in clean_lines(pg)])

questions = {}
qpat = re.compile(r'^(\d{1,2})、')
cur, buf = None, []
def flush():
    global cur, buf
    if cur and buf: questions[cur] = '\n'.join(buf)
    cur, buf = None, []

for pg, t in full:
    m = qpat.match(t)
    if m and int(m.group(1)) <= 20:
        flush(); cur = int(m.group(1)); buf = [t]
    elif cur:
        if t.startswith('第2题') or t.startswith('第3题'): flush(); break
        buf.append(t)
flush()
print('Q1-20 parsed:', sorted(questions.keys()))

def split_options(qtext):
    lines = qtext.split('\n')
    stem_lines, opts, cur_o = [], [], None
    for ln in lines:
        m = re.match(r'^([A-E])\s*[.．、]\s*(.*)$', ln)
        if m and not (len(ln) < 6 and not m.group(2)):
            if cur_o: opts.append(cur_o)
            cur_o = [m.group(1), m.group(2)]
        elif cur_o:
            cur_o[1] += ln
        else:
            stem_lines.append(ln)
    if cur_o: opts.append(cur_o)
    stem = '\n'.join(stem_lines)
    stem = re.sub(r'^\d{1,2}、', '', stem)
    return stem, [(l, x) for l, x in opts]

for n in range(1, 21):
    if n not in questions:
        print('MISSING Q', n); continue
    stem, opts = split_options(questions[n])
    questions[n] = {'stem': stem, 'opts': opts}
    if len(opts) != 4:
        print(f'Q{n}: 选项数={len(opts)} 需核查')

for n in (1, 9, 15):
    print(f'--- Q{n}: {questions[n]["stem"][:50]}... opts={len(questions[n]["opts"])}')

json.dump({str(k): v for k, v in questions.items()},
          open('hg2_q1_20.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved hg2_q1_20.json')
