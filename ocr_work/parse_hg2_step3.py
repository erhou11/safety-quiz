# Step3: 解析答案（PDF pp 11-18）
import json, re

out = json.load(open('ocr_hg2.json', encoding='utf-8'))
APAGES = [10,11,12,13,14,15]

def clean_lines(pg):
    res = []
    for e in out[str(pg)]:
        t = e['t'].strip()
        if not t: continue
        if '最顶级VIP' in t or '注安、初会' in t: continue
        if re.match(r'^\d+\s*/\s*14$', t): continue
        if t in ('微信：872117', '233网校', 'www.233.com'): continue
        if t.startswith('全真机考'): continue
        if t.startswith('考证就上'): continue
        if t in ('免费题库，复习资料包，', '扫码下载即可获得'): continue
        if '加微信' in t and len(t) < 30: continue
        if re.match(r'^8721?17?$', t): continue
        if t in ('超押',): continue
        res.append(t)
    return res

full = []
for pg in APAGES:
    full.extend([(pg, t) for t in clean_lines(pg)])

# ---------- Q1-25: "N、答案：X" ----------
answers = {}
cur, buf = None, []
started = False
for pg, t in full:
    if t == '答案解析':
        started = True; continue
    if not started: continue
    m = re.match(r'^(\d{1,2})、答案：(.+)$', t)
    if m:
        if cur: answers[cur] = '\n'.join(buf)
        cur, buf = int(m.group(1)), ['ANS:' + m.group(2).strip()]
    elif cur:
        # 简答题答案开始标记: "26、1.参照..."
        m2 = re.match(r'^(\d{2})、(\d)\.(.+)$', t)
        if m2:
            answers[cur] = '\n'.join(buf)
            cur = None
            # 交给简答题解析
            buf = [(int(m2.group(1)), int(m2.group(2)), m2.group(3))]
            break
        buf.append(t)
if cur: answers[cur] = '\n'.join(buf)

print('choice answers:', sorted(answers.keys()))

# 解析每题: ANS行 + 解析：
for n in sorted(answers):
    txt = answers[n]
    lines = txt.split('\n')
    ans_line = lines[0]
    ans = re.sub(r'^ANS:', '', ans_line).replace('，', ',').replace(' ', '')
    ans = ''.join(c for c in ans if c in 'ABCDE,')
    exp = '\n'.join(lines[1:])
    exp = re.sub(r'^解析：', '', exp)
    # Q21-25 的解析里有【答案】X【解析】结构
    exp = re.sub(r'【答案】[A-E,]+', '', exp)
    exp = re.sub(r'^【解析】', '', exp)
    answers[n] = {'answer': ans, 'exp': exp.strip()}
    print(f"Q{n}: ans={ans} exp_len={len(exp)}")

# ---------- 简答题答案：从 buf 继续 ----------
essay = {}  # (case, sub) -> text
ccase, csub, cbuf = buf[0][0], buf[0][1], [buf[0][2]]
for pg, t in full:
    pass  # full已消费，重新遍历

# 重新遍历找简答题答案
essay_raw = []
in_essay = False
for pg, t in full:
    m2 = re.match(r'^(\d{2})、(\d)\.(.+)$', t)
    if m2:
        in_essay = True
        essay_raw.append((int(m2.group(1)), int(m2.group(2)), m2.group(3)))
        continue
    if in_essay:
        essay_raw.append(t)

# 按 (case,sub) 切分
cur_key, cbuf = None, []
for item in essay_raw:
    if isinstance(item, tuple):
        if cur_key: essay[cur_key] = '\n'.join(cbuf)
        cur_key = (item[0], item[1]); cbuf = [item[2]]
    else:
        cbuf.append(item)
if cur_key: essay[cur_key] = '\n'.join(cbuf)

print('essay answers:', sorted(essay.keys()))
for k in sorted(essay):
    print(f'  {k}: {essay[k][:50]}... len={len(essay[k])}')

json.dump({'choice': {str(k): v for k, v in answers.items()},
           'essay': {f'{k[0]}-{k[1]}': v for k, v in essay.items()}},
          open('hg2_answers.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('saved')
