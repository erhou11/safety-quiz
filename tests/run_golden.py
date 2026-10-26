#!/usr/bin/env python3
"""金样本回归：三套出过事的原文件（up6/up17/up18）全流程重跑并比对指纹。

用法：python3 tests/run_golden.py [--write] [--fixtures DIR]
--write 把当前结果写为 tests/golden.json 基线（仅在确认差异合理时用）。
不带 --write 时与基线比对，任一项不一致退出码 1 并逐项报告。

流程与 app.py 上传管线同序：parse_pair → 行内选项拆分 → 坐标块救解析
→ 图/表提取 → 空解析收尾 → 成套体检。
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import upload_lib as U  # noqa: E402

SETS = ['6', '17', '18']


def run_one(fixtures, up, tmp):
    qs, warnings = U.parse_pair(
        U.extract_text(os.path.join(fixtures, up + '.pdf')),
        U.extract_text(os.path.join(fixtures, up + '_ans.pdf')))
    U.split_inline_options(qs)
    U.rescue_explanations(os.path.join(fixtures, up + '_ans.pdf'), qs)
    U.attach_pdf_images(os.path.join(fixtures, up + '.pdf'), qs, tmp,
                        'gq', 'images', 'question')
    U.attach_pdf_images(os.path.join(fixtures, up + '_ans.pdf'), qs, tmp,
                        'g', 'exp_images', 'answer')
    still = U.resolve_empty_explanations(qs)
    audit = U.audit_questions(qs)
    canon = [[q['stem'], [o['text'] for o in q['options']], q['answer'], q['type']]
             for q in qs]
    return {
        'total': len(qs),
        'fingerprint': hashlib.sha256(
            json.dumps(canon, ensure_ascii=False).encode()).hexdigest()[:16],
        'exp_table_seqs': [i + 1 for i, q in enumerate(qs) if q.get('exp_images')],
        'q_image_seqs': [i + 1 for i, q in enumerate(qs) if q.get('images')],
        'exp_nonempty': sum(1 for q in qs if (q.get('explanation') or '').strip()),
        'still_empty': still,
        'audit_blocking': audit['blocking'],
        'opt_counts_bad': {str(i + 1): len(q['options']) for i, q in enumerate(qs)
                           if not (2 <= len(q['options']) <= 6)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--fixtures', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'fixtures'))
    args = ap.parse_args()
    golden_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'golden.json')
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for up in SETS:
            results[up] = run_one(args.fixtures, up, tmp)
    if args.write:
        with open(golden_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print('基线已写入', golden_path)
        return 0
    with open(golden_path, encoding='utf-8') as f:
        golden = json.load(f)
    failed = 0
    for up in SETS:
        for key, want in golden[up].items():
            got = results[up].get(key)
            if got != want:
                failed += 1
                print('FAIL up%s.%s\n  基线: %r\n  现在: %r' % (up, key, want, got))
            else:
                print('ok   up%s.%s' % (up, key))
    print('金样本回归：%s' % ('全部通过' if not failed else '%d 项不一致' % failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
