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

复核步骤（2026-10-26 用户定）：第一遍解析只要出现提示性错误（缺答案 /
选项数异常），不立即下结论——先用严格模式（题号顺序锚定 + 选项顺序锚定）
按原卷重解析一遍，取问题更少的结果为准；仍修不好的才保留警告转人工。
起因：某 106 题消防卷因页脚广告行与「B 」空格标号变体被拆成 110 题、
答案错位，复核模式可完整还原。

解析为空硬规定（2026-10-26 用户定）：任何上传只要有题解析为空，不许直接
下「原书没给解析」的结论，也不许静默成套——必须再拿原文件逐页核对：
答案册里的解析常是扫描图片表格，文字层提取不到，须扫描每道题条目区间
内的图片（宽 ≥150pt），把图/表裁出来挂到该题 exp_images；题面 PDF 里的
图/表同理挂到 images。图/表补上后解析仍为空的，转人工核对，不直接成套。
起因：破题系列 8 道题的解析是整张图片表格，曾被误判为「原书未给解析」，
另有 31 道题文字解析在、关键表格丢失。
"""
import os
import re

_SPLIT_PAT = re.compile(r'^(答案解析|参考答案|答案与解析|答案及解析)\s*$')
_SECT_PAT = re.compile(r'(单选|多选)题')
_Q_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*(.+)$')
_OPT_PAT = re.compile(r'^([A-E])\s*[.、．:：]\s*(.*)$')
_OPT_SPACE_PAT = re.compile(r'^([A-E])\s+(\S.*)$')
_ANS_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*答案\s*[:：]\s*([A-E][A-E，,、\s]*)\s*(.*)$')
_AD_PAT = re.compile(r'233网校|wx\.233\.com|全真机考|扫码|加微|联系电话|联系地址|合作微信|顶级课程|核心押题|睿和中心|0\d{2,3}-\d{7,8}')
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


def _parse_questions(qlines, strict=False):
    """题面行 -> 题目列表（保留印刷题号 _pn，题型先按单选/多选标题行）。

    strict=True 为复核模式：题号必须严格顺序递增才认作新题（防选项续行里
    的「2.50h」类数字被误当题号拆题），选项字母也须按 A→E 顺序出现。
    两种模式都允许「B 屋顶…」这种字母后空格的标号变体（仅限非首个选项，
    且必须是期待的下一个字母，避免题干续行以字母开头时误判）。
    """
    qs, cur, cur_opt, sect = [], None, None, 'single'
    next_n = None
    next_opt = 'A'

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
        if m and (not strict or next_n is None or int(m.group(1)) == next_n):
            flush()
            cur = {'_pn': int(m.group(1)), 'type': sect, 'cat': '', 'stem': m.group(2),
                   'options': [], 'images': [], 'exp_images': [],
                   'case_bg': '', 'case_images': []}
            next_n = int(m.group(1)) + 1
            next_opt = 'A'
            continue
        m = _OPT_PAT.match(l)
        if m and cur and (not strict or m.group(1) == next_opt):
            cur_opt = {'text': m.group(2).strip()}
            cur['options'].append(cur_opt)
            next_opt = chr(ord(m.group(1)) + 1)
            continue
        m = _OPT_SPACE_PAT.match(l)
        if m and cur and cur_opt is not None and m.group(1) == next_opt:
            cur_opt = {'text': m.group(2).strip()}
            cur['options'].append(cur_opt)
            next_opt = chr(ord(m.group(1)) + 1)
            continue
        if cur_opt is not None:
            cur_opt['text'] = (cur_opt['text'] + l).strip()
        elif cur:
            cur['stem'] += l
    flush()
    return qs


_ANS2_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*([A-E]{1,6})\s*(?:解析\s*[:：]\s*(.*))?$')
_EXP_HEAD_PAT = re.compile(r'^解析\s*[:：]\s*(.*)$')


def _parse_answer_blocks(alines):
    """块格式答案区 -> {题号: {answer, explanation}}。

    两种版式：
    - 「N、答案：ABC」开头（_ANS_PAT），其后为解析；
    - 紧凑版式（破题类答案册）：「N. ABC」单独成行，其后「解析：…」；
      「解析」可与题号同行（「208.D解析：…」），也可单独成行。
    """
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
        m = _ANS2_PAT.match(l)
        if m:
            cur_n = int(m.group(1))
            ans[cur_n] = {'answer': re.findall(r'[A-E]', m.group(2)),
                          'explanation': (m.group(3) or '').strip()}
            continue
        if cur_n is not None:
            em = _EXP_HEAD_PAT.match(l)
            if em:
                l = em.group(1).strip()
                if not l:
                    continue
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
    """按题号/顺序把答案并入题目并过质量门。返回 (题目, 警告, 问题题数)。"""
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
        return [], ['未解析出任何题目'], 999
    no_ans = [i + 1 for i, q in enumerate(out) if not q['answer']]
    bad_opt = [i + 1 for i, q in enumerate(out) if not (2 <= len(q['options']) <= 6)]
    if no_ans:
        warnings.append('第 %s 题缺答案' % ','.join(map(str, no_ans[:10])))
    if bad_opt:
        warnings.append('第 %s 题选项数异常' % ','.join(map(str, bad_opt[:10])))
    no_exp = [i + 1 for i, q in enumerate(out) if not (q.get('explanation') or '').strip()]
    if no_exp:
        warnings.append('第 %s 题解析为空（原卷可能为图片表格，需人工核对）'
                        % ','.join(map(str, no_exp[:10])))
    flagged = len(no_ans) + len(bad_opt)
    if len(no_ans) > max(1, len(out) // 5) or len(bad_opt) > max(1, len(out) // 5):
        return [], warnings + ['缺答案/选项异常比例过高，转人工'], flagged
    return out, warnings, flagged


def parse_pair(q_text, a_text=None):
    """试题文本 + 可选的独立答案文本 -> (questions, warnings)。

    试题文本自带答案区时先用自带的，独立答案文件补缺（含解析）。
    第一遍出现提示性错误（缺答案 / 选项数异常）时不下结论：用严格顺序
    锚定模式按原卷复核重解析，问题更少才采纳复核结果（见模块头注释）。
    """
    base = []
    lines = _clean(q_text.splitlines())
    split = next((i for i, l in enumerate(lines) if _SPLIT_PAT.match(l.strip())), None)
    if split is not None:
        qlines, embedded = lines[:split], lines[split + 1:]
    else:
        qlines, embedded = lines, []
        if not a_text:
            base.append('未找到答案解析分隔行')
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

    def fresh(parsed):
        return [dict(q, options=list(q['options'])) for q in parsed]

    out, warnings, flagged = _finish(fresh(qs), ans, list(base))
    flagged_warn = any('缺答案' in w or '选项数异常' in w for w in warnings)
    if flagged_warn or not out:
        qs2 = _parse_questions(qlines, strict=True)
        if qs2:
            out2, warnings2, flagged2 = _finish(fresh(qs2), ans, list(base))
            if out2 and (not out or flagged2 < flagged):
                out, warnings = out2, warnings2
    return out, warnings


def parse_text(text):
    """单文件解析（题面+答案同在一个 PDF）：parse_pair 的兼容入口。"""
    return parse_pair(text, None)


# ---------------------------------------------------------------------------
# 图/表提取（硬规定）：文字层之外，把原文件里的图片表格按题裁出来挂上。
# 答案 PDF 的图 -> exp_images，题面 PDF 的图 -> images。
# ---------------------------------------------------------------------------

_ANS_HEAD_PAT = re.compile(r'^(\d{1,3})\s*[、.．]\s*(?:答案\s*[:：]\s*)?([A-E]{1,6})(?![A-Za-z0-9])')
_IMG_MIN_W = 150      # 表格/示意图的最小宽度（pt）；页眉 logo、图标远小于此
_IMG_MIN_H = 25


def _page_lines(page):
    """一页的文字行 -> [(y0, x0, text)]，按阅读顺序（先纵后横）。"""
    out = []
    try:
        d = page.get_text('dict')
    except Exception:
        return out
    for block in d.get('blocks', []):
        if block.get('type') != 0:
            continue
        for line in block.get('lines', []):
            text = ''.join(s.get('text', '') for s in line.get('spans', [])).strip()
            if text:
                x0, y0 = line['bbox'][0], line['bbox'][1]
                out.append((y0, x0, text))
    out.sort()
    return out


def _find_entries(doc, kind):
    """按页扫描条目题头 -> [(印刷题号, 页序, y0)]（文档顺序）。

    kind='answer' 认答案条目头（「N、答案：A」或紧凑式「N. ABC」）；
    kind='question' 认题面题头（「N、…」）。
    题号须与上一个已认题头衔接（允许漏检 3 个以内自动再同步），解析正文里
    「1. A 选项…」这类行内编号因题号回跳会被丢弃，不会冒充条目头。
    """
    entries = []
    expected = None
    for pno in range(len(doc)):
        for y0, _x0, text in _page_lines(doc[pno]):
            if kind == 'answer':
                m = _ANS_HEAD_PAT.match(text)
            else:
                m = _Q_PAT.match(text)
            if not m:
                continue
            num = int(m.group(1))
            if expected is None or expected <= num <= expected + 3:
                entries.append((num, pno, y0))
                expected = num + 1
    return entries


def attach_pdf_images(pdf_path, qs, out_dir, prefix, field, kind):
    """把 pdf_path 中宽 ≥150pt 的图片裁出，按条目区间归属挂到 qs 的 field。

    prefix 为文件名前缀（如 'up17'），图片存 out_dir、URL 为 'imgup/<文件名>'。
    返回实际挂图数。条目头检出太少（不足题目数一半）时归属不可靠，宁可
    一张不挂、返回 0，留给「解析为空转人工」兜底，绝不乱挂。
    """
    if not pdf_path or not qs:
        return 0
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
    except Exception:
        return 0
    entries = _find_entries(doc, kind)
    if len(entries) < max(1, len(qs) // 2):
        doc.close()
        return 0
    # 印刷题号 -> 题目序号：优先用条目头在文档中的次序（第 k 个条目头即第 k 题），
    # 与 parse_pair 的输出次序一致；次序对不上时退回「题号-首题号+1」。
    by_order = {num: i + 1 for i, (num, _p, _y) in enumerate(entries)}
    first_num = entries[0][0]

    def seq_of(num):
        s = by_order.get(num)
        if s is not None and s <= len(qs):
            return s
        s = num - first_num + 1
        return s if 1 <= s <= len(qs) else None

    os.makedirs(out_dir, exist_ok=True)
    attached = 0
    seen = set()
    per_q = {}
    for pno in range(len(doc)):
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                continue
            for rect in rects:
                key = (pno, xref, round(rect.x0), round(rect.y0))
                if key in seen:
                    continue
                seen.add(key)
                if rect.width < _IMG_MIN_W or rect.height < _IMG_MIN_H:
                    continue
                if rect.width > pw * 0.92 and rect.height > ph * 0.85:
                    continue  # 整页扫描底图，不是题内图/表
                if rect.y0 < 45 and rect.height < 60:
                    continue  # 页眉 logo / 装饰
                owner = None
                for num, ep, ey in entries:
                    if ep < pno or (ep == pno and ey <= rect.y0 + 5):
                        owner = num
                    else:
                        break
                if owner is None:
                    continue
                seq = seq_of(owner)
                if seq is None:
                    continue
                clip = pymupdf.Rect(max(0, rect.x0 - 2), max(0, rect.y0 - 26),
                                    min(pw, rect.x1 + 2), min(ph, rect.y1 + 4))
                k = per_q.get(seq, 0) + 1
                per_q[seq] = k
                fname = '%s-%d-%d.png' % (prefix, seq, k)
                try:
                    pix = page.get_pixmap(clip=clip, dpi=200)
                    pix.save(os.path.join(out_dir, fname))
                except Exception:
                    continue
                qs[seq - 1].setdefault(field, [])
                url = 'imgup/' + fname
                if url not in qs[seq - 1][field]:
                    qs[seq - 1][field].append(url)
                    attached += 1
    doc.close()
    return attached


_INLINE_SEP_PAT = re.compile(r'([A-E])(?:[.、．:：]\s*|\s+)')
_ROW_SEP_PAT = re.compile(r'([A-E])(?=[\u4e00-\u9fff])')


def _try_split(stem, answer, pat, min_opt_len):
    """从题干里按 A→E 顺序标号链拆选项；不达标返回 None（宁可不拆）。"""
    marks = []
    idx = 0
    for letter in 'ABCDE':
        m = pat.search(stem, idx)
        if not m or m.group(1) != letter:
            break
        marks.append((m.start(), m.end()))
        idx = m.end()
    if len(marks) < 3 or marks[0][0] < 6:
        return None
    opts = []
    for i, (_s, e) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(stem)
        opts.append(stem[e:end].strip())
    if any(len(o) < min_opt_len for o in opts):
        return None
    if answer and any(ord(a) - 65 >= len(opts) for a in answer):
        return None
    new_stem = stem[:marks[0][0]].strip()
    if len(new_stem) < 6:
        return None
    return new_stem, [{'text': o} for o in opts]


def split_inline_options(qs):
    """0 选项题的结构修复：选项被行内排版/表格行吞进题干时拆回来。

    两种形态：标准行内式（「A 未设…B.仅设…」，标号带点或空格）与表格行式
    （每行以字母起头、后接中文）。拆不达标（<3 项、某项过短、答案越界）
    一律不动，留给成套体检拦下转人工。返回修复题数。
    """
    fixed = 0
    for q in qs:
        if q.get('type') == 'essay' or len(q.get('options') or []) >= 1:
            continue
        stem = (q.get('stem') or '').strip()
        got = _try_split(stem, q.get('answer'), _INLINE_SEP_PAT, 2) or \
            _try_split(stem, q.get('answer'), _ROW_SEP_PAT, 6)
        if got:
            q['stem'], q['options'] = got
            fixed += 1
    return fixed


def rescue_explanations(pdf_path, qs):
    """第二通道救解析：坐标块按条目区间再提取一遍文字，专补空解析。

    行式解析在多栏排版/行序错乱时会把解析行挂错题或丢掉；这里用答案册
    条目头的位置坐标圈定每道题的版面区间，只取区间内文字块拼回解析。
    只填原本为空的题，绝不覆盖已解析出的内容。返回补回题数。
    """
    empties = {i for i, q in enumerate(qs)
               if not (q.get('explanation') or '').strip()}
    if not pdf_path or not empties:
        return 0
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
    except Exception:
        return 0
    entries = _find_entries(doc, 'answer')
    if len(entries) < max(1, len(qs) // 2):
        doc.close()
        return 0
    filled = 0
    for k, (num, pno, y0) in enumerate(entries):
        seq = k + 1
        if seq > len(qs):
            seq = num - entries[0][0] + 1
        if seq - 1 not in empties:
            continue
        nxt = entries[k + 1] if k + 1 < len(entries) else None
        end_p = nxt[1] if nxt else len(doc) - 1
        lines = []
        for p in range(pno, end_p + 1):
            blocks = sorted(doc[p].get_text('blocks'), key=lambda b: (b[1], b[0]))
            for b in blocks:
                if b[4] is None:
                    continue
                if p == pno and b[1] < y0 - 8:
                    continue
                if nxt and p == nxt[1] and b[1] >= nxt[2] - 2:
                    continue
                lines.extend(b[4].splitlines())
        text = ''.join(l.strip() for l in _clean(lines))
        text = re.sub(r'^\d{1,3}\s*[、.．]\s*(?:答案\s*[:：]\s*)?[A-E]{1,6}\s*', '', text)
        text = re.sub(r'^解析\s*[:：]\s*', '', text)
        if len(text) >= 6:
            qs[seq - 1]['explanation'] = text
            filled += 1
    doc.close()
    return filled


_FIG_REF_PAT = re.compile(r'如图|下图|下表|见表|图示|附图|所示')


def audit_questions(qs):
    """成套体检：返回 {'blocking': {问题: [题号]}, 'warnings': {...}}。

    blocking 是带病成套的硬伤（缺答案 / 选项数异常 / 答案字母越界 /
    解析为空且无图 / 整题重复 / 题干过短），调用方必须整套转人工；
    warnings 是可疑但不拦的项（正文提到图/表却没挂图、解析过短、
    选项过长疑似并行）。
    """
    blocking, warns = {}, {}

    def add(d, code, i):
        d.setdefault(code, []).append(i)

    seen = {}
    for i, q in enumerate(qs, 1):
        ans = q.get('answer') or []
        opts = q.get('options') or []
        stem = (q.get('stem') or '').strip()
        exp = (q.get('explanation') or '').strip()
        if q.get('type') != 'essay':
            if not ans:
                add(blocking, 'no_answer', i)
            if not (2 <= len(opts) <= 6):
                add(blocking, 'bad_options', i)
            elif ans and any(ord(a) - 65 >= len(opts) for a in ans):
                add(blocking, 'answer_out_of_range', i)
        if not exp and not q.get('exp_images'):
            add(blocking, 'empty_explanation', i)
        if len(stem) < 6:
            add(blocking, 'stem_too_short', i)
        key = (stem, tuple(o.get('text', '') for o in opts), tuple(ans))
        if stem and key in seen:
            add(blocking, 'dup_question', i)
        seen[key] = i
        if _FIG_REF_PAT.search(stem) and not q.get('images'):
            add(warns, 'stem_fig_ref_no_image', i)
        if _FIG_REF_PAT.search(exp) and not q.get('exp_images') and len(exp) < 120:
            add(warns, 'exp_fig_ref_no_image', i)
        if 0 < len(exp) <= 2:
            add(warns, 'exp_too_short', i)
        if any(len(o.get('text', '')) > 300 for o in opts):
            add(warns, 'option_too_long', i)
    return {'blocking': blocking, 'warnings': warns}


def resolve_empty_explanations(qs):
    """解析为空硬规定的收尾：图/表已挂上的，解析填引导语；仍为空的列出。

    返回 still_empty（1 起序号列表）——这些题已按原文件核过文字与图/表
    仍无解析，调用方必须转人工核对，不得直接成套。
    """
    still = []
    for i, q in enumerate(qs, 1):
        if (q.get('explanation') or '').strip():
            continue
        if q.get('exp_images'):
            q['explanation'] = '原书本题解析为图/表，文字层无内容，图/表已随题附上（见下图）。'
        else:
            still.append(i)
    return still
