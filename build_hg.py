# 构建化工安全阶段测评（一）s17 数据集
import json, re, hashlib, shutil, os

W = os.path.expanduser('~/workspace/quizapp')
OW = os.path.join(W, 'ocr_work')
IMGDIR = os.path.join(W, 'www', 'img17')
os.makedirs(IMGDIR, exist_ok=True)

def add_img(src, prefix):
    data = open(src, 'rb').read()
    name = prefix + hashlib.md5(data).hexdigest()[:12] + '.png'
    shutil.copy(src, os.path.join(IMGDIR, name))
    return 'img17/' + name

q120 = json.load(open(os.path.join(OW, 'hg_q1_20.json'), encoding='utf-8'))
q2125 = json.load(open(os.path.join(OW, 'hg_q21_essay.json'), encoding='utf-8'))
ans = json.load(open(os.path.join(OW, 'hg_answers.json'), encoding='utf-8'))
essay_ans = json.load(open(os.path.join(OW, 'hg_essay_answers.json'), encoding='utf-8'))
choice_ans = ans['choice']
# Q13 答案手动补
choice_ans['13'] = {'answer': 'C',
    'exp': '低低液位报警应联锁切断出料；高高液位报警设定值不应大于液相体积达到计算容积90%时的高度；压力报警高限设置两级，第一级阈值为正常工作压力的上限、第二级阈值取下列计算值中的较小者：(1)安全阀设定压力值90%；(2)工作压力上限与安全阀设计压力值之和的50%。'}

questions = []
SID = 's17'

def clean(t):
    t = re.sub(r'微信：?87211?7?', '', t)
    t = re.sub(r'需要资料加微?', '', t)
    t = re.sub(r'超押', '', t)
    return t.strip()

# ---------- Q1-20 单选 ----------
for n in range(1, 21):
    d = q120[str(n)]
    a = choice_ans[str(n)]
    images, options = [], []
    if n == 1:
        # 图片选项
        for L in 'ABCD':
            img = add_img(os.path.join(OW, 'hg', f'q1_{L}.png'), 'hg17_q1')
            options.append({'img': img})
        stem = clean(d['stem'])
    elif n == 3:
        images = [add_img(os.path.join(OW, 'hg', 'q3_table.png'), 'hg17_q3')]
        stem = clean(d['stem']) + '（介质参数见下表）'
        options = [{'text': clean(x)} for l, x in d['opts']]
    elif n == 9:
        images = [add_img(os.path.join(OW, 'hg', 'q9_fn.png'), 'hg17_q9')]
        stem = clean(d['stem'])
        options = [{'text': clean(x)} for l, x in d['opts']]
    else:
        stem = clean(d['stem'])
        options = [{'text': clean(x)} for l, x in d['opts']]
    questions.append({
        'set': SID, 'n': n, 'cat': '单项选择题', 'type': 'single',
        'stem': stem, 'answer': list(a['answer']),
        'explanation': clean(a['exp']),
        'images': images, 'exp_images': [], 'options': options,
        'case_bg': '',
    })

# ---------- Q21-25 案例分析选择题 ----------
case21_bg = clean(q2125['case21_bg'])
case21_img = add_img(os.path.join(OW, 'hg', 'case21_table.png'), 'hg17_c21')
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
        'case_images': [case21_img],
    })

# ---------- Q26-40 简答题 ----------
case27_img = add_img(os.path.join(OW, 'hg', 'case27_table.png'), 'hg17_c27')
case_map = {26: '26', 27: '27', 28: '28'}
for ci, cn in enumerate([26, 27, 28]):
    c = q2125['cases'][str(cn)]
    bg = clean(c['bg'])
    # 案例27背景中"现部分参数见下表" -> 配图
    cimgs = [case27_img] if cn == 27 else []
    for si, (sq, subq) in enumerate(c['subs']):
        n = 26 + ci * 5 + si
        key = f'{cn}-{sq}'
        exp = essay_ans[key]
        # 去掉答案开头的重述问题行（与题干重复）
        lines = exp.split('\n')
        if lines and lines[0].strip().rstrip('。') == subq.strip().rstrip('。'):
            exp = '\n'.join(lines[1:]).strip()
        questions.append({
            'set': SID, 'n': n, 'cat': '案例分析简答题', 'type': 'essay',
            'stem': f'{sq}.{clean(subq)}',
            'answer': [],
            'explanation': exp,
            'images': [], 'exp_images': [],
            'options': [],
            'case_bg': bg,
            'case_images': cimgs,
        })

print(f'共 {len(questions)} 题')
print('题型:', [(q['n'], q['type']) for q in questions if q['n'] in (1, 21, 23, 26, 31, 36)])

# 校验：答案一一对应
assert len(questions) == 40
for q in questions:
    if q['type'] in ('single', 'multi'):
        assert q['answer'], f"Q{q['n']} 无答案"
    else:
        assert q['explanation'], f"Q{q['n']} 无参考答案"
        assert q['case_bg'], f"Q{q['n']} 无案例背景"

# 写入 questions_full.json
full = json.load(open(os.path.join(W, 'questions_full.json'), encoding='utf-8'))
full['questions'] = [q for q in full['questions'] if q['set'] != SID] + questions
# 新字段 case_bg/case_images 补到旧题（空值）
for q in full['questions']:
    q.setdefault('case_bg', '')
    q.setdefault('case_images', [])
# sets
full['sets'] = [s for s in full['sets'] if s['id'] != SID]
full['sets'].append({
    'id': SID,
    'title': '化工安全阶段测评（一）',
    'kicker': '李天宇亲编8-1',
    'subject': 'huagong',
    'desc': '2026安全工程师·化工安全·阶段测评（一）：20单选+5案例分析选择+15简答',
})
json.dump(full, open(os.path.join(W, 'questions_full.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('written to questions_full.json')
print('img17 files:', os.listdir(IMGDIR))
