# 构建化工李天宇8-4 s20 数据集
import json, re, os

W = os.path.expanduser('~/workspace/quizapp')
OW = os.path.join(W, 'ocr_work')

q120 = json.load(open(os.path.join(OW, 'hg4_q1_20.json'), encoding='utf-8'))
q2125 = json.load(open(os.path.join(OW, 'hg4_q21_essay.json'), encoding='utf-8'))
ans = json.load(open(os.path.join(OW, 'hg4_answers.json'), encoding='utf-8'))
choice_ans = ans['choice']
essay_ans = ans['essay']

questions = []
SID = 's20'

def clean(t):
    t = re.sub(r'微信：?87211?7?', '', t)
    t = re.sub(r'需要资料加微?', '', t)
    t = re.sub(r'超押加微?', '', t)
    t = re.sub(r'超押', '', t)
    return t.strip()

# ---------- Q1-20 ----------
for n in range(1, 21):
    d = q120[str(n)]
    a = choice_ans[str(n)]
    stem = clean(d['stem'])
    options = [{'text': clean(x)} for l, x in d['opts']]
    questions.append({
        'set': SID, 'n': n, 'cat': '单项选择题', 'type': 'single',
        'stem': stem, 'answer': list(a['answer']),
        'explanation': clean(a['exp']),
        'images': [], 'exp_images': [], 'options': options,
        'case_bg': '',
    })

# ---------- Q21-25 ----------
case21_bg = clean(q2125['case21_bg'])
for n in range(21, 26):
    d = q2125['q21_25'][str(n)]
    a = choice_ans[str(n)]
    tp = 'single' if d['type'] == '单项选择题' else 'multi'
    cat = '案例分析' + d['type']
    ans_letters = [c for c in a['answer'].split(',') if c]
    questions.append({
        'set': SID, 'n': n, 'cat': cat, 'type': tp,
        'stem': clean(d['stem']),
        'answer': ans_letters,
        'explanation': clean(a['exp']),
        'images': [], 'exp_images': [],
        'options': [{'text': clean(x)} for l, x in d['opts']],
        'case_bg': case21_bg,
        'case_images': [],
    })

# ---------- Q26-40 简答题 ----------
for ci, cn in enumerate([26, 27, 28]):
    c = q2125['cases'][str(cn)]
    bg = clean(c['bg'])
    for si, (sq, subq) in enumerate(c['subs']):
        n = 26 + ci * 5 + si
        key = f'{cn}-{sq}'
        exp = essay_ans[key]
        lines = exp.split('\n')
        if lines and lines[0].strip().rstrip('。') == subq.strip().rstrip('。'):
            exp = '\n'.join(lines[1:]).strip()
        questions.append({
            'set': SID, 'n': n, 'cat': '案例分析简答题', 'type': 'essay',
            'stem': f'{sq}.{clean(subq)}',
            'answer': [],
            'explanation': clean(exp),
            'images': [], 'exp_images': [],
            'options': [],
            'case_bg': bg,
            'case_images': [],
        })

print(f'共 {len(questions)} 题')
assert len(questions) == 40
for q in questions:
    if q['type'] in ('single', 'multi'):
        assert q['answer'], f"Q{q['n']} 无答案"
        valid = [chr(ord('A')+i) for i in range(len(q['options']))]
        for L in q['answer']:
            assert L in valid, f"Q{q['n']} 答案{L}超出选项{valid}"
    else:
        assert q['explanation'], f"Q{q['n']} 无参考答案"
        assert q['case_bg'], f"Q{q['n']} 无案例背景"

full = json.load(open(os.path.join(W, 'questions_full.json'), encoding='utf-8'))
full['questions'] = [q for q in full['questions'] if q['set'] != SID] + questions
for q in full['questions']:
    q.setdefault('case_bg', '')
    q.setdefault('case_images', [])
full['sets'] = [s for s in full['sets'] if s['id'] != SID]
full['sets'].append({
    'id': SID,
    'title': '化工李天宇8-4',
    'kicker': '李天宇亲编8-4',
    'subject': 'huagong',
    'desc': '2026安全工程师·化工安全·点题锁分班2：20单选+5案例分析选择+15简答',
})
json.dump(full, open(os.path.join(W, 'questions_full.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('written to questions_full.json')
print('总题数:', len(full['questions']), '套数:', len(full['sets']))
