#!/usr/bin/env python3
"""阶段4：私有套题满 1 年自动转公开 + 转公开前查重。

规则（product-rules.md 第四节）：
- 每套题私有期 1 年（created_at 起算），期满自动进公共总题库、暂时全部免费。
- 进总题库时自动查重：与公共库已有题重复的（指纹相同，口径同 dedup_check.fingerprint）
  不再重复显示——从转公开的套里剔除并重新编号；套内自重复也一并剔除。
- 若一套题全部与公共库重复，则不转公开（避免出现 0 题空套），留在私有并报告。

用法：
    python3 promote_public.py [--data questions_full.json] [--today YYYY-MM-DD] [--dry-run]
部署后由定时任务每周跑一次。写回为原子替换（tmp + replace），格式同主数据（indent=1）。
"""
import argparse, json, os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedup_check import fingerprint

PRIVATE_DAYS = 365


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='questions_full.json')
    ap.add_argument('--today', default=date.today().isoformat())
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.today)

    with open(a.data, encoding='utf-8') as f:
        d = json.load(f)
    sets = {s['id']: s for s in d['sets']}
    by_set = {}
    for q in d['questions']:
        by_set.setdefault(q['set'], []).append(q)

    public_fps = set()
    for s in d['sets']:
        if s.get('visibility', 'public') == 'public':
            for q in by_set.get(s['id'], []):
                public_fps.add(fingerprint(q))

    promoted, skipped_all_dup, not_due, no_date = [], [], 0, 0
    reference_sets = 0
    drop_ids = set()  # (set_id, id(q)) 待剔除题目的对象标识

    for s in d['sets']:
        if s.get('visibility', 'public') != 'private':
            continue
        if s.get('alias_of'):
            # 引用型套题不存题目，只是用户名下的入口；源套题按自己的入库日期
            # 独立转公开，引用套不重复转公开，避免公共库出现两套相同内容。
            reference_sets += 1
            continue
        ca = s.get('created_at')
        if not ca:
            no_date += 1
            continue
        try:
            age = (today - date.fromisoformat(ca)).days
        except ValueError:
            no_date += 1
            continue
        if age < PRIVATE_DAYS:
            not_due += 1
            continue
        qs = by_set.get(s['id'], [])
        seen = set(public_fps)
        kept, dropped, dropped_objs = [], 0, []
        for q in qs:
            fp = fingerprint(q)
            if fp in seen:
                dropped += 1
                dropped_objs.append(q)
            else:
                seen.add(fp)
                kept.append(q)
        if not kept:
            skipped_all_dup.append((s['id'], s.get('title', ''), len(qs)))
            continue
        drop_ids.update(id(q) for q in dropped_objs)
        for i, q in enumerate(kept, 1):
            q['n'] = i
        s['visibility'] = 'public'
        s['promoted_at'] = a.today
        public_fps = seen
        promoted.append((s['id'], s.get('title', ''), len(kept), dropped))

    if promoted:
        d['questions'] = [q for q in d['questions'] if id(q) not in drop_ids]
        if not a.dry_run:
            tmp = a.data + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, a.data)

    print('=== 转公开报告（%s%s）===' % (a.today, '，dry-run 未写回' if a.dry_run else ''))
    for sid, title, kept_n, dropped_n in promoted:
        print('  转公开 %s《%s》：保留 %d 题，剔除重复 %d 题' % (sid, title, kept_n, dropped_n))
    for sid, title, total in skipped_all_dup:
        print('  跳过 %s《%s》：%d 题全部与公共库重复，未转公开' % (sid, title, total))
    print('  未到期私有套 %d 个；缺 created_at 跳过 %d 个；引用型套题跳过 %d 个；本次共转公开 %d 套'
          % (not_due, no_date, reference_sets, len(promoted)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
