"""用户上传 PDF 的自动解析（文字层）：套用法规卷解析模式并泛化。

支持的版式（233 网校类标准卷）：
- 题面区与答案区由「答案解析 / 参考答案 / 答案与解析」一行分隔
- 题目以「N、」或「N.」开头，选项以「A. / A、」开头
- 答案区每题以「N、答案：ABC」开头，其后为解析
- 「单选题 / 多选题」标题行切换题型；最终题型以答案字母数校正（>1 为多选）

试题与答案分开两个文件时（2026-10-26 起支持双文件上传）：
- 试题 PDF 单独解析题目（可无答案分隔行）
- 答案 PDF 除上面的块格式外，还支持紧凑答案表：
  「1、A 2、AB 3、D」逐题式与「1—3 AAB」区间式

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
_RANGE_PAT = re.compile(r'(\d{1,3})\s*[-—~～]\s*(\d{1,3})\s*[：:.、]?\s*([A-E]{2,})')
_PAIR_PAT = re.compile(r'(\d{1,3})\s*[、.．:：]\s*([A-E]{1,6})(?![A-Za-z])')


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


def _parse_questions(qlines):
    """题面行 -> 题目列表（保留印刷题号 _pn，题型先按单选/多选标题行）。"""
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
    return qs


def _parse_answer_blocks(alines):
    """块格式答案区：「N、答案：ABC」开头、其后为解析 -> {题号: {answer, explanation}}"""
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
    return ans


def _parse_answers_loose(text):
    """独立答案文件的宽松解析：块格式优先（带解析），紧凑答案表补缺。

    紧凑式：区间「1—3 AAB」（题量须与字母数对齐）、逐题「1、A 2、AB」。
    """
    ans = {}
    flat = re.sub(r'\s+', ' ', text)
    for m in _RANGE_PAT.finditer(flat):
        a, b = int(m.group(1)), int(m.group(2))
        letters = re.findall(r'[A-E]', m.group(3))
        if 0 < b - a <= 200 and b - a + 1 == len(letters):
            for i, ch in enumerate(letters):
                ans.setdefault(a + i, {'answer': [ch], 'explanation': ''})
    for m in _PAIR_PAT.finditer(flat):
        n = int(m.group(1))
        if n not in ans:
            ans[n] = {'answer': re.findall(r'[A-E]', m.group(2)), 'explanation': ''}
    ans.update(_parse_answer_blocks(_clean(text.splitlines())))
    return ans


def _finish(qs, ans, warnings):
    """按题号/顺序把答案并入题目并过质量门（与原单文件逻辑一致）。"""
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


def parse_pair(q_text, a_text=None):
    """试题文本 + 可选的独立答案文本 -> (questions, warnings)。

    试题文本自带答案区时先用自带的，独立答案文件补缺（含解析）。
    """
    warnings = []
    lines = _clean(q_text.splitlines())
    split = next((i for i, l in enumerate(lines) if _SPLIT_PAT.match(l.strip())), None)
    if split is not None:
        qlines, embedded = lines[:split], lines[split + 1:]
    else:
        qlines, embedded = lines, []
        if not a_text:
            warnings.append('未找到答案解析分隔行')
    qs = _parse_questions(qlines)
    if not qs:
        return [], ['未解析出任何题目']
    ans = _parse_answer_blocks(embedded) if embedded else {}
    if a_text:
        for n, a in _parse_answers_loose(a_text).items():
            if n not in ans or not ans[n].get('answer'):
                ans[n] = a
            elif not ans[n].get('explanation') and a.get('explanation'):
                ans[n]['explanation'] = a['explanation']
    return _finish(qs, ans, warnings)


def parse_text(text):
    """单文件解析（题面+答案同在一个 PDF）：parse_pair 的兼容入口。"""
    return parse_pair(text, None)
