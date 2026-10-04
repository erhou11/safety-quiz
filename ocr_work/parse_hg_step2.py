# Step2: 解析 Q21-25 案例分析选择题 + 26-28 案例简答题
import json, re

out = json.load(open('ocr_hg.json', encoding='utf-8'))
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
        if '加微信' in t and len(t) < 30: continue
        if re.match(r'^8721?17?$', t): continue
        res.append(t)
    return res

full = []
for pg in QPAGES:
    full.extend([(pg, t) for t in clean_lines(pg)])

# ---------- Q21-25 ----------
q21_25 = {}
cur, buf, ctype = None, [], None
started = False
for pg, t in full:
    if t.startswith('第2题'):
        started = True; continue
    if t.startswith('第3题'):
        break
    if not started: continue
    m = re.match(r'^(?:(\d{1,2})、)?【(单项选择题|多项选择题)】(\d{1,2})\.', t)
    if m:
        if cur: q21_25[cur] = {'type': ctype, 'text': '\n'.join(buf)}
        cur = int(m.group(1) or m.group(3)); ctype = m.group(2); buf = [t]
    elif cur:
        buf.append(t)
if cur: q21_25[cur] = {'type': ctype, 'text': '\n'.join(buf)}
print('Q21-25:', sorted(q21_25.keys()))

# 21的案例背景
case21_bg = []
in_bg = False
for pg, t in full:
    if re.match(r'^21、案例背景', t):
        in_bg = True; case21_bg.append(t); continue
    if in_bg and '【单项选择题】21.' in t:
        break
    if in_bg:
        case21_bg.append(t)
print('case21 bg lines:', len(case21_bg))

def split_opts(qtext):
    lines = qtext.split('\n')
    stem_lines, opts, cur_o = [], [], None
    for ln in lines:
        m = re.match(r'^([A-E])\s*[.．、]\s*(.*)$', ln)
        if m:
            if cur_o: opts.append(cur_o)
            cur_o = [m.group(1), m.group(2)]
        elif cur_o:
            cur_o[1] += ln
        else:
            stem_lines.append(ln)
    if cur_o: opts.append(cur_o)
    stem = '\n'.join(stem_lines)
    stem = re.sub(r'^(?:\d{1,2}、)?【(?:单项|多项)选择题】\d{1,2}\.', '', stem)
    return stem, [(l, x) for l, x in opts]

for n in range(21, 26):
    stem, opts = split_opts(q21_25[n]['text'])
    q21_25[n]['stem'] = stem
    q21_25[n]['opts'] = opts
    print(f"Q{n} [{q21_25[n]['type']}] opts={len(opts)} stem={stem[:50]}...")

# ---------- 26-28 案例简答 ----------
cases = {}
cur, buf = None, []
started = False
for pg, t in full:
    if t.startswith('第3题'):
        started = True; continue
    if t == '答案解析':
        break
    if not started: continue
    m = re.match(r'^(\d{2})、案例背景', t)
    if m:
        if cur: cases[cur] = '\n'.join(buf)
        cur, buf = int(m.group(1)), [t]
    elif cur:
        buf.append(t)
if cur: cases[cur] = '\n'.join(buf)
print('cases:', sorted(cases.keys()))

for cn in sorted(cases):
    txt = cases[cn]
    mm = re.search(r'依据上述案例背景[，,]?回答下列问题：', txt)
    assert mm, f'case {cn} no split marker'
    bg, qs = txt[:mm.start()], txt[mm.end():]
    subs, sq, sqbuf = [], None, []
    for ln in qs.split('\n'):
        m2 = re.match(r'^(\d)\.(.*)$', ln)
        if m2 and int(m2.group(1)) <= 5 and len(ln) < 120:
            if sq: subs.append((sq, ' '.join(sqbuf)))
            sq, sqbuf = int(m2.group(1)), [m2.group(2)]
        elif sq:
            sqbuf.append(ln)
    if sq: subs.append((sq, ' '.join(sqbuf)))
    bglines = bg.split('\n')
    bg_clean = '\n'.join(l for l in bglines[1:] if not re.match(rf'^{cn}\.', l))
    cases[cn] = {'bg': bg_clean.strip(), 'subs': subs}
    print(f'case {cn}: bg {len(bg_clean)} chars, subs={[s[0] for s in subs]}')
    for s in subs:
        print(f'   {s[0]}. {s[1][:45]}...')

json.dump({'q21_25': {str(k): v for k, v in q21_25.items()},
           'case21_bg': '\n'.join(case21_bg),
           'cases': {str(k): v for k, v in cases.items()}},
          open('hg_q21_essay.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved')
