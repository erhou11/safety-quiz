#!/usr/bin/env python3
"""总管审核工具（上传三审制，2026-10-26 用户定）。

在服务器 /opt/quizapp 下用 venv 的 python 运行：
  review_admin.py list
      列出待处理队列：need_review / defect / owner_review / owner_final。
  review_admin.py set-defect <id> <problems.json>
      二审结论=原文件缺陷：need_review -> defect，把问题清单（字符串数组
      JSON 文件）写进 summary.problems，展示给上传者确认。
  review_admin.py reparse <id>
      三审第一步：按原管线重跑存盘原文件，打印 READY 或 BLOCKING 明细；
      READY 时同步把状态恢复为 ready（与 confirm_ok 的自动复核同口径）。
  review_admin.py set-owner-final <id>
      三审仍不过、原卷已打包发站长亲审后标记：owner_review -> owner_final。
"""
import json
import os
import sqlite3
import sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'data', 'quiz.db')
PDIR = os.environ.get('PIPELINE_DIR', '/opt/quizapp-pipeline')


def board(text=None, task_id=None, task_status=None):
    bb_path = os.path.join(PDIR, 'blackboard.json')
    if not os.path.exists(bb_path):
        return
    lock = os.path.join(PDIR, 'blackboard.lock')
    try:
        os.mkdir(lock)
    except OSError:
        return
    try:
        with open(bb_path, encoding='utf-8') as f:
            bb = json.load(f)
        if task_id and task_status:
            for t in bb.get('task_pool', []):
                if t.get('id') == task_id:
                    t['status'] = task_status
        if text:
            bb.setdefault('notes', []).append(
                {'at': date.today().isoformat(), 'from': 'boss', 'text': text})
        with open(bb_path, 'w', encoding='utf-8') as f:
            json.dump(bb, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    finally:
        try:
            os.rmdir(lock)
        except OSError:
            pass


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get(c, up_id):
    return c.execute('SELECT * FROM uploads WHERE id=?', (up_id,)).fetchone()


def cmd_list():
    c = conn()
    rows = c.execute(
        "SELECT id, email, title, status, summary FROM uploads "
        "WHERE status IN ('need_review','defect','owner_review','owner_final') "
        "ORDER BY id").fetchall()
    if not rows:
        print('（队列为空）')
    for r in rows:
        s = json.loads(r['summary'] or '{}')
        probs = s.get('problems') or []
        print('U-%d [%s] %s <%s> 题数=%s 问题=%s'
              % (r['id'], r['status'], r['title'], r['email'],
                 s.get('total'), '；'.join(probs) if probs else '（未写）'))


def cmd_set_defect(up_id, problems_path):
    with open(problems_path, encoding='utf-8') as f:
        problems = json.load(f)
    assert isinstance(problems, list) and problems, 'problems 必须是非空字符串数组'
    c = conn()
    row = get(c, up_id)
    if row is None:
        print('不存在的 upload id'); sys.exit(1)
    if row['status'] != 'need_review':
        print('当前状态是 %s，不是 need_review，不能翻 defect' % row['status']); sys.exit(1)
    summary = json.loads(row['summary'] or '{}')
    summary['problems'] = [str(p) for p in problems]
    summary['defect_at'] = date.today().isoformat()
    c.execute('UPDATE uploads SET status=?, summary=? WHERE id=?',
              ('defect', json.dumps(summary, ensure_ascii=False), up_id))
    c.commit()
    board(text='二审结论 U-%d：原文件本身有缺陷，已转「待上传者确认」，问题清单：%s'
               % (up_id, '；'.join(summary['problems'])),
          task_id='U-%d' % up_id, task_status='defect')
    print('U-%d -> defect，问题 %d 条' % (up_id, len(problems)))


def cmd_set_owner_final(up_id):
    c = conn()
    row = get(c, up_id)
    if row is None:
        print('不存在的 upload id'); sys.exit(1)
    if row['status'] != 'owner_review':
        print('当前状态是 %s，不是 owner_review' % row['status']); sys.exit(1)
    summary = json.loads(row['summary'] or '{}')
    summary['escalated_at'] = date.today().isoformat()
    c.execute('UPDATE uploads SET status=?, summary=? WHERE id=?',
              ('owner_final', json.dumps(summary, ensure_ascii=False), up_id))
    c.commit()
    board(text='U-%d 三审仍未通过，原卷已发站长亲审，等站长处理。' % up_id,
          task_id='U-%d' % up_id, task_status='owner_final')
    print('U-%d -> owner_final' % up_id)


def cmd_reparse(up_id):
    sys.path.insert(0, BASE)
    os.chdir(BASE)
    import app as quizapp
    with quizapp.app.app_context():
        row = quizapp.db().execute(
            'SELECT * FROM uploads WHERE id=?', (up_id,)).fetchone()
        if row is None:
            print('不存在的 upload id'); sys.exit(1)
        ready, info = quizapp._reparse_stored_upload(row)
        if ready:
            d = quizapp.db()
            d.execute('UPDATE uploads SET status=?, summary=? WHERE id=?',
                      ('ready', json.dumps(info['summary'], ensure_ascii=False), up_id))
            d.commit()
            print('READY total=%d（已恢复待确认生成）' % info['total'])
        else:
            print('BLOCKING ' + json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'list':
        cmd_list()
    elif len(sys.argv) == 4 and sys.argv[1] == 'set-defect':
        cmd_set_defect(int(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == 'set-owner-final':
        cmd_set_owner_final(int(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == 'reparse':
        cmd_reparse(int(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(2)
