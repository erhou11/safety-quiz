#!/usr/bin/env python3
"""上传原文件保留期清理（2026-10-27 用户定）。

规则：用户上传的原始 PDF（题目卷 + 答案卷）在套题已生成（uploads.status
='done'）满两个月后，若期间没有进入问题流程（defect / owner_review /
owner_final 等状态的记录不在清理范围），删除原 PDF 以节省空间；题库数据
（questions_full.json）、uploads 记录与解析结果 JSON（<id>.json，用于同
文件复用）保留不动。

安全校验：删之前先确认题库里确实还有这套题（沿 alias_of 找到源套题并计
数），题库里找不到题目的记录一律跳过，宁可不删。每次实际删除会在该条
uploads.summary 里写 originals_deleted_at 标记，并追加一行日志到
data/cleanup_originals.log。用 --dry-run 只报告不删。
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'data', 'quiz.db')
UPLOAD_DIR = os.path.join(BASE, 'data', 'uploads')
QUESTIONS_PATH = os.path.join(BASE, 'questions_full.json')
LOG_PATH = os.path.join(BASE, 'data', 'cleanup_originals.log')
RETENTION = '-2 months'


def log(msg):
    line = '%s %s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')
    except OSError:
        pass


def _canonical_set_id(sets_by_id, sid):
    seen = set()
    while sid and sid in sets_by_id and sets_by_id[sid].get('alias_of') and sid not in seen:
        seen.add(sid)
        sid = sets_by_id[sid]['alias_of']
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not os.path.exists(DB_PATH):
        log('no database, skip')
        return 0
    data = {'sets': [], 'questions': []}
    if os.path.exists(QUESTIONS_PATH):
        with open(QUESTIONS_PATH, encoding='utf-8') as fh:
            data = json.load(fh)
    sets_by_id = {s['id']: s for s in data.get('sets', [])}
    counts = {}
    for q in data.get('questions', []):
        counts[q.get('set')] = counts.get(q.get('set'), 0) + 1

    d = sqlite3.connect(DB_PATH)
    d.row_factory = sqlite3.Row
    rows = d.execute(
        "SELECT * FROM uploads WHERE status='done' AND set_id IS NOT NULL "
        "AND date(created_at) <= date('now', ?) ORDER BY id", (RETENTION,)).fetchall()
    acted = 0
    freed = 0
    for row in rows:
        root = _canonical_set_id(sets_by_id, row['set_id'])
        if not counts.get(root):
            log('skip upload %d: set %s not found in library' % (row['id'], row['set_id']))
            continue
        paths = [os.path.join(UPLOAD_DIR, '%d.pdf' % row['id']),
                 os.path.join(UPLOAD_DIR, '%d_ans.pdf' % row['id'])]
        existing = [p for p in paths if os.path.exists(p)]
        if not existing:
            continue
        size = sum(os.path.getsize(p) for p in existing)
        names = [os.path.basename(p) for p in existing]
        if args.dry_run:
            log('dry-run: would delete upload %d (%s, %.1f KB)'
                % (row['id'], ', '.join(names), size / 1024))
            continue
        for p in existing:
            os.remove(p)
        try:
            summary = json.loads(row['summary'] or '{}')
        except Exception:
            summary = {}
        summary['originals_deleted_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary['originals_deleted_files'] = names
        d.execute('UPDATE uploads SET summary=? WHERE id=?',
                  (json.dumps(summary, ensure_ascii=False), row['id']))
        acted += 1
        freed += size
        log('deleted originals of upload %d (%s, %.1f KB)'
            % (row['id'], ', '.join(names), size / 1024))
    if not args.dry_run:
        d.commit()
    log('done: %d uploads cleaned, %.1f KB freed%s'
        % (acted, freed / 1024, ' (dry-run)' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
