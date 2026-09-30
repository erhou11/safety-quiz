"""把 ~/workspace/quiz/questions.json 里的 base64 图片抽成独立文件，生成服务端用的 questions_full.json。"""
import json, base64, hashlib, os

SRC = '/home/hatch/workspace/quiz/questions.json'
OUTDIR = '/home/hatch/workspace/quizapp'
imgdir = os.path.join(OUTDIR, 'www', 'img')
os.makedirs(imgdir, exist_ok=True)

qs = json.load(open(SRC, encoding='utf-8'))
seen = set()

def save_img(data_uri):
    header, b64 = data_uri.split(',', 1)
    raw = base64.b64decode(b64)
    h = hashlib.sha256(raw).hexdigest()[:12]
    ext = 'png'
    if 'jpeg' in header or 'jpg' in header:
        ext = 'jpg'
    elif 'gif' in header:
        ext = 'gif'
    name = f'{h}.{ext}'
    if name not in seen:
        with open(os.path.join(imgdir, name), 'wb') as f:
            f.write(raw)
        seen.add(name)
    return f'img/{name}'

full = []
for q in qs:
    nq = dict(q)
    nq['images'] = [save_img(u) for u in q.get('images', [])]
    nq['exp_images'] = [save_img(u) for u in q.get('exp_images', [])]
    opts = []
    for o in q['options']:
        if 'img' in o:
            opts.append({'img': save_img(o['img'])})
        else:
            opts.append({'text': o['text']})
    nq['options'] = opts
    full.append(nq)

with open(os.path.join(OUTDIR, 'questions_full.json'), 'w', encoding='utf-8') as f:
    json.dump(full, f, ensure_ascii=False)

total_bytes = sum(os.path.getsize(os.path.join(imgdir, n)) for n in seen)
print(f'questions: {len(full)}, unique images: {len(seen)}, img bytes: {total_bytes}')
