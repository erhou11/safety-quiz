"""用户上传 PDF 的自动解析（文字层）：套用法规卷解析模式并泛化。

支持的版式（233 网校类标准卷）：
- 题面区与答案区由「答案解析 / 参考答案 / 答案与解析」一行分隔
- 题目以「N、」或「N.」开头，选项以「A. / A、」开头
- 答案区每题以「N、答案：ABC」开头，其后为解析
- 「单选题 / 多选题」标题行切换题型；最终题型以答案字母数校正（>1 为多选）

解析质量不达标（无文字层、找不到题、缺答案比例过高）时返回空并给出原因，
由调用方转人工审核（need_review），不硬凑。
"""
import re

_SPLIT_PAT = re.compile(r'^(答案解析|参考答案|答案与解析|答案及解析)\s*$')
_SECT_PAT = re.compile(r'(单选|多选)题')
_Q_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*(.+)$')
_OPT_PAT = re.compile(r'^([A-E])\s*[.、．:：]\s*(.*)$')
_ANS_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*答案\s*[:：]\s*([A-E][A-E，,、\s]*)\s*(.*)$')
_AD_PAT = re.compile(r'233网校|wx\.233\.com|全真机考|扫码|加微')


def extract_text(pdf_path):
    """提取 PDF 文字层全文；失败返回空串。"""
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        return '\n'.join(parts)
    except Exception:
        return ''


def _clean(lines):
    return [l.rstrip() for l in lines if l.strip() and not _AD_PAT.search(l)]


def parse_text(text):
    """返回 (questions, warnings)。questions 元素与题库 JSON 同构（set/n 由调用方定）。"""
    warnings = []
    lines = _clean(text.splitlines())
    split = next((i for i, l in enumerate(lines) if _SPLIT_PAT.match(l.strip())), None)
    if split is None:
        return [], ['未找到答案解析分隔行']
    qlines, alines = lines[:split], lines[split + 1:]

    qs, cur, cur_opt, sect = [], None, None, 'single'

    def flush():
        nonlocal cur, cur_opt
        if cur:
            cur['stem'] = cur['stem'].strip()
            qs.append(cur)
        cur, cur_opt = None, None

    for raw in qlines:
        l = raw.strip()
        m = _SECT_PAT.search(l)
        if m and len(l) <= 30:
            sect = 'multi' if m.group(1) == '多选' else 'single'
            continue
        m = _Q_PAT.match(l)
        if m:
            flush()
            cur = {'_pn': int(m.group(1)), 'type': sect, 'cat': '', 'stem': m.group(2),
                   'options': [], 'images': [], 'exp_images': [],
                   'case_bg': '', 'case_images': []}
            continue
        m = _OPT_PAT.match(l)
        if m and cur:
            cur_opt = {'text': m.group(2).strip()}
            cur['options'].append(cur_opt)
            continue
        if cur_opt is not None:
            cur_opt['text'] = (cur_opt['text'] + l).strip()
        elif cur:
            cur['stem'] += l
    flush()

    ans = {}
    cur_n = None
    for raw in alines:
        l = raw.strip()
        m = _ANS_PAT.match(l)
        if m:
            cur_n = int(m.group(1))
            ans[cur_n] = {'answer': re.findall(r'[A-E]', m.group(2)),
                          'explanation': m.group(3).strip()}
            continue
        if cur_n is not None:
            ans[cur_n]['explanation'] = (ans[cur_n]['explanation'] + l).strip()

    # 答案匹配：题面印刷题号全卷唯一时按题号对，否则按顺序对
    pns = [q['_pn'] for q in qs]
    by_number = len(set(pns)) == len(pns)
    out = []
    for i, q in enumerate(qs, 1):
        a = ans.get(q['_pn'] if by_number else i, {})
        answer = a.get('answer', [])
        q['answer'] = answer
        q['explanation'] = a.get('explanation', '')
        if len(answer) > 1:
            q['type'] = 'multi'
        del q['_pn']
        out.append(q)

    if not out:
        return [], ['未解析出任何题目']
    no_ans = [i + 1 for i, q in enumerate(out) if not q['answer']]
    bad_opt = [i + 1 for i, q in enumerate(out) if not (2 <= len(q['options']) <= 6)]
    if no_ans:
        warnings.append('第 %s 题缺答案' % ','.join(map(str, no_ans[:10])))
    if bad_opt:
        warnings.append('第 %s 题选项数异常' % ','.join(map(str, bad_opt[:10])))
    if len(no_ans) > max(1, len(out) // 5) or len(bad_opt) > max(1, len(out) // 5):
        return [], warnings + ['缺答案/选项异常比例过高，转人工']
    return out, warnings
