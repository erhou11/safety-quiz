import json, re
out = json.load(open('ocr_hg2.json', encoding='utf-8'))
QPAGES = [7,8,9,10]

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

# 案例26-28（26的标题OCR为"26例背景"）
cases = {}
cur, buf = None, []
started = False
for pg, t in full:
    if t.startswith('第3题'):
        started = True; continue
    if t == '答案解析':
        break
    if not started: continue
    m = re.match(r'^(\d{2})[、例]案例?背景', t) or re.match(r'^(\d{2})例背景', t)
    if m:
        if cur: cases[cur] = '\n'.join(buf)
        cur, buf = int(m.group(1)), [t]
    elif cur:
        buf.append(t)
if cur: cases[cur] = '\n'.join(buf)
print('cases:', sorted(cases.keys()))

result = {}
for cn in sorted(cases):
    txt = cases[cn]
    mm = re.search(r'依据上述案例背景[，,]?回答下列问题：', txt)
    assert mm, f'case {cn} no split marker'
    bg, qs = txt[:mm.start()], txt[mm.end():]
    subs, sq, sqbuf = [], None, []
    for ln in qs.split('\n'):
        m2 = re.match(r'^(\d)[.、](.*)$', ln)
        if m2 and int(m2.group(1)) <= 5 and len(ln) < 120:
            if sq: subs.append((sq, ' '.join(sqbuf)))
            sq, sqbuf = int(m2.group(1)), [m2.group(2)]
        elif sq:
            sqbuf.append(ln)
    if sq: subs.append((sq, ' '.join(sqbuf)))
    bglines = bg.split('\n')
    bg_clean = '\n'.join(l for l in bglines[1:] if not re.match(rf'^{cn}[.、例]', l))
    result[cn] = {'bg': bg_clean.strip(), 'subs': subs}
    print(f'case {cn}: bg {len(bg_clean)} chars, subs={[s[0] for s in subs]}')

# 案例28补小问2（OCR漏掉，原图确认）
c28 = result[28]
subs = c28['subs']
assert [s[0] for s in subs] == [1,3,4,5]
subs.insert(1, (2, '工艺方案变更前是否应进行可靠性论证，并简述企业可采取的风险识别方法。'))
print('case28 subs fixed:', [s[0] for s in subs])

# 合并到已有文件
old = json.load(open('hg2_q21_essay.json', encoding='utf-8'))
old['cases'] = {str(k): v for k, v in result.items()}
json.dump(old, open('hg2_q21_essay.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved')
