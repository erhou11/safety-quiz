"""安全生产技术刷题 App 后端：Flask + SQLite，题目作答/进度/错题全部服务端持久化。
支持多套题：每套题独立的进度、随机顺序与错题本。"""
import json, os, re, sqlite3, secrets, random, shutil, threading, hashlib
from datetime import timedelta, date
from flask import Flask, request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from collections import Counter
import upload_lib
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def extract_hints(explanation, max_hints=6):
    """从简答题参考答案中提取提示关键词，每条不超过5字。"""
    # 按（1）（2）或 1. 2. 分点
    points = re.split(r'[（(]\d+[)）]|\d+[.、]\s*', explanation)
    points = [p.strip('；;。，, \n') for p in points if p.strip()]
    hints = []
    for p in points:
        # 取第一分句
        clause = re.split(r'[，；;。]', p)[0].strip()
        # 去书名号内容（规范名称太长不适合做提示）
        clause = re.sub(r'《[^》]*》', '', clause)
        # 去常见动词前缀
        clause = re.sub(r'^(设置|采用|进行|参照|依照|按照|指出|简述|列出|结合|根据)', '', clause)
        clause = clause.strip('，,、。；;：: ')
        # 优先提取数字+单位（如50%、25mm、10t）
        m = re.search(r'\d+(?:\.\d+)?\s*(?:%|mm|t|℃|m|h|个月|年)', clause)
        if m:
            hint = m.group(0).replace(' ', '')
        else:
            # 取前5字，但跳过太短的无意义片段
            hint = clause[:5].strip()
            if len(hint) < 2:
                continue
        hint = hint.strip('，,、。；;：:')
        if hint and hint not in hints and len(hints) < max_hints:
            hints.append(hint)
    return hints

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, 'quiz.db')

with open(os.path.join(BASE, 'questions_full.json'), encoding='utf-8') as f:
    _data = json.load(f)
SETS = _data['sets']
SUBJECTS = _data.get('subjects', [])
CATEGORIES = _data.get('categories', [])
for _s in SUBJECTS:
    _s.setdefault('category', 'zj-anquan')

# 各考试类别上传时可选择的科目/专业（规范清单，2026-10-26 用户要求上传页改下拉选择）：
# 一建/二建的专业名即该专业的「专业实务」方向，与注安实务方向 tab 的命名口径一致。
CATEGORY_SUBJECTS = {
    'yj-jianzao': ['建设工程经济', '建设工程法规及相关知识', '建设工程项目管理',
                    '建筑工程', '公路工程', '铁路工程', '民航机场工程', '港口与航道工程',
                    '水利水电工程', '市政公用工程', '通信与广电工程', '矿业工程', '机电工程'],
    'ej-jianzao': ['建设工程施工管理', '建设工程法规及相关知识',
                    '建筑工程', '公路工程', '水利水电工程', '市政公用工程', '矿业工程', '机电工程'],
    'yj-xiaofang': ['消防安全技术实务', '消防安全技术综合能力', '消防安全案例分析'],
    'ej-anquan': ['安全生产法律法规', '安全生产专业实务'],
    'cj-anquan': ['安全生产法律法规', '安全生产实务'],
}


def _category_subjects():
    """上传页下拉清单：规范清单在前，数据里已有的科目补充在后（去重）。"""
    out = {}
    for c in CATEGORIES:
        cid = c['id']
        titles = list(CATEGORY_SUBJECTS.get(cid, []))
        for s in SUBJECTS:
            if s.get('category', 'zj-anquan') == cid and s['title'] not in titles:
                titles.append(s['title'])
        out[cid] = titles
    return out
def _build_indexes():
    """由 _data 重建套题/题目索引（启动加载与热重读共用）。

    引用型套题（alias_of）不重复保存题目：索引层把源套题的题目映射到引用套的
    set id 下，磁盘 questions 里始终只有一份。源套题的作答进度仍按引用套 id
    独立记录，互不影响。
    """
    global SET_MAP, QUESTIONS, SET_IDS, ORDERS
    SET_MAP = {s['id']: s for s in SETS}
    QUESTIONS = {}
    for q in _data['questions']:
        QUESTIONS['%s:%d' % (q['set'], q['n'])] = q
    SET_IDS = [s['id'] for s in SETS]
    ORDERS = {}
    for sid in SET_IDS:
        ORDERS[sid] = sorted(int(k.split(':')[1]) for k in QUESTIONS
                             if k.startswith(sid + ':'))
    pending = [s for s in SETS if s.get('alias_of')]
    while pending:
        progressed = False
        for s in list(pending):
            src = s.get('alias_of')
            if src in ORDERS and ORDERS[src] and '%s:%d' % (src, ORDERS[src][0]) in QUESTIONS:
                for n in ORDERS[src]:
                    QUESTIONS['%s:%d' % (s['id'], n)] = QUESTIONS['%s:%d' % (src, n)]
                ORDERS[s['id']] = list(ORDERS[src])
                pending.remove(s)
                progressed = True
        if not progressed:
            break


def _canonical_set_id(sid):
    """沿 alias_of 链找到真正存题目的源套题 id（防链环）。"""
    seen = set()
    cur = sid
    while cur in SET_MAP and SET_MAP[cur].get('alias_of') and cur not in seen:
        seen.add(cur)
        cur = SET_MAP[cur]['alias_of']
    return cur


def _set_questions(sid):
    """按套题顺序取题目；引用型套题返回源套题的同一批题目对象。"""
    return [QUESTIONS['%s:%d' % (sid, n)] for n in ORDERS.get(sid, [])
            if '%s:%d' % (sid, n) in QUESTIONS]


_build_indexes()

# ---- 题库文件变更自动重读（2026-10-26 方案A）----
# 题库数据在每个 gunicorn worker 内存里各一份：upload_confirm 只更新处理该请求的
# worker 并写盘，其余 worker 不重读就会不认识新套题（req_set 静默回退 s1=85 题）。
# 每个请求前比对 questions_full.json 的修改时间，变了就整体重读对齐，无需重启服务。
DATA_FILE = os.path.join(BASE, 'questions_full.json')
_seen_mtime = os.path.getmtime(DATA_FILE)
_reload_lock = threading.Lock()


def _maybe_reload():
    global _seen_mtime, _data, SETS, SUBJECTS, CATEGORIES
    try:
        mt = os.path.getmtime(DATA_FILE)
    except OSError:
        return
    if mt == _seen_mtime:
        return
    with _reload_lock:
        if mt == _seen_mtime:
            return
        try:
            with open(DATA_FILE, encoding='utf-8') as f:
                fresh = json.load(f)
        except Exception:
            return  # 读失败（多为文件正被原子替换的瞬间）：保留旧数据，下个请求再试
        _data = fresh
        SETS = _data['sets']
        SUBJECTS = _data.get('subjects', [])
        CATEGORIES = _data.get('categories', [])
        for _s in SUBJECTS:
            _s.setdefault('category', 'zj-anquan')
        _build_indexes()
        _seen_mtime = mt

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


@app.before_request
def _sync_questions_data():
    _maybe_reload()


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
    CREATE TABLE IF NOT EXISTS donations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        display_name TEXT,
        amount REAL NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS uploads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        category TEXT, subject_title TEXT, title TEXT, filename TEXT,
        status TEXT DEFAULT 'parsing',
        summary TEXT, set_id TEXT,
        file_sha256 TEXT, answer_sha256 TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    ''')
    _cols = [r[1] for r in d.execute('PRAGMA table_info(uploads)').fetchall()]
    for _col in ('answer_filename', 'file_sha256', 'answer_sha256'):
        if _cols and _col not in _cols:
            d.execute('ALTER TABLE uploads ADD COLUMN %s TEXT' % _col)
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


def set_visible(s):
    """套题可见性：public 人人可见；private 仅所有者（按登录邮箱匹配）可见。
    旧数据没有 visibility 字段时默认 public，保证老版本 JSON 行为不变。"""
    if s.get('visibility', 'public') == 'public':
        return True
    email = session.get('email')
    return bool(email) and email == s.get('owner_email')


_GUARDED_PATHS = {'/api/state', '/api/questions', '/api/round', '/api/visit',
                  '/api/answer', '/api/favorites', '/api/favorite',
                  '/api/reset', '/api/reset_set'}


@app.before_request
def _guard_private_sets():
    if request.path in _GUARDED_PATHS:
        sid = (request.args.get('set') or
               (request.get_json(silent=True) or {}).get('set') or 's1')
        s = SET_MAP.get(sid)
        if s is not None and not set_visible(s):
            return jsonify({'ok': False, 'msg': '该套题未公开'}), 403


def public_q(sid, n):
    q = QUESTIONS['%s:%d' % (sid, n)]
    out = {'n': q['n'], 'cat': q['cat'], 'type': q['type'],
            'stem': q['stem'], 'options': q['options'], 'images': q['images'],
            'case_bg': q.get('case_bg', ''), 'case_images': q.get('case_images', [])}
    if q['type'] == 'essay':
        out['hints'] = extract_hints(q.get('explanation', ''))
    return out


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
    if mode == 'essay':
        return [n for n in ORDERS[sid]
                if QUESTIONS['%s:%d' % (sid, n)]['type'] == 'essay']
    return ORDERS[sid]


@app.route('/api/meta')
def meta():
    c = cid()
    d = db()
    ans_counts = {r['set_id']: r['c'] for r in d.execute(
        'SELECT set_id, COUNT(*) AS c FROM answers WHERE client=? GROUP BY set_id', (c,))}
    out = []
    for s in SETS:
        if not set_visible(s):
            continue
        qs = _set_questions(s['id'])
        out.append({'id': s['id'], 'title': s['title'], 'kicker': s['kicker'],
                    'subject': s.get('subject', 'jishu'), 'desc': s.get('desc', ''),
                    'category': s.get('category', 'zj-anquan'),
                    'alias_of': s.get('alias_of'),
                    'visibility': s.get('visibility', 'public'),
                    'mine': bool(session.get('email')) and session.get('email') == s.get('owner_email'),
                    'total': len(qs),
                    'single': sum(1 for q in qs if q['type'] == 'single'),
                    'multi': sum(1 for q in qs if q['type'] == 'multi'),
                    'essay': sum(1 for q in qs if q['type'] == 'essay'),
                    'answered': ans_counts.get(s['id'], 0)})
    return jsonify({'categories': CATEGORIES, 'subjects': SUBJECTS, 'sets': out,
                    'category_subjects': _category_subjects()})


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


def _vip_tier(total):
    """贵宾等级（按累计打赏金额）与名字颜色：2026-10-26 用户定版。"""
    if total >= 100:
        return '紫金贵宾', '#c792ff'
    if total >= 50:
        return '黄金贵宾', '#f0c75e'
    if total >= 10:
        return '白银贵宾', '#d7dde6'
    if total > 0:
        return '青铜贵宾', '#d08a4e'
    return '普通用户', '#b9b6ac'


def _donation_total(email):
    if not email:
        return 0
    row = db().execute('SELECT COALESCE(SUM(amount), 0) AS t FROM donations WHERE email=?',
                       (email,)).fetchone()
    return row['t'] or 0


def _daily_limit(email):
    """每日上传上限：普通 5 套；累计打赏 10 元以上（不含 10 元）20 套（2026-10-26 用户定）。"""
    return 20 if _donation_total(email) > 10 else DAILY_UPLOAD_LIMIT


_TIER_RANK = {'普通用户': 0, '青铜贵宾': 1, '白银贵宾': 2, '黄金贵宾': 3, '紫金贵宾': 4}


def _tier_rank(total):
    return _TIER_RANK[_vip_tier(total)[0]]


@app.get('/api/me')
def me():
    if session.get('uid'):
        email = session.get('email')
        total = _donation_total(email)
        tier, color = _vip_tier(total)
        return jsonify({'logged_in': True, 'email': email,
                        'donation_total': total, 'vip_tier': tier, 'vip_color': color})
    return jsonify({'logged_in': False})


@app.get('/api/donations/recent')
def donations_recent():
    """打赏公告（公开）：最近 10 笔，附捐献者当前累计等级与颜色。"""
    rows = db().execute(
        'SELECT d.display_name, d.amount, d.created_at, '
        '(SELECT COALESCE(SUM(amount), 0) FROM donations WHERE email = d.email) AS total '
        'FROM donations d ORDER BY d.id DESC LIMIT 10').fetchall()
    out = []
    for r in rows:
        tier, color = _vip_tier(r['total'])
        amt = r['amount']
        out.append({'display': r['display_name'],
                    'amount': int(amt) if float(amt).is_integer() else amt,
                    'tier': tier, 'color': color, 'at': r['created_at']})
    return jsonify(out)


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
    if mode not in ('seq', 'rand', 'wrong', 'fav', 'essay'):
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


# ---------------- 用户上传题库（阶段3：免费 + 打赏） ----------------
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
DAILY_UPLOAD_LIMIT = 5  # 暂定防滥用上限（套/天），待用户正式定


def _save_questions_data():
    """运行时新增套题/科目后把题库 JSON 原子写回磁盘（重启不丢）。"""
    _data['subjects'] = SUBJECTS
    tmp = os.path.join(BASE, 'questions_full.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(BASE, 'questions_full.json'))


def _pipeline_notify(up_id, src_pdf, orig_name, email, category, subject_title,
                     ans_pdf=None, ans_name=None):
    """解析未过时把 PDF 登记进三 AI 流水线黑板（尽力而为，失败不影响主流程）。"""
    pdir = os.environ.get('PIPELINE_DIR', '/opt/quizapp-pipeline')
    inbox = os.path.join(pdir, 'inbox')
    if not os.path.isdir(inbox):
        return
    try:
        dst = os.path.join(inbox, 'U-%d-%s' % (up_id, os.path.basename(orig_name) or 'upload.pdf'))
        shutil.copyfile(src_pdf, dst)
        ans_dst_name = None
        if ans_pdf and os.path.exists(ans_pdf):
            ans_dst_name = 'U-%d-答案-%s' % (up_id, os.path.basename(ans_name) or 'answer.pdf')
            shutil.copyfile(ans_pdf, os.path.join(inbox, ans_dst_name))
        bb_path = os.path.join(pdir, 'blackboard.json')
        lock = os.path.join(pdir, 'blackboard.lock')
        try:
            os.mkdir(lock)
        except FileExistsError:
            return
        try:
            with open(bb_path, encoding='utf-8') as f:
                bb = json.load(f)
            task = {
                'id': 'U-%d' % up_id, 'pdf': 'inbox/' + os.path.basename(dst),
                'subject': subject_title, 'category': category, 'questions': 0,
                'status': 'pending', 'from_upload': True, 'uploader': email,
                'created_at': date.today().isoformat()}
            if ans_dst_name:
                task['answer_pdf'] = 'inbox/' + ans_dst_name
            bb.setdefault('task_pool', []).append(task)
            bb.setdefault('notes', []).append({
                'at': date.today().isoformat(), 'from': 'boss',
                'text': '用户上传 U-%d 自动解析未过，转人工处理：%s（%s）'
                        % (up_id, orig_name, subject_title)})
            with open(bb_path, 'w', encoding='utf-8') as f:
                json.dump(bb, f, ensure_ascii=False, indent=1)
        finally:
            os.rmdir(lock)
    except Exception:
        pass


def _my_upload(up_id):
    if not session.get('uid'):
        return None
    return db().execute('SELECT * FROM uploads WHERE id=? AND email=?',
                        (up_id, session.get('email'))).fetchone()


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _backfill_upload_hashes(exclude_up_id=None):
    """给历史上传补算文件指纹（一次性效果：算过的行不再重算）。"""
    d = db()
    rows = d.execute('SELECT id FROM uploads WHERE file_sha256 IS NULL').fetchall()
    changed = False
    for r in rows:
        if exclude_up_id is not None and r['id'] == exclude_up_id:
            continue
        qpath = os.path.join(UPLOAD_DIR, '%d.pdf' % r['id'])
        if not os.path.exists(qpath):
            continue
        apath = os.path.join(UPLOAD_DIR, '%d_ans.pdf' % r['id'])
        try:
            d.execute('UPDATE uploads SET file_sha256=?, answer_sha256=? WHERE id=?',
                      (_sha256_file(qpath),
                       _sha256_file(apath) if os.path.exists(apath) else None,
                       r['id']))
            changed = True
        except Exception:
            continue
    if changed:
        d.commit()


def _library_match_info(s, email):
    """命中题库时的对外信息：公开套和本人套可报名字；他人私有套只报事实，
    不泄露对方套题名称与所有者。"""
    mine = bool(email) and s.get('owner_email') == email
    vis = s.get('visibility', 'public')
    return {'set_id': s['id'],
            'title': s.get('title') if (vis == 'public' or mine) else None,
            'visibility': vis,
            'mine': mine,
            'total': len(ORDERS.get(s['id'], [])),
            'pct': 100,
            'exact': True}


def _exact_library_match(email, new_qs):
    """解析后全题库查重：题目指纹多重集与某个非引用套题完全一致才算整套重复。

    用多重集（Counter）而非集合：套内若有两道相同题，题量差异不能被集合吞掉。
    命中后确认生成时只建引用套题，不再把题目重复写进题库。
    """
    try:
        from dedup_check import fingerprint
        new_counter = Counter(fingerprint(q) for q in new_qs)
        if not new_counter:
            return None
        for s in SETS:
            if s.get('alias_of'):
                continue
            qs = _set_questions(s['id'])
            if len(qs) != len(new_qs):
                continue
            if Counter(fingerprint(q) for q in qs) == new_counter:
                return _library_match_info(s, email)
        return None
    except Exception:
        return None


def _public_library_dup(email, new_qs):
    """与公共题库高度相同（≥90%）但非整套完全一致时的提示；不拦、不自动引用。"""
    try:
        from dedup_check import fingerprint
        new_fps = {fingerprint(q) for q in new_qs}
        if not new_fps:
            return None
        best = None
        for s in SETS:
            if s.get('alias_of') or s.get('visibility', 'public') != 'public':
                continue
            if email and s.get('owner_email') == email:
                continue
            qs = _set_questions(s['id'])
            if not qs:
                continue
            fps = {fingerprint(q) for q in qs}
            ratio = len(new_fps & fps) / len(new_fps)
            if ratio >= 0.9 and (best is None or ratio > best[0]):
                best = (ratio, s)
        if best is None:
            return None
        return {'set_id': best[1]['id'], 'title': best[1].get('title'),
                'pct': round(best[0] * 100)}
    except Exception:
        return None


def _find_file_reuse(up_id, q_hash, a_hash):
    """上传前文件指纹复用：题目+答案两个 PDF 字节级完全相同才命中。

    返回 ('library', 源套题id) 或 ('parse', 已解析题目列表) 或 None。
    命中 library 时连题目都不用提取；命中 parse 时跳过提取与解析、复用解析结果。
    """
    _backfill_upload_hashes(exclude_up_id=up_id)
    d = db()
    rows = d.execute(
        "SELECT * FROM uploads WHERE id<>? AND file_sha256=? "
        "AND COALESCE(answer_sha256, '')=COALESCE(?, '') "
        "AND status IN ('ready', 'done') "
        "ORDER BY CASE WHEN status='done' THEN 0 ELSE 1 END, id",
        (up_id, q_hash, a_hash)).fetchall()
    for row in rows:
        if row['set_id'] and row['set_id'] in SET_MAP:
            root = _canonical_set_id(row['set_id'])
            if _set_questions(root):
                return ('library', root)
    for row in rows:
        p = os.path.join(UPLOAD_DIR, '%d.json' % row['id'])
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding='utf-8') as fh:
                qs = json.load(fh)
            if isinstance(qs, list) and qs:
                return ('parse', qs)
        except Exception:
            continue
    return None


def _find_dup(email, new_qs, exclude_up_id=None):
    """上传查重（2026-10-26 用户定）：新解析的题目与本人已有套题、本人其他待确认
    上传逐题比指纹（口径同 dedup_check.fingerprint）；以新套题目数为分母，
    重合 ≥90% 视为整套重复，返回重合最高的一条 {'title', 'pct'}，否则 None。
    只提示不拦截；查重自身出错时返回 None，绝不影响上传主流程。"""
    try:
        from dedup_check import fingerprint
        new_fps = {fingerprint(q) for q in new_qs}
        if not new_fps:
            return None
        best = None  # (ratio, title)
        for s in SETS:
            if s.get('owner_email') != email:
                continue
            fps = {fingerprint(q) for q in _set_questions(s['id'])}
            if not fps:
                continue
            ratio = len(new_fps & fps) / len(new_fps)
            if ratio >= 0.9 and (best is None or ratio > best[0]):
                best = (ratio, s.get('title') or s['id'])
        try:
            rows = db().execute("SELECT id, title FROM uploads WHERE email=? AND status='ready'",
                                (email,)).fetchall()
        except Exception:
            rows = []  # DB 读失败只跳过待确认比对，不能连累已命中的套题结果
        for r in rows:
            if exclude_up_id is not None and r['id'] == exclude_up_id:
                continue
            try:
                with open(os.path.join(UPLOAD_DIR, '%d.json' % r['id']), encoding='utf-8') as fh:
                    other = json.load(fh)
                fps = {fingerprint(q) for q in other}
            except Exception:
                continue
            if not fps:
                continue
            ratio = len(new_fps & fps) / len(new_fps)
            if ratio >= 0.9 and (best is None or ratio > best[0]):
                best = (ratio, r['title'])
        if best is None:
            return None
        return {'title': best[1], 'pct': round(best[0] * 100)}
    except Exception:
        return None


@app.post('/api/upload')
def upload_pdf():
    if not session.get('uid'):
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    f = request.files.get('file')
    if f is None or not (f.filename or '').lower().endswith('.pdf'):
        return jsonify({'ok': False, 'msg': '请选择 PDF 文件'}), 400
    af = request.files.get('answer_file')
    ans_name = af.filename if (af is not None and (af.filename or '').lower().endswith('.pdf')) else None
    category = (request.form.get('category') or 'zj-anquan').strip()
    if CATEGORIES and category not in {c['id'] for c in CATEGORIES}:
        return jsonify({'ok': False, 'msg': '考试类别不正确'}), 400
    subject_title = (request.form.get('subject_title') or '').strip()[:30]
    if not subject_title:
        return jsonify({'ok': False, 'msg': '请填写科目名称'}), 400
    title = (request.form.get('title') or '').strip()[:60] or \
        os.path.splitext(os.path.basename(f.filename))[0][:60]
    email = session.get('email')
    d = db()
    today_n = d.execute("SELECT COUNT(*) AS c FROM uploads WHERE email=? AND date(created_at)=date('now')",
                        (email,)).fetchone()['c']
    limit = _daily_limit(email)
    if today_n >= limit:
        return jsonify({'ok': False, 'msg': '今天上传次数已达上限（%d 套），明天再来' % limit}), 429
    cur = d.execute('INSERT INTO uploads(email, category, subject_title, title, filename, answer_filename, status)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (email, category, subject_title, title, f.filename, ans_name, 'parsing'))
    up_id = cur.lastrowid
    d.commit()
    pdf_path = os.path.join(UPLOAD_DIR, '%d.pdf' % up_id)
    f.save(pdf_path)
    ans_path = None
    if ans_name:
        ans_path = os.path.join(UPLOAD_DIR, '%d_ans.pdf' % up_id)
        af.save(ans_path)
    q_hash = _sha256_file(pdf_path)
    a_hash = _sha256_file(ans_path) if ans_path else None
    d.execute('UPDATE uploads SET file_sha256=?, answer_sha256=? WHERE id=?',
              (q_hash, a_hash, up_id))
    d.commit()

    # 先查文件指纹：同文件以前已解析/已成套的，直接复用，不再提取、不再解析。
    qs, warnings = [], []
    library_match = None
    reused = None
    reuse = _find_file_reuse(up_id, q_hash, a_hash)
    if reuse and reuse[0] == 'library':
        root = reuse[1]
        qs = _set_questions(root)
        library_match = _library_match_info(SET_MAP[root], email)
        reused = {'kind': 'file_library', 'extraction_skipped': True}
    elif reuse and reuse[0] == 'parse':
        qs = reuse[1]
        reused = {'kind': 'file_parse', 'extraction_skipped': True}
    else:
        text = upload_lib.extract_text(pdf_path)
        if len(text.strip()) < 200:
            qs, warnings = [], ['未提取到文字层（可能是扫描版），转人工处理']
        elif ans_path:
            qs, warnings = upload_lib.parse_pair(text, upload_lib.extract_text(ans_path))
        else:
            qs, warnings = upload_lib.parse_text(text)

    if qs:
        if library_match is None:
            # 解析结果先落 staging JSON（确认生成引用套时不会写入题库，仅作兜底），
            # 再和全题库做整套查重：完全一致就走引用，不重复入库。
            with open(os.path.join(UPLOAD_DIR, '%d.json' % up_id), 'w', encoding='utf-8') as fh:
                json.dump(qs, fh, ensure_ascii=False)
            library_match = _exact_library_match(email, qs)
        summary = {'total': len(qs),
                   'single': sum(1 for q in qs if q['type'] == 'single'),
                   'multi': sum(1 for q in qs if q['type'] == 'multi'),
                   'essay': sum(1 for q in qs if q['type'] == 'essay'),
                   'warnings': warnings}
        if reused:
            summary['reused'] = reused
        if library_match:
            summary['library_match'] = library_match
        else:
            dup = _find_dup(email, qs, exclude_up_id=up_id)
            if dup:
                summary['dup'] = dup
            library_dup = _public_library_dup(email, qs)
            if library_dup:
                summary['library_dup'] = library_dup
        d.execute('UPDATE uploads SET status=?, summary=? WHERE id=?',
                  ('ready', json.dumps(summary, ensure_ascii=False), up_id))
        status = 'ready'
    else:
        summary = {'total': 0, 'warnings': warnings}
        d.execute('UPDATE uploads SET status=?, summary=? WHERE id=?',
                  ('need_review', json.dumps(summary, ensure_ascii=False), up_id))
        status = 'need_review'
        _pipeline_notify(up_id, pdf_path, f.filename, email, category, subject_title,
                         ans_pdf=ans_path, ans_name=ans_name)
    d.commit()
    return jsonify({'ok': True, 'id': up_id, 'status': status, 'summary': summary})


@app.get('/api/upload_info')
def upload_info():
    """上传页温馨提示用的实时信息：人工审核排队总数 + 本人今日已用额度。"""
    if not session.get('uid'):
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    d = db()
    queue_total = d.execute("SELECT COUNT(*) AS c FROM uploads WHERE status='need_review'").fetchone()['c']
    email = session.get('email')
    today_used = d.execute("SELECT COUNT(*) AS c FROM uploads WHERE email=? AND date(created_at)=date('now')",
                           (email,)).fetchone()['c']
    limit = _daily_limit(email)
    total = _donation_total(email)
    tier, color = _vip_tier(total)
    return jsonify({'ok': True, 'queue_total': queue_total, 'today_used': today_used,
                    'daily_limit': limit, 'remaining': max(0, limit - today_used),
                    'vip_tier': tier, 'vip_color': color, 'donation_total': total})


@app.get('/api/my_uploads')
def my_uploads():
    if not session.get('uid'):
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    d = db()
    # 人工审核排队位置（贵宾插队规则，2026-10-26 用户定）：等级高→低，同等级按提交时间先后
    pend = d.execute("SELECT id, email FROM uploads WHERE status='need_review' ORDER BY id").fetchall()
    _totals = {}

    def _rank(email):
        if email not in _totals:
            _totals[email] = _tier_rank(_donation_total(email))
        return _totals[email]

    queue_pos = {}
    for v in pend:
        rv = _rank(v['email'])
        queue_pos[v['id']] = sum(1 for o in pend
                                 if _rank(o['email']) > rv
                                 or (_rank(o['email']) == rv and o['id'] < v['id']))
    rows = d.execute('SELECT id, category, subject_title, title, filename, answer_filename, status, summary, set_id, created_at'
                        ' FROM uploads WHERE email=? ORDER BY id DESC LIMIT 50',
                        (session.get('email'),)).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item['summary'] = json.loads(item['summary'] or '{}')
        if item['status'] == 'need_review' and item['id'] in queue_pos:
            ahead = queue_pos[item['id']]
            item['queue_ahead'] = ahead
            item['eta_hours'] = min(72, (ahead + 1) * 12)
            item['is_vip'] = _donation_total(session.get('email')) > 0
        out.append(item)
    return jsonify(out)


@app.post('/api/upload/<int:up_id>/confirm')
def upload_confirm(up_id):
    row = _my_upload(up_id)
    if row is None:
        return jsonify({'ok': False, 'msg': '记录不存在或无权操作'}), 404
    if row['status'] != 'ready':
        return jsonify({'ok': False, 'msg': '该上传不在待确认状态'}), 400
    try:
        summary = json.loads(row['summary'] or '{}')
    except Exception:
        summary = {}
    json_path = os.path.join(UPLOAD_DIR, '%d.json' % up_id)
    source_id = (summary.get('library_match') or {}).get('set_id')
    if source_id and source_id in SET_MAP:
        source_id = _canonical_set_id(source_id)
    elif source_id and not os.path.exists(json_path):
        return jsonify({'ok': False, 'msg': '题库中的原套题已不存在，请重新上传'}), 409
    else:
        source_id = None
    category = row['category'] or 'zj-anquan'
    subject = next((s for s in SUBJECTS
                    if s.get('category', 'zj-anquan') == category and s['title'] == row['subject_title']), None)
    if subject is None:
        subject = {'id': 'sj%d' % up_id, 'title': row['subject_title'],
                   'desc': '用户上传', 'category': category}
        SUBJECTS.append(subject)
    sid = 'up%d' % up_id
    if source_id:
        # 整套重复：只在用户名下新建一个引用套题，题目仍用题库里原套的，
        # 不把题目再写进 questions_full.json。作答进度按这个新套题 id 独立记录。
        if sid in SET_MAP:
            d = db()
            d.execute('UPDATE uploads SET status=?, set_id=? WHERE id=?', ('done', sid, up_id))
            d.commit()
            return jsonify({'ok': True, 'set': sid, 'total': len(ORDERS.get(sid, [])),
                            'alias_of': source_id, 'reused': True})
        new_set = {'id': sid, 'subject': subject['id'], 'title': row['title'],
                   'kicker': '用户上传', 'desc': '',
                   'category': category, 'owner_email': row['email'],
                   'created_at': date.today().isoformat(), 'visibility': 'private',
                   'alias_of': source_id}
        SETS.append(new_set)
        _build_indexes()
        _save_questions_data()
        d = db()
        d.execute('UPDATE uploads SET status=?, set_id=? WHERE id=?', ('done', sid, up_id))
        d.commit()
        return jsonify({'ok': True, 'set': sid, 'total': len(ORDERS.get(sid, [])),
                        'alias_of': source_id, 'reused': True})
    with open(json_path, encoding='utf-8') as fh:
        parsed = json.load(fh)
    new_set = {'id': sid, 'subject': subject['id'], 'title': row['title'],
               'kicker': '用户上传', 'desc': '', 'category': category,
               'owner_email': row['email'], 'created_at': date.today().isoformat(),
               'visibility': 'private'}
    SETS.append(new_set)
    SET_MAP[sid] = new_set
    SET_IDS.append(sid)
    ns = []
    for i, q in enumerate(parsed, 1):
        q['set'] = sid
        q['n'] = i
        q['cat'] = row['subject_title']
        _data['questions'].append(q)
        QUESTIONS['%s:%d' % (sid, i)] = q
        ns.append(i)
    ORDERS[sid] = ns
    _save_questions_data()
    d = db()
    d.execute('UPDATE uploads SET status=?, set_id=? WHERE id=?', ('done', sid, up_id))
    d.commit()
    return jsonify({'ok': True, 'set': sid, 'total': len(ns)})


@app.post('/api/upload/<int:up_id>/discard')
def upload_discard(up_id):
    row = _my_upload(up_id)
    if row is None:
        return jsonify({'ok': False, 'msg': '记录不存在或无权操作'}), 404
    if row['status'] == 'done':
        return jsonify({'ok': False, 'msg': '已生成套题，不能在此放弃'}), 400
    d = db()
    d.execute('DELETE FROM uploads WHERE id=?', (up_id,))
    d.commit()
    for ext in ('pdf', 'json'):
        p = os.path.join(UPLOAD_DIR, '%d.%s' % (up_id, ext))
        if os.path.exists(p):
            os.remove(p)
    p = os.path.join(UPLOAD_DIR, '%d_ans.pdf' % up_id)
    if os.path.exists(p):
        os.remove(p)
    return jsonify({'ok': True})


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8001)
