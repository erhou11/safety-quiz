"""安全生产技术刷题 App 后端：Flask + SQLite，题目作答/进度/错题全部服务端持久化。
支持多套题：每套题独立的进度、随机顺序与错题本。"""
import json, os, re, sqlite3, secrets, random
from datetime import timedelta
from flask import Flask, request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, 'quiz.db')

with open(os.path.join(BASE, 'questions_full.json'), encoding='utf-8') as f:
    _data = json.load(f)
SETS = _data['sets']
SUBJECTS = _data.get('subjects', [])
QUESTIONS = {}
for q in _data['questions']:
    QUESTIONS['%s:%d' % (q['set'], q['n'])] = q
SET_IDS = [s['id'] for s in SETS]
ORDERS = {sid: sorted(int(k.split(':')[1]) for k in QUESTIONS if k.startswith(sid + ':'))
          for sid in SET_IDS}

app = Flask(__name__)
sk_file = os.path.join(BASE, 'secret.key')
if not os.path.exists(sk_file):
    with open(sk_file, 'wb') as f:
        f.write(secrets.token_bytes(32))
with open(sk_file, 'rb') as f:
    app.secret_key = f.read()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)


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


def _has_col(d, table, col):
    return any(r['name'] == col for r in d.execute('PRAGMA table_info(%s)' % table))


def _rebuild_with_set(d, tbl, cols, pk):
    """旧表重建为带 set_id 的新结构，旧数据归为 s1。"""
    col_defs = {'client': 'client TEXT', 'n': 'n INTEGER', 'selected': 'selected TEXT',
                'correct': 'correct INTEGER', 'mode': 'mode TEXT', 'pos': 'pos INTEGER',
                'order_json': 'order_json TEXT', 'ts': 'ts DATETIME DEFAULT CURRENT_TIMESTAMP'}
    new_cols = ['client', 'set_id TEXT DEFAULT \'s1\'']
    new_cols += [col_defs[c] for c in cols]
    d.execute('CREATE TABLE %s_new(%s, PRIMARY KEY(%s))' % (tbl, ', '.join(new_cols), pk))
    sel = ', '.join(["'s1'"] + cols)
    d.execute('INSERT INTO %s_new(client, set_id, %s) SELECT client, %s FROM %s'
              % (tbl, ', '.join(cols), sel, tbl))
    d.execute('DROP TABLE %s' % tbl)
    d.execute('ALTER TABLE %s_new RENAME TO %s' % (tbl, tbl))


def init_db():
    d = db()
    d.execute('PRAGMA journal_mode=WAL')
    d.executescript('''
    CREATE TABLE IF NOT EXISTS answers(
        client TEXT, set_id TEXT DEFAULT 's1', n INTEGER, selected TEXT, correct INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client, set_id, n));
    CREATE TABLE IF NOT EXISTS wrong(
        client TEXT, set_id TEXT DEFAULT 's1', n INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client, set_id, n));
    CREATE TABLE IF NOT EXISTS favorites(
        client TEXT, set_id TEXT DEFAULT 's1', n INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client, set_id, n));
    CREATE TABLE IF NOT EXISTS progress(
        client TEXT, set_id TEXT DEFAULT 's1', mode TEXT, pos INTEGER,
        PRIMARY KEY(client, set_id, mode));
    CREATE TABLE IF NOT EXISTS rand_order(
        client TEXT, set_id TEXT DEFAULT 's1', order_json TEXT,
        PRIMARY KEY(client, set_id));
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        pw_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    ''')
    # 迁移旧库：没有 set_id 列说明是旧表，重建（旧数据归为 s1）
    if not _has_col(d, 'answers', 'set_id'):
        _rebuild_with_set(d, 'answers', ['n', 'selected', 'correct', 'ts'], 'client, set_id, n')
        _rebuild_with_set(d, 'wrong', ['n', 'ts'], 'client, set_id, n')
        _rebuild_with_set(d, 'progress', ['mode', 'pos'], 'client, set_id, mode')
        _rebuild_with_set(d, 'rand_order', ['order_json'], 'client, set_id')
    d.commit()


def cid():
    uid = session.get('uid')
    if uid:
        return 'u%d' % uid
    if 'cid' not in session:
        session['cid'] = secrets.token_hex(16)
    return session['cid']


def migrate_anon_to_user(anon_cid, uid):
    """登录/注册时把当前匿名进度合并到账号下（账号已有数据优先保留）。"""
    if not anon_cid:
        return
    new_cid = 'u%d' % uid
    if anon_cid == new_cid:
        return
    d = db()
    d.execute('INSERT OR IGNORE INTO answers(client,set_id,n,selected,correct,ts)'
              ' SELECT ?,set_id,n,selected,correct,ts FROM answers WHERE client=?',
              (new_cid, anon_cid))
    d.execute('INSERT OR IGNORE INTO wrong(client,set_id,n,ts)'
              ' SELECT ?,set_id,n,ts FROM wrong WHERE client=?', (new_cid, anon_cid))
    d.execute('INSERT OR IGNORE INTO favorites(client,set_id,n,ts)'
              ' SELECT ?,set_id,n,ts FROM favorites WHERE client=?', (new_cid, anon_cid))
    d.execute('INSERT OR IGNORE INTO progress(client,set_id,mode,pos)'
              ' SELECT ?,set_id,mode,pos FROM progress WHERE client=?', (new_cid, anon_cid))
    d.execute('INSERT OR IGNORE INTO rand_order(client,set_id,order_json)'
              ' SELECT ?,set_id,order_json FROM rand_order WHERE client=?', (new_cid, anon_cid))
    d.commit()


def _do_login(uid, email):
    migrate_anon_to_user(session.get('cid'), uid)
    session['uid'] = uid
    session['email'] = email
    session.permanent = True


def req_set():
    s = (request.args.get('set') or
         (request.get_json(silent=True) or {}).get('set') or 's1')
    return s if s in SET_IDS else 's1'


def public_q(sid, n):
    q = QUESTIONS['%s:%d' % (sid, n)]
    return {'n': q['n'], 'cat': q['cat'], 'type': q['type'],
            'stem': q['stem'], 'options': q['options'], 'images': q['images'],
            'case_bg': q.get('case_bg', ''), 'case_images': q.get('case_images', [])}


def full_q(sid, n):
    return QUESTIONS['%s:%d' % (sid, n)]


def get_order(client, sid, mode):
    d = db()
    if mode == 'rand':
        row = d.execute('SELECT order_json FROM rand_order WHERE client=? AND set_id=?',
                        (client, sid)).fetchone()
        if row:
            return json.loads(row['order_json'])
        order = ORDERS[sid][:]
        random.shuffle(order)
        d.execute('INSERT OR REPLACE INTO rand_order(client, set_id, order_json) VALUES (?, ?, ?)',
                  (client, sid, json.dumps(order)))
        d.commit()
        return order
    if mode == 'wrong':
        rows = d.execute('SELECT n FROM wrong WHERE client=? AND set_id=? ORDER BY ts',
                         (client, sid)).fetchall()
        return [r['n'] for r in rows]
    if mode == 'fav':
        rows = d.execute('SELECT n FROM favorites WHERE client=? AND set_id=? ORDER BY ts',
                         (client, sid)).fetchall()
        return [r['n'] for r in rows]
    return ORDERS[sid]


@app.route('/api/meta')
def meta():
    c = cid()
    d = db()
    ans_counts = {r['set_id']: r['c'] for r in d.execute(
        'SELECT set_id, COUNT(*) AS c FROM answers WHERE client=? GROUP BY set_id', (c,))}
    out = []
    for s in SETS:
        qs = [q for q in QUESTIONS.values() if q['set'] == s['id']]
        out.append({'id': s['id'], 'title': s['title'], 'kicker': s['kicker'],
                    'subject': s.get('subject', 'jishu'), 'desc': s.get('desc', ''),
                    'total': len(qs),
                    'single': sum(1 for q in qs if q['type'] == 'single'),
                    'multi': sum(1 for q in qs if q['type'] == 'multi'),
                    'essay': sum(1 for q in qs if q['type'] == 'essay'),
                    'answered': ans_counts.get(s['id'], 0)})
    return jsonify({'subjects': SUBJECTS, 'sets': out})


@app.post('/api/register')
def register():
    body = request.get_json(force=True) or {}
    email = (body.get('email') or '').strip().lower()
    password = body.get('password') or ''
    if not EMAIL_RE.match(email):
        return jsonify({'ok': False, 'msg': '邮箱格式不正确'}), 400
    if len(password) < 6:
        return jsonify({'ok': False, 'msg': '密码至少 6 位'}), 400
    d = db()
    try:
        cur = d.execute('INSERT INTO users(email, pw_hash) VALUES (?, ?)',
                        (email, generate_password_hash(password)))
        d.commit()
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'msg': '该邮箱已注册，请直接登录'}), 409
    _do_login(cur.lastrowid, email)
    return jsonify({'ok': True, 'email': email})


@app.post('/api/login')
def login():
    body = request.get_json(force=True) or {}
    email = (body.get('email') or '').strip().lower()
    password = body.get('password') or ''
    row = db().execute('SELECT id, pw_hash FROM users WHERE email=?', (email,)).fetchone()
    if not row or not check_password_hash(row['pw_hash'], password):
        return jsonify({'ok': False, 'msg': '邮箱或密码不正确'}), 401
    _do_login(row['id'], email)
    return jsonify({'ok': True, 'email': email})


@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.get('/api/me')
def me():
    if session.get('uid'):
        return jsonify({'logged_in': True, 'email': session.get('email')})
    return jsonify({'logged_in': False})


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'questions': len(QUESTIONS),
                    'sets': {sid: len(ORDERS[sid]) for sid in SET_IDS}})


@app.route('/api/state')
def state():
    c = cid()
    sid = req_set()
    d = db()
    prog = {r['mode']: r['pos'] for r in d.execute(
        'SELECT mode, pos FROM progress WHERE client=? AND set_id=?', (c, sid))}
    wrong_n = d.execute('SELECT COUNT(*) AS c FROM wrong WHERE client=? AND set_id=?',
                        (c, sid)).fetchone()['c']
    fav_n = d.execute('SELECT COUNT(*) AS c FROM favorites WHERE client=? AND set_id=?',
                      (c, sid)).fetchone()['c']
    answered = d.execute('SELECT COUNT(*) AS c FROM answers WHERE client=? AND set_id=?',
                         (c, sid)).fetchone()['c']
    return jsonify({'seq_pos': prog.get('seq', 0), 'rand_pos': prog.get('rand', 0),
                    'wrong_count': wrong_n, 'fav_count': fav_n, 'answered': answered})


@app.route('/api/questions')
def questions():
    c = cid()
    sid = req_set()
    mode = request.args.get('mode', 'seq')
    if mode not in ('seq', 'rand', 'wrong', 'fav'):
        mode = 'seq'
    return jsonify([public_q(sid, n) for n in get_order(c, sid, mode)])


@app.route('/api/round')
def round_state():
    """本客户端已作答过的题目（含答案解析，供回看已答题目用）。"""
    c = cid()
    sid = req_set()
    d = db()
    out = {}
    for r in d.execute('SELECT n, selected, correct FROM answers WHERE client=? AND set_id=?',
                       (c, sid)):
        q = full_q(sid, r['n'])
        out[r['n']] = {'selected': json.loads(r['selected']), 'correct': bool(r['correct']),
                       'answer': q['answer'], 'explanation': q['explanation'],
                       'exp_images': q['exp_images']}
    return jsonify(out)


@app.route('/api/visit', methods=['POST'])
def visit():
    c = cid()
    sid = req_set()
    d = db()
    body = request.get_json(force=True)
    mode = body.get('mode', 'seq')
    pos = int(body.get('pos', 0))
    d.execute('INSERT OR REPLACE INTO progress(client, set_id, mode, pos) VALUES (?, ?, ?, ?)',
              (c, sid, mode, pos))
    d.commit()
    return jsonify({'ok': True})


@app.route('/api/answer', methods=['POST'])
def answer():
    c = cid()
    sid = req_set()
    d = db()
    body = request.get_json(force=True)
    n = int(body['n'])
    selected = sorted(s.upper() for s in body.get('selected', []))
    q = full_q(sid, n)
    correct = selected == sorted(q['answer'])
    d.execute('INSERT OR REPLACE INTO answers(client, set_id, n, selected, correct, ts)'
              ' VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
              (c, sid, n, json.dumps(selected), 1 if correct else 0))
    if correct:
        d.execute('DELETE FROM wrong WHERE client=? AND set_id=? AND n=?', (c, sid, n))
    else:
        d.execute('INSERT OR IGNORE INTO wrong(client, set_id, n, ts) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
              (c, sid, n))
    mode = body.get('mode', 'seq')
    order = get_order(c, sid, mode)
    if n in order:
        pos = min(order.index(n) + 1, len(order))
        d.execute('INSERT OR REPLACE INTO progress(client, set_id, mode, pos) VALUES (?, ?, ?, ?)',
              (c, sid, mode, pos))
    d.commit()
    return jsonify({'correct': correct, 'answer': q['answer'],
                    'explanation': q['explanation'], 'exp_images': q['exp_images']})


@app.route('/api/favorites')
def favorites():
    """本套已收藏的题号列表。"""
    c = cid()
    sid = req_set()
    d = db()
    rows = d.execute('SELECT n FROM favorites WHERE client=? AND set_id=? ORDER BY ts',
                     (c, sid)).fetchall()
    return jsonify([r['n'] for r in rows])


@app.route('/api/favorite', methods=['POST'])
def favorite():
    """收藏/取消收藏某题（toggle）。"""
    c = cid()
    sid = req_set()
    d = db()
    body = request.get_json(force=True)
    n = int(body['n'])
    row = d.execute('SELECT 1 FROM favorites WHERE client=? AND set_id=? AND n=?',
                    (c, sid, n)).fetchone()
    if row:
        d.execute('DELETE FROM favorites WHERE client=? AND set_id=? AND n=?', (c, sid, n))
        faved = False
    else:
        d.execute('INSERT OR IGNORE INTO favorites(client, set_id, n) VALUES (?, ?, ?)',
                  (c, sid, n))
        faved = True
    d.commit()
    return jsonify({'faved': faved})


@app.route('/api/reset', methods=['POST'])
def reset():
    c = cid()
    sid = req_set()
    d = db()
    body = request.get_json(force=True) or {}
    mode = body.get('mode', 'seq')
    d.execute('DELETE FROM progress WHERE client=? AND set_id=? AND mode=?', (c, sid, mode))
    if mode == 'rand':
        order = ORDERS[sid][:]
        random.shuffle(order)
        d.execute('INSERT OR REPLACE INTO rand_order(client, set_id, order_json) VALUES (?, ?, ?)',
                  (c, sid, json.dumps(order)))
    d.commit()
    return jsonify({'ok': True})


@app.route('/api/reset_set', methods=['POST'])
def reset_set():
    """重做整套：清除该套全部作答记录与进度，回到未做状态（错题本保留）。"""
    c = cid()
    sid = req_set()
    d = db()
    d.execute('DELETE FROM answers WHERE client=? AND set_id=?', (c, sid))
    d.execute('DELETE FROM progress WHERE client=? AND set_id=?', (c, sid))
    order = ORDERS[sid][:]
    random.shuffle(order)
    d.execute('INSERT OR REPLACE INTO rand_order(client, set_id, order_json) VALUES (?, ?, ?)',
              (c, sid, json.dumps(order)))
    d.commit()
    return jsonify({'ok': True})


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8001)
