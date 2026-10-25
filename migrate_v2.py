#!/usr/bin/env python3
"""题目数据 v2 迁移：给 questions_full.json 加三大类字段（阶段1 数据层改造）。

- 顶层加 categories（6 大考试类别，顺序按用户 2026-10-25 所定）
- subjects 每项加 category（现有 10 科目全归中级注册安全工程师 zj-anquan）
- sets 每项加 category / owner_email / created_at / visibility=private
  （存量 29 套归站长，私有期 1 年自 created_at 起算）

用法：
  python3 migrate_v2.py --owner-email xxx@yyy --date 2026-10-26 \
      --src questions_full.json --dst questions_full_v2.json
不覆盖源文件；输出后自检套数/题量/引用完整性。
"""
import argparse, json, sys
from datetime import date

CATEGORIES = [
    {'id': 'yj-jianzao', 'title': '一级建造师', 'desc': '一级建造师执业资格考试'},
    {'id': 'ej-jianzao', 'title': '二级建造师', 'desc': '二级建造师执业资格考试'},
    {'id': 'yj-xiaofang', 'title': '一级注册消防工程师', 'desc': '一级注册消防工程师资格考试'},
    {'id': 'ej-anquan', 'title': '二级注册安全工程师', 'desc': '二级注册安全工程师职业资格考试'},
    {'id': 'zj-anquan', 'title': '中级注册安全工程师', 'desc': '中级注册安全工程师职业资格考试'},
    {'id': 'cj-anquan', 'title': '初级注册安全工程师', 'desc': '初级注册安全工程师职业资格考试'},
]
LEGACY_CATEGORY = 'zj-anquan'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--owner-email', required=True, help='存量套题归属的站长账号邮箱')
    ap.add_argument('--date', default=date.today().isoformat(), help='入库日期（私有期起算日）YYYY-MM-DD')
    ap.add_argument('--src', default='questions_full.json')
    ap.add_argument('--dst', default='questions_full_v2.json')
    a = ap.parse_args()

    with open(a.src, encoding='utf-8') as f:
        d = json.load(f)
    sets, subjects, questions = d['sets'], d.get('subjects', []), d['questions']

    d['categories'] = CATEGORIES
    for s in subjects:
        s['category'] = LEGACY_CATEGORY
    for s in sets:
        s['category'] = LEGACY_CATEGORY
        s['owner_email'] = a.owner_email
        s['created_at'] = a.date
        s['visibility'] = 'private'

    # 自检
    set_ids = {s['id'] for s in sets}
    assert len(set_ids) == len(sets), 'set id 重复'
    bad = [q for q in questions if q['set'] not in set_ids]
    assert not bad, '有题目引用了不存在的套题: %s' % bad[:3]
    assert all(s.get('category') and s.get('owner_email') and s.get('created_at')
               and s.get('visibility') for s in sets), '套题新字段不全'
    assert all(s.get('category') for s in subjects), '科目 category 不全'

    with open(a.dst, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print('OK: %d 套 / %d 题 / %d 科目 / %d 类别 -> %s（owner=%s, 起算 %s）'
          % (len(sets), len(questions), len(subjects), len(CATEGORIES),
             a.dst, a.owner_email, a.date))


if __name__ == '__main__':
    sys.exit(main())
