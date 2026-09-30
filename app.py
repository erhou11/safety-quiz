"""安全生产技术刷题 App 后端：Flask + SQLite，题目作答/进度/错题全部服务端持久化。"""
import json, os, sqlite3, secrets, random
from flask import Flask, request, jsonify, session, g

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, 'quiz.db')

with open(os.path.join(BASE, 'questions_full.json'), encoding='utf-8') as f:
    QUESTIONS = {q['n']: q for q in json.load(f)}
ORDER_SEQ = sorted(QUESTIONS.keys())

app = Flask(__name__)
sk_file = os.path.join(BASE, 'secret.key')
if not os.path.exists(sk_file):
    with open(sk_file, 'wb') as f:
        f.write(secrets.token_bytes(32))
with open(sk_file, 'rb') as f:
    app.secret_key = f.read()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    d = g.pop('db', None)
    if d is not None:
        d.close()


def init_db():
    d = db()
    d.executescript('''
    CREATE TABLE IF NOT EXISTS answers(
        client TEXT, n INTEGER, selected TEXT, correct INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client, n));
    CREATE TABLE IF NOT EXISTS wrong(
        client TEXT, n INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client, n));
    CREATE TABLE IF NOT EXISTS progress(
        client TEXT, mode TEXT, pos INTEGER, PRIMARY KEY(client, mode));
    CREATE TABLE IF NOT EXISTS rand_order(
        client TEXT, order_json TEXT, PRIMARY KEY(client));
    ''')
    d.commit()


def cid():
    if 'cid' not in session:
        session['cid'] = secrets.token_hex(16)
    return session['cid']


def public_q(n):
    q = QUESTIONS[n]
    return {'n': q['n'], 'cat': q['cat'], 'type': q['type'],
            'stem': q['stem'], 'options': q['options'], 'images': q['images']}


def get_order(client, mode):
    d = db()
    if mode == 'rand':
        row = d.execute('SELECT order_json FROM rand_order WHERE client=?', (client,)).fetchone()
        if row:
            return json.loads(row['order_json'])
        order = ORDER_SEQ[:]
        random.shuffle(order)
        d.execute('INSERT OR REPLACE INTO rand_order VALUES (?, ?)', (client, json.dumps(order)))
        d.commit()
        return order
    if mode == 'wrong':
        rows = d.execute('SELECT n FROM wrong WHERE client=? ORDER BY ts', (client,)).fetchall()
        return [r['n'] for r in rows]
    return ORDER_SEQ


@app.route('/api/meta')
def meta():
    return jsonify({
        'total': len(QUESTIONS),
        'single': sum(1 for q in QUESTIONS.values() if q['type'] == 'single'),
        'multi': sum(1 for q in QUESTIONS.values() if q['type'] == 'multi'),
    })


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'questions': len(QUESTIONS)})


@app.route('/api/state')
def state():
    c = cid()
    d = db()
    prog = {r['mode']: r['pos'] for r in d.execute(
        'SELECT mode, pos FROM progress WHERE client=?', (c,))}
    wrong_n = d.execute('SELECT COUNT(*) AS c FROM wrong WHERE client=?', (c,)).fetchone()['c']
    answered = d.execute('SELECT COUNT(*) AS c FROM answers WHERE client=?', (c,)).fetchone()['c']
    return jsonify({'seq_pos': prog.get('seq', 0), 'rand_pos': prog.get('rand', 0),
                    'wrong_count': wrong_n, 'answered': answered})


@app.route('/api/questions')
def questions():
    c = cid()
    mode = request.args.get('mode', 'seq')
    if mode not in ('seq', 'rand', 'wrong'):
        mode = 'seq'
    return jsonify([public_q(n) for n in get_order(c, mode)])


@app.route('/api/round')
def round_state():
    """本客户端已作答过的题目（含答案解析，供回看已答题目用）。"""
    c = cid()
    d = db()
    out = {}
    for r in d.execute('SELECT n, selected, correct FROM answers WHERE client=?', (c,)):
        q = QUESTIONS[r['n']]
        out[r['n']] = {'selected': json.loads(r['selected']), 'correct': bool(r['correct']),
                       'answer': q['answer'], 'explanation': q['explanation'],
                       'exp_images': q['exp_images']}
    return jsonify(out)


@app.route('/api/visit', methods=['POST'])
def visit():
    c = cid()
    d = db()
    body = request.get_json(force=True)
    mode = body.get('mode', 'seq')
    pos = int(body.get('pos', 0))
    d.execute('INSERT OR REPLACE INTO progress VALUES (?, ?, ?)', (c, mode, pos))
    d.commit()
    return jsonify({'ok': True})


@app.route('/api/answer', methods=['POST'])
def answer():
    c = cid()
    d = db()
    body = request.get_json(force=True)
    n = int(body['n'])
    selected = sorted(s.upper() for s in body.get('selected', []))
    q = QUESTIONS[n]
    correct = selected == sorted(q['answer'])
    d.execute('INSERT OR REPLACE INTO answers VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
              (c, n, json.dumps(selected), 1 if correct else 0))
    if correct:
        d.execute('DELETE FROM wrong WHERE client=? AND n=?', (c, n))
    else:
        d.execute('INSERT OR IGNORE INTO wrong VALUES (?, ?, CURRENT_TIMESTAMP)', (c, n))
    mode = body.get('mode', 'seq')
    order = get_order(c, mode)
    if n in order:
        pos = min(order.index(n) + 1, len(order))
        d.execute('INSERT OR REPLACE INTO progress VALUES (?, ?, ?)', (c, mode, pos))
    d.commit()
    return jsonify({'correct': correct, 'answer': q['answer'],
                    'explanation': q['explanation'], 'exp_images': q['exp_images']})


@app.route('/api/reset', methods=['POST'])
def reset():
    c = cid()
    d = db()
    body = request.get_json(force=True) or {}
    mode = body.get('mode', 'seq')
    d.execute('DELETE FROM progress WHERE client=? AND mode=?', (c, mode))
    if mode == 'rand':
        order = ORDER_SEQ[:]
        random.shuffle(order)
        d.execute('INSERT OR REPLACE INTO rand_order VALUES (?, ?)', (c, json.dumps(order)))
    d.commit()
    return jsonify({'ok': True})


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8001)
