# Step3b: 解析简答题答案（修复版）
import json, re

out = json.load(open('ocr_hg.json', encoding='utf-8'))
APAGES = [11,12,13,14,15,16,17,18]

def clean_lines(pg):
    res = []
    for e in out[str(pg)]:
        t = e['t'].strip()
        if not t: continue
        if '最顶级VIP' in t or '注安、初会' in t: continue
        if re.match(r'^\d+\s*/\s*17$', t): continue
        if t in ('微信：872117', '233网校', 'www.233.com'): continue
        if t.startswith('全真机考'): continue
        if t.startswith('考证就上'): continue
        if t in ('免费题库，复习资料包，', '扫码下载即可获得'): continue
        if '加微信' in t and len(t) < 30: continue
        if re.match(r'^8721?17?$', t): continue
        if t == '超押': continue
        res.append(t)
    return res

full = []
for pg in APAGES:
    full.extend([(pg, t) for t in clean_lines(pg)])

# 找到简答题答案起始位置（第一个 "26、1."）
start_idx = None
for i, (pg, t) in enumerate(full):
    if re.match(r'^26、1\.', t):
        start_idx = i; break
assert start_idx is not None

essay = {}
ccase, csub, cbuf = None, None, []
for pg, t in full[start_idx:]:
    m = re.match(r'^(\d{2})、(\d)\.(.+)$', t)  # "26、1.xxx"
    m2 = re.match(r'^([1-5])\.(.+)$', t) if not m else None  # "2.xxx"
    if m:
        if ccase: essay[(ccase, csub)] = '\n'.join(cbuf)
        ccase, csub, cbuf = int(m.group(1)), int(m.group(2)), [m.group(3)]
    elif m2 and ccase and len(t) < 150:
        if ccase: essay[(ccase, csub)] = '\n'.join(cbuf)
        csub, cbuf = int(m2.group(1)), [m2.group(2)]
    elif ccase:
        cbuf.append(t)
if ccase: essay[(ccase, csub)] = '\n'.join(cbuf)

print('essay answers:', sorted(essay.keys()))
assert sorted(essay.keys()) == [(26,i) for i in range(1,6)] + [(27,i) for i in range(1,6)] + [(28,i) for i in range(1,6)], 'count mismatch!'

# 清理水印残留
def clean_exp(t):
    t = re.sub(r'超押', '', t)
    t = re.sub(r'微信：?87211?7?', '', t)
    t = re.sub(r'需要资料加', '', t)
    t = re.sub(r'资料加', '', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()

for k in essay:
    essay[k] = clean_exp(essay[k])
    print(f'  {k}: len={len(essay[k])} head={essay[k][:40]}...')

json.dump({f'{k[0]}-{k[1]}': v for k, v in essay.items()},
          open('hg_essay_answers.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved hg_essay_answers.json')
