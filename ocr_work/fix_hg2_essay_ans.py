import json, re
out = json.load(open('ocr_hg2.json', encoding='utf-8'))
APAGES = [13,14,15]

def clean_lines(pg):
    res = []
    for e in out[str(pg)]:
        t = e['t'].strip()
        if not t: continue
        if '最顶级VIP' in t or '注安、初会' in t: continue
        if re.match(r'^\d+\s*/\s*14$', t): continue
        if t in ('微信：872117',): continue
        if '加微信' in t and len(t) < 30: continue
        if re.match(r'^8721?17?$', t): continue
        if '扫码进微信' in t or '获取资料' in t: continue
        res.append(t)
    return res

full = []
for pg in APAGES:
    full.extend(clean_lines(pg))

essay = {}
ccase, csub, cbuf = None, None, []
for t in full:
    m = re.match(r'^(\d{2})、(\d)[.、](.+)$', t)
    if m:
        if ccase: essay[(ccase, csub)] = '\n'.join(cbuf)
        ccase, csub, cbuf = int(m.group(1)), int(m.group(2)), [m.group(3)]
        continue
    m2 = re.match(r'^([2-5])[.、](.+)$', t)
    if m2 and ccase and len(t) < 100:
        essay[(ccase, csub)] = '\n'.join(cbuf)
        csub, cbuf = int(m2.group(1)), [m2.group(2)]
        continue
    if ccase:
        cbuf.append(t)
if ccase: essay[(ccase, csub)] = '\n'.join(cbuf)

print('essay answers:', sorted(essay.keys()))
for k in sorted(essay):
    print(f'  {k}: len={len(essay[k])} {essay[k][:45]}...')

old = json.load(open('hg2_answers.json', encoding='utf-8'))
old['essay'] = {f'{k[0]}-{k[1]}': v for k, v in essay.items()}
json.dump(old, open('hg2_answers.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved')
