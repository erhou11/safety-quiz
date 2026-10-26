const $ = s => document.querySelector(s);
const LETTERS = 'ABCDEFGH';
let mode = 'seq', order = [], pos = 0, roundMap = {}, t0 = 0, picked = [];
let favSet = new Set();
let curSet = localStorage.getItem('quiz_set') || 's1';
let curSubject = localStorage.getItem('quiz_subject') || 'jishu';
// 答题状态写进 URL hash（#quiz=seq），刷新/标签页恢复时 URL 不变，可直接回到答题页
function setQuizHash(m) { try { history.replaceState(null, '', '#quiz=' + m); } catch (e) {} }
function clearQuizHash() { try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
let setsMeta = [];
let subjectsMeta = [];
let categoriesMeta = [];
let categorySubjectsMap = {};
let curCategory = localStorage.getItem('quiz_category') || 'zj-anquan';

function categorySubjects() {
  if (!categoriesMeta.length) return subjectsMeta;
  return subjectsMeta.filter(s => (s.category || 'zj-anquan') === curCategory);
}

function visibleCategories() {
  // 只显示「当前用户能看到的套题」所在的类别：没题的类别名称不出现，
  // 哪个类别上传了题库，哪个类别的名称才显示出来（2026-10-26 用户要求）
  const catOfSubject = {};
  subjectsMeta.forEach(s => { catOfSubject[s.id] = s.category || 'zj-anquan'; });
  const have = new Set(setsMeta.map(s => s.category || catOfSubject[s.subject] || 'zj-anquan'));
  return categoriesMeta.filter(c => have.has(c.id));
}

function renderCategoryTabs() {
  const box = $('#category-tabs'); box.innerHTML = '';
  const cats = visibleCategories();
  box.classList.toggle('hidden', cats.length <= 1);
  cats.forEach(c => {
    const b = document.createElement('button');
    b.className = 'subj-tab' + (c.id === curCategory ? ' active' : '');
    b.textContent = c.title;
    b.onclick = () => {
      if (curCategory === c.id) return;
      curCategory = c.id;
      localStorage.setItem('quiz_category', curCategory);
      curSet = null;
      renderPractice();
    };
    box.appendChild(b);
  });
}

function show(id) {
  document.querySelectorAll('.screen').forEach(e => e.classList.remove('active'));
  $('#screen-' + id).classList.add('active');
  window.scrollTo(0, 0);
  // 把当前页面记进 URL hash，刷新后回到原页面，不再一律回首页；
  // 答题页的 hash 是 #quiz=模式，由 setQuizHash 维护，这里不覆盖
  try {
    if (id === 'quiz') { if (!/#quiz=/.test(location.hash)) setQuizHash(mode); }
    else if (id === 'home') history.replaceState(null, '', location.pathname + location.search);
    else history.replaceState(null, '', '#page=' + id);
  } catch (e) {}
}
async function api(p, o = {}) {
  const r = await fetch('/api/' + p, Object.assign({ headers: { 'Content-Type': 'application/json' } }, o));
  if (!r.ok) throw new Error('api ' + r.status);
  return r.json();
}
const withSet = (p, body) => {
  if (body) { const b = JSON.parse(body); b.set = curSet; return JSON.stringify(b); }
  return p + (p.includes('?') ? '&' : '?') + 'set=' + curSet;
};

function categorySets() {
  // 首页套题改为平铺：当前类别下全部可见套题，按科目顺序再按原顺序排
  const catOfSubject = {};
  subjectsMeta.forEach(s => { catOfSubject[s.id] = s.category || 'zj-anquan'; });
  const subjIdx = {};
  subjectsMeta.forEach((s, i) => { subjIdx[s.id] = i; });
  return setsMeta
    .filter(s => (s.category || catOfSubject[s.subject] || 'zj-anquan') === curCategory)
    .slice()
    .sort((a, b) => (subjIdx[a.subject] ?? 99) - (subjIdx[b.subject] ?? 99));
}

function subjectSets() {
  return setsMeta.filter(s => s.subject === curSubject);
}

function subjectsWithSets() {
  // 科目选择只列「有可见套题」的科目，没题的科目不出现（与类别显隐同一规矩）
  const have = new Set(categorySets().map(s => s.subject));
  return categorySubjects().filter(s => have.has(s.id));
}

function renderSubjectTabs() {
  const box = $('#subject-tabs'); box.innerHTML = '';
  subjectsWithSets().forEach(s => {
    const b = document.createElement('button');
    b.className = 'subj-tab' + (s.id === curSubject ? ' active' : '');
    b.textContent = s.title;
    b.onclick = () => {
      if (curSubject === s.id) return;
      curSubject = s.id;
      localStorage.setItem('quiz_subject', curSubject);
      const ss = subjectSets();
      curSet = ss.length ? ss[0].id : null;
      localStorage.setItem('quiz_set', curSet || '');
      renderPractice();
    };
    box.appendChild(b);
  });
}

// 套题自定义排序 (localStorage, 按科目存)
function getSetOrder() {
  try {
    const o = JSON.parse(localStorage.getItem('quiz_set_order_' + curSubject) || '[]');
    return Array.isArray(o) ? o : [];
  } catch (e) { return []; }
}
function saveSetOrder(ids) {
  localStorage.setItem('quiz_set_order_' + curSubject, JSON.stringify(ids));
}
function orderedSets() {
  const ss = subjectSets();
  const order = getSetOrder();
  if (!order.length) return ss;
  const pos = {};
  order.forEach((id, i) => pos[id] = i);
  return ss.slice().sort((a, b) => {
    const pa = (a.id in pos) ? pos[a.id] : 1e9;
    const pb = (b.id in pos) ? pos[b.id] : 1e9;
    return pa - pb;
  });
}

function renderSetTabs() {
  const box = $('#set-tabs'); box.innerHTML = '';
  orderedSets().forEach(s => {
    const b = document.createElement('button');
    b.className = 'set-tab' + (s.id === curSet ? ' active' : '');
    b.dataset.setId = s.id;
    b.innerHTML = '<div class="st-k"></div><div class="st-t"></div><div class="st-c"></div><div class="st-s"></div>';
    b.querySelector('.st-k').textContent = s.kicker;
    b.querySelector('.st-t').textContent = s.title;
    b.querySelector('.st-c').textContent = s.total + ' 题';
    const stEl = b.querySelector('.st-s');
    const done = s.answered || 0;
    if (done >= s.total && s.total > 0) {
      stEl.textContent = '已做'; stEl.classList.add('done');
      const redo = document.createElement('span');
      redo.className = 'st-redo'; redo.textContent = '重做';
      redo.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm('确定重做《' + s.title + '》？将清除本套全部作答记录。')) return;
        await api('reset_set?set=' + s.id, { method: 'POST' });
        renderPractice();
      };
      b.appendChild(redo);
    }
    else if (done > 0) { stEl.textContent = '未做完'; stEl.classList.add('doing'); }
    else { stEl.textContent = '未做'; stEl.classList.add('todo'); }
    b.onclick = () => {
      curSet = s.id;
      localStorage.setItem('quiz_set', curSet);
      show('set'); renderSetPage();
    };
    box.appendChild(b);
  });
  initSetDrag(box);
}

// 套题拖动排序: 长按卡片 450ms 或直接拖 ⋮⋮ 手柄, 触屏/鼠标通用
function initSetDrag(box) {
  box.querySelectorAll('.set-tab').forEach(card => {
    card.addEventListener('pointerdown', e => {
      // 重做按钮不触发拖动
      if (e.target.closest('.st-redo')) return;
      const startX = e.clientX, startY = e.clientY;
      let dragging = false, placeholder = null, offsetY = 0, timer = null;

      const startDrag = () => {
        dragging = true;
        const rect = card.getBoundingClientRect();
        offsetY = startY - rect.top;
        placeholder = document.createElement('div');
        placeholder.className = 'drag-placeholder';
        placeholder.style.height = rect.height + 'px';
        box.insertBefore(placeholder, card);
        card.classList.add('dragging');
        card.style.position = 'fixed';
        card.style.left = rect.left + 'px';
        card.style.top = rect.top + 'px';
        card.style.width = rect.width + 'px';
        card.style.margin = '0';
        card.style.zIndex = '100';
        card.style.pointerEvents = 'none';
        // 拖动中阻止页面滚动
        document.addEventListener('touchmove', preventScroll, { passive: false });
      };
      const preventScroll = ev => ev.preventDefault();

      const move = ev => {
        if (!dragging) {
          // 未进入拖动: 移动超阈值视为滚动, 取消长按
          if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 12) {
            cancel();
          }
          return;
        }
        card.style.top = (ev.clientY - offsetY) + 'px';
        const tabs = [...box.querySelectorAll('.set-tab:not(.dragging)')];
        let target = null;
        for (const t of tabs) {
          const r = t.getBoundingClientRect();
          if (ev.clientY < r.top + r.height / 2) { target = t; break; }
        }
        if (target) box.insertBefore(placeholder, target);
        else box.appendChild(placeholder);
      };

      const up = () => {
        cancel();
        if (dragging && placeholder) {
          box.insertBefore(card, placeholder);
          placeholder.remove();
          card.classList.remove('dragging');
          card.style.cssText = '';
          document.removeEventListener('touchmove', preventScroll);
          const ids = [...box.querySelectorAll('.set-tab')].map(el => el.dataset.setId);
          saveSetOrder(ids);
          // 拖动后屏蔽一次点击, 防止误触选中
          const block = ev => { ev.stopPropagation(); ev.preventDefault(); };
          box.addEventListener('click', block, true);
          setTimeout(() => box.removeEventListener('click', block, true), 300);
        }
        dragging = false;
      };

      const cancel = () => {
        if (timer) { clearTimeout(timer); timer = null; }
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', up);
      };

      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', up);
      timer = setTimeout(startDrag, 450);
    });
  });
}

async function loadHome() {
  loadMe().catch(() => {});
  const meta = await api('meta');
  categoriesMeta = meta.categories || [];
  categorySubjectsMap = meta.category_subjects || {};
  subjectsMeta = meta.subjects || [];
  setsMeta = meta.sets;
  const vcats = visibleCategories();
  if (vcats.length && !vcats.some(c => c.id === curCategory))
    curCategory = vcats.some(c => c.id === 'zj-anquan') ? 'zj-anquan' : vcats[0].id;
  updateStartBtn();
}

function updateStartBtn() {
  const sub = $('#start-sub');
  if (!sub) return;
  if (setsMeta.length) {
    const total = setsMeta.reduce((a, s) => a + (s.total || 0), 0);
    sub.textContent = '你的题库共 ' + setsMeta.length + ' 套 · ' + total + ' 题';
  } else {
    sub.textContent = '登录后开启你的专属题库';
  }
}

async function renderPractice() {
  // 刷题页只做选择：先选科目（只列有题的），再选套题；详情与模式在套题页
  renderCategoryTabs();
  const subs = subjectsWithSets();
  if (!subs.some(s => s.id === curSubject)) curSubject = subs.length ? subs[0].id : null;
  if (curSubject) localStorage.setItem('quiz_subject', curSubject);
  renderSubjectTabs();
  const ss = subjectSets();
  if (!ss.some(s => s.id === curSet)) curSet = ss.length ? ss[0].id : null;
  localStorage.setItem('quiz_set', curSet || '');
  if (curSet) curSubject = setsMeta.find(x => x.id === curSet)?.subject || curSubject;
  renderSetTabs();
}

async function renderSetPage() {
  const s = setsMeta.find(x => x.id === curSet);
  if (!s) { show('practice'); renderPractice(); return; }
  curSubject = s.subject;
  $('#set-title').textContent = s.title;
  $('#set-desc').textContent = s.desc;
  $('#st-total').textContent = s.total;
  $('#st-single').textContent = s.single;
  $('#st-multi').textContent = s.multi;
  $('#st-essay').textContent = s.essay || 0;
  $('#st-essay-wrap').classList.toggle('hidden', !(s.essay > 0));
  const st = await api(withSet('state'));
  $('#seq-hint').textContent = st.seq_pos > 0 ? `上次做到第 ${st.seq_pos + 1} 题，点击继续` : '从第 1 题开始，完整练完一套';
  $('#rand-hint').textContent = st.rand_pos > 0 ? `上次做到第 ${st.rand_pos + 1} 题，点击继续` : '打乱顺序，随机抽题练习';
  $('#wrong-hint').textContent = st.wrong_count > 0 ? `共 ${st.wrong_count} 道错题，点击重练` : '答错的题目会自动收录在这里';
  $('#btn-seq').onclick = () => startQuiz('seq', st.seq_pos);
  $('#btn-rand').onclick = () => startQuiz('rand', st.rand_pos);
  const bw = $('#btn-wrong');
  bw.classList.toggle('disabled', st.wrong_count === 0);
  bw.onclick = () => { if (st.wrong_count > 0) startQuiz('wrong', 0); };
  $('#fav-hint').textContent = st.fav_count > 0 ? `共 ${st.fav_count} 道收藏，点击重练` : '点题目旁的 ★ 收藏题目';
  const bf = $('#btn-fav');
  bf.classList.toggle('disabled', st.fav_count === 0);
  bf.onclick = () => { if (st.fav_count > 0) startQuiz('fav', 0); };
  const be = $('#btn-essay');
  be.classList.toggle('hidden', !(s.essay > 0));
  $('#essay-hint').textContent = s.essay > 0 ? `共 ${s.essay} 道简答题` : '';
  be.onclick = () => { if (s.essay > 0) startQuiz('essay', 0); };
  initCardDrag(document.querySelector('.cards'));
}

// 练习卡片拖动排序: 长按 450ms, 触屏/鼠标通用, 顺序存 localStorage
function initCardDrag(box) {
  if (!box || box.dataset.dragInit) return;
  box.dataset.dragInit = '1';
  // 恢复保存的顺序
  try {
    const saved = JSON.parse(localStorage.getItem('quiz_card_order') || '[]');
    if (saved.length) {
      const map = {};
      box.querySelectorAll('.card').forEach(c => { map[c.id] = c; });
      saved.forEach(id => { if (map[id]) box.appendChild(map[id]); });
    }
  } catch (e) {}
  box.querySelectorAll('.card').forEach(card => {
    card.addEventListener('pointerdown', e => {
      const startX = e.clientX, startY = e.clientY;
      let dragging = false, placeholder = null, offsetY = 0, timer = null;
      const preventScroll = ev => ev.preventDefault();
      const startDrag = () => {
        dragging = true;
        const rect = card.getBoundingClientRect();
        offsetY = startY - rect.top;
        placeholder = document.createElement('div');
        placeholder.className = 'drag-placeholder';
        placeholder.style.height = rect.height + 'px';
        box.insertBefore(placeholder, card);
        card.classList.add('dragging');
        card.style.position = 'fixed';
        card.style.left = rect.left + 'px';
        card.style.top = rect.top + 'px';
        card.style.width = rect.width + 'px';
        card.style.margin = '0';
        card.style.zIndex = '100';
        card.style.pointerEvents = 'none';
        document.addEventListener('touchmove', preventScroll, { passive: false });
      };
      const move = ev => {
        if (!dragging) {
          if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 12) cancel();
          return;
        }
        card.style.top = (ev.clientY - offsetY) + 'px';
        const cards = [...box.querySelectorAll('.card:not(.dragging)')];
        let target = null;
        for (const t of cards) {
          const r = t.getBoundingClientRect();
          if (ev.clientY < r.top + r.height / 2) { target = t; break; }
        }
        if (target) box.insertBefore(placeholder, target);
        else box.appendChild(placeholder);
      };
      const up = () => {
        cancel();
        if (dragging && placeholder) {
          box.insertBefore(card, placeholder);
          placeholder.remove();
          card.classList.remove('dragging');
          card.style.cssText = '';
          document.removeEventListener('touchmove', preventScroll);
          const ids = [...box.querySelectorAll('.card')].map(el => el.id);
          try { localStorage.setItem('quiz_card_order', JSON.stringify(ids)); } catch (e) {}
          const block = ev => { ev.stopPropagation(); ev.preventDefault(); };
          box.addEventListener('click', block, true);
          setTimeout(() => box.removeEventListener('click', block, true), 300);
        }
        dragging = false;
      };
      const cancel = () => {
        if (timer) { clearTimeout(timer); timer = null; }
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', up);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', up);
      timer = setTimeout(startDrag, 450);
    });
  });
}

async function startQuiz(m, resumePos) {
  mode = m; t0 = Date.now(); picked = [];
  order = await api(withSet('questions?mode=' + m));
  if (!order.length) return;
  roundMap = await api(withSet('round'));
  favSet = new Set(await api(withSet('favorites')).catch(() => []));
  pos = Math.min(resumePos || 0, order.length - 1);
  setQuizHash(m);
  show('quiz');
  renderQ();
}

async function renderQ() {
  const q = order[pos];
  $('#q-count').textContent = (pos + 1) + '/' + order.length;
  $('#q-prog-fill').style.width = ((pos + 1) / order.length * 100) + '%';
  $('#q-cat').textContent = '分类 ' + q.cat;
  $('#q-type').textContent = q.type === 'single' ? '单选题' : q.type === 'multi' ? '多选题' : '简答题';
  const favBtn = $('#q-fav');
  favBtn.classList.toggle('on', favSet.has(q.n));
  favBtn.onclick = async () => {
    const r = await api('favorite', { method: 'POST', body: withSet(null, JSON.stringify({ n: q.n })) });
    if (r.faved) favSet.add(q.n); else favSet.delete(q.n);
    favBtn.classList.toggle('on', r.faved);
  };
  const qc = $('#q-case');
  if (q.case_bg && q.type !== 'essay') {
    qc.classList.remove('hidden'); qc.innerHTML = '';
    const t = document.createElement('div'); t.className = 'qcase-title'; t.textContent = '案例背景';
    const b = document.createElement('div'); b.className = 'qcase-body'; b.textContent = q.case_bg;
    qc.append(t, b);
    (q.case_images || []).forEach(u => { const i = document.createElement('img'); i.src = '/' + u; i.loading = 'lazy'; qc.appendChild(i); });
  } else { qc.classList.add('hidden'); qc.innerHTML = ''; }
  $('#q-stem').textContent = q.n + '．' + q.stem.replace(/^\s*\d+\s*[.．、]\s*/, '');
  const im = $('#q-imgs'); im.innerHTML = '';
  q.images.forEach(u => { const i = document.createElement('img'); i.src = '/' + u; i.loading = 'lazy'; im.appendChild(i); });
  const box = $('#q-opts'); box.innerHTML = '';
  const prev = roundMap[q.n];
  if (q.type === 'essay') {
    if (!prev) {
      // 提示按钮
      if (q.hints && q.hints.length) {
        const hb = document.createElement('button');
        hb.className = 'essay-btn hint-btn'; hb.textContent = '💡 提示';
        const hintBox = document.createElement('div');
        hintBox.className = 'hint-box hidden';
        hintBox.innerHTML = q.hints.map((h, i) => `<span class="hint-tag">${i + 1}. ${h}</span>`).join('');
        hb.onclick = () => hintBox.classList.toggle('hidden');
        box.appendChild(hb);
        box.appendChild(hintBox);
      }
      const b = document.createElement('button');
      b.className = 'essay-btn'; b.textContent = '查看参考答案';
      b.onclick = () => submit([]);
      box.appendChild(b);
    }
  } else q.options.forEach((o, i) => {
    const L = LETTERS[i];
    const b = document.createElement('button');
    b.className = 'opt'; b.dataset.letter = L;
    if (o.img) { const im2 = document.createElement('img'); im2.src = '/' + o.img; im2.loading = 'lazy'; b.appendChild(im2); }
    else {
      const s1 = document.createElement('span'); s1.className = 'ol'; s1.textContent = L;
      const s2 = document.createElement('span'); s2.className = 'ot'; s2.textContent = o.text;
      b.appendChild(s1); b.appendChild(s2);
    }
    if (!prev) b.onclick = () => onPick(L);
    box.appendChild(b);
  });
  $('#q-submit').classList.toggle('hidden', q.type !== 'multi' || !!prev);
  $('#q-prev').disabled = pos === 0;
  $('#q-next').textContent = pos === order.length - 1 ? '完成' : '下一题';
  const fb = $('#q-feedback'); fb.classList.add('hidden'); fb.innerHTML = '';
  if (prev) showFeedback(q, prev);
  api('visit', { method: 'POST', body: withSet(null, JSON.stringify({ mode, pos })) }).catch(() => {});
}

function onPick(L) {
  const q = order[pos];
  if (q.type === 'single') { submit([L]); return; }
  const b = document.querySelector(`.opt[data-letter="${L}"]`);
  b.classList.toggle('sel');
  picked = b.classList.contains('sel') ? [...new Set([...picked, L])] : picked.filter(x => x !== L);
}

async function submit(sel) {
  const q = order[pos];
  const r = await api('answer', { method: 'POST', body: withSet(null, JSON.stringify({ n: q.n, selected: sel, mode })) });
  roundMap[q.n] = { selected: sel, correct: r.correct, answer: r.answer, explanation: r.explanation, exp_images: r.exp_images };
  showFeedback(q, roundMap[q.n]);
}

function showFeedback(q, res) {
  document.querySelectorAll('.opt').forEach(b => {
    const L = b.dataset.letter; b.onclick = null;
    if (res.answer.includes(L)) b.classList.add('right');
    else if (res.selected.includes(L)) b.classList.add('wrong');
    b.classList.add('done');
  });
  const eb = document.querySelector('.essay-btn'); if (eb) eb.remove();
  $('#q-submit').classList.add('hidden');
  const fb = $('#q-feedback'); fb.classList.remove('hidden');
  const t = document.createElement('div');
  let fbClass = res.correct ? 'ok' : 'no';
  let fbText = q.type === 'essay' ? '参考答案' : (res.correct ? '回答正确' : '回答错误');
  // 多选少选（没错选、只漏选）显示部分正确
  if (q.type === 'multi' && !res.correct) {
    const wrong = (res.selected || []).some(x => !(res.answer || []).includes(x));
    if (!wrong) { fbText = '部分正确'; fbClass = 'part'; }
  }
  // 显示用户选的答案（答错时才显示，按字母排序）
  if (q.type !== 'essay' && !res.correct && res.selected && res.selected.length) {
    fbText += `（你选：${[...res.selected].sort().join('、')}）`;
  }
  t.className = 'fb-title ' + fbClass;
  t.textContent = fbText;
  fb.append(t);
  if (q.type !== 'essay') {
    const row = document.createElement('div');
    row.className = 'fb-row'; row.innerHTML = '正确答案：<b></b>';
    row.querySelector('b').textContent = res.answer.join('、');
    fb.append(row);
  }
  const exp = document.createElement('div');
  exp.className = 'fb-exp'; exp.textContent = res.explanation;
  fb.append(exp);
  res.exp_images.forEach(u => { const i = document.createElement('img'); i.src = '/' + u; fb.appendChild(i); });
}

$('#q-submit').onclick = () => { if (picked.length) submit(picked); };
$('#q-prev').onclick = () => { if (pos > 0) { pos--; picked = []; renderQ(); } };
$('#q-next').onclick = () => {
  if (pos < order.length - 1) { pos++; picked = []; renderQ(); }
  else finishRound();
};
$('#q-back').onclick = () => { clearQuizHash(); show('set'); renderSetPage(); };

// 进度条点击/拖拽跳转：按位置比例定位到对应题目
const progBar = document.querySelector('.qprog');
let progDrag = false;
function progSeek(e) {
  if (!order.length) return;
  const r = progBar.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
  const target = Math.min(order.length - 1, Math.floor(ratio * order.length));
  if (target !== pos) { pos = target; picked = []; renderQ(); }
}
progBar.addEventListener('pointerdown', e => { progDrag = true; progBar.setPointerCapture(e.pointerId); progSeek(e); });
progBar.addEventListener('pointermove', e => { if (progDrag) progSeek(e); });
progBar.addEventListener('pointerup', () => { progDrag = false; });
progBar.addEventListener('pointercancel', () => { progDrag = false; });

function finishRound() {
  clearQuizHash();
  const total = order.length;
  // 计分：只算单选和多选
  let score = 0, maxScore = 0;
  let singleOk = 0, singleTotal = 0, multiOk = 0, multiTotal = 0;
  order.forEach(q => {
    const r = roundMap[q.n];
    if (q.type === 'essay' || !r) return;
    const ans = r.answer || [];
    const sel = r.selected || [];
    if (q.type === 'single') {
      singleTotal++;
      maxScore += 1;
      if (r.correct) { singleOk++; score += 1; }
    } else if (q.type === 'multi') {
      multiTotal++;
      // 多选：选错（选了答案外的选项）得0分；全对2分；漏选按0.5分/个计
      const wrong = sel.some(x => !ans.includes(x));
      maxScore += 2;
      if (!wrong) {
        if (r.correct) { multiOk++; score += 2; }
        else score += sel.filter(x => ans.includes(x)).length * 0.5;
      }
    }
  });
  // 分数保留一位小数（去掉末尾的.0）
  const fmt = n => (Math.round(n * 10) / 10).toString();
  $('#r-score').textContent = fmt(score) + ' / ' + fmt(maxScore) + ' 分';
  $('#r-detail').textContent = `单选答对 ${singleOk}/${singleTotal} 道 · 多选答对 ${multiOk}/${multiTotal} 道`;
  const rate = maxScore > 0 ? score / maxScore : 0;
  $('#r-ring').style.setProperty('--p', (rate * 100).toFixed(1));
  $('#r-praise').textContent =
    maxScore === 0 ? '这一轮没有计分题，看看错题本也不错' :
    rate >= 1 ? '满分！这一轮稳稳拿下 🏆' :
    rate >= 0.8 ? '很棒，正确率优秀，继续保持' :
    rate >= 0.6 ? '不错，错题已收进错题本，记得回看' :
    '完成一轮就是进步，错题本里见';
  show('result');
}
$('#r-retry').onclick = async () => { await api('reset', { method: 'POST', body: withSet(null, JSON.stringify({ mode })) }); startQuiz(mode, 0); };
$('#r-home').onclick = () => { show('practice'); renderPractice(); };

let authMode = 'login';
async function loadMe() {
  const me = await api('me');
  const logged = !!me.logged_in;
  const info = $('#user-info');
  info.innerHTML = '';
  if (logged) {
    const s = document.createElement('span');
    s.textContent = me.email;
    if (me.vip_color) s.style.color = me.vip_color;
    info.appendChild(s);
    if (me.vip_tier && me.vip_tier !== '普通用户') {
      const b = document.createElement('span');
      b.className = 'vip-badge';
      b.textContent = me.vip_tier;
      if (me.vip_color) { b.style.color = me.vip_color; b.style.borderColor = me.vip_color; }
      info.appendChild(b);
    }
  }
  $('#btn-upload').classList.toggle('hidden', !logged);
  $('#btn-auth').classList.toggle('hidden', logged);
  $('#btn-logout').classList.toggle('hidden', !logged);
}
function setAuthMode(m) {
  authMode = m;
  $('#tab-login').classList.toggle('active', m === 'login');
  $('#tab-register').classList.toggle('active', m === 'register');
  $('#auth-submit').textContent = m === 'login' ? '登录' : '注册';
  $('#auth-err').textContent = '';
  $('#auth-password').setAttribute('autocomplete', m === 'login' ? 'current-password' : 'new-password');
}
$('#btn-auth').onclick = () => { setAuthMode('login'); $('#auth-email').value = ''; $('#auth-password').value = ''; show('auth'); };
$('#btn-logout').onclick = async () => {
  await api('logout', { method: 'POST' });
  localStorage.removeItem('quiz_set'); localStorage.removeItem('quiz_subject'); localStorage.removeItem('quiz_category');
  curCategory = 'zj-anquan'; curSubject = 'jishu'; curSet = null;
  loadHome();
};
$('#auth-back').onclick = () => { show('home'); };
$('#tab-login').onclick = () => setAuthMode('login');
$('#tab-register').onclick = () => setAuthMode('register');
$('#auth-submit').onclick = async () => {
  const email = $('#auth-email').value.trim(), password = $('#auth-password').value;
  const err = $('#auth-err');
  if (!email || !password) { err.textContent = '请输入邮箱和密码'; return; }
  $('#auth-submit').disabled = true;
  try {
    const r = await api(authMode, { method: 'POST', body: JSON.stringify({ email, password }) });
    if (!r.ok) { err.textContent = r.msg || '操作失败'; return; }
    show('home'); loadHome();
  } catch (e) { err.textContent = '网络异常，请稍后重试'; }
  finally { $('#auth-submit').disabled = false; }
};
$('#auth-password').addEventListener('keydown', e => { if (e.key === 'Enter') $('#auth-submit').click(); });

// ---------- 上传题库 ----------
const UP_STATUS = { parsing: ['解析中', ''], ready: ['待确认生成', 'ready'], need_review: ['等待人工审核', 'review'], defect: ['待你确认', 'review'], owner_review: ['复核中', 'review'], owner_final: ['站长亲审中', 'review'], done: ['已生成套题', 'ready'] };
$('#btn-upload').onclick = () => { show('upload'); renderUpload(); };
$('#promo-upload').onclick = () => {
  // 首页宣传卡大按钮：已登录直达上传页，未登录先去登录/注册
  if (!$('#btn-upload').classList.contains('hidden')) { show('upload'); renderUpload(); }
  else $('#btn-auth').click();
};
$('#btn-start').onclick = () => {
  // 首页「开始刷题」入口：已登录进刷题页（选套题），未登录先去登录/注册
  if (!$('#btn-upload').classList.contains('hidden')) { show('practice'); renderPractice(); }
  else $('#btn-auth').click();
};
$('#pr-back').onclick = () => { show('home'); loadHome(); };
$('#set-back').onclick = () => { show('practice'); renderPractice(); };
$('#up-back').onclick = () => { show('home'); loadHome(); };

// 打赏模块：上传成功页与刷完题的完成页共用同一块内容
const REWARD_HTML = `
  <div class="reward-t">解析不要钱，服务器和人工校对要吃饭。<br>觉得好用，可以<span class="rw-gold">请站长喝杯水</span> ☕</div>
  <div class="reward-imgs">
    <div><img src="/reward-alipay.jpg?v=3" alt="支付宝打赏码"><span>支付宝</span></div>
    <div><img src="/reward-wechat.jpg?v=3" alt="微信打赏码"><span>微信</span></div>
  </div>
  <div class="reward-tip">打赏时请在备注里写上您的登录邮箱，即可获得贵宾称号；管理员白天审核后自动更新，夜间暂停更新。</div>
  <div class="reward-s">打赏完全自愿，不打赏不影响任何功能</div>`;
['#up-reward', '#r-reward'].forEach(s => { const el = $(s); if (el) el.innerHTML = REWARD_HTML; });

function renderUpload() {
  const sel = $('#up-category');
  sel.innerHTML = '';
  const cats = categoriesMeta.length ? categoriesMeta : [{ id: 'zj-anquan', title: '中级注册安全工程师' }];
  cats.forEach(c => {
    const o = document.createElement('option');
    o.value = c.id; o.textContent = c.title;
    if (c.id === curCategory) o.selected = true;
    sel.appendChild(o);
  });
  fillSubjectList();
  loadMyUploads();
  // 温馨提示的实时行：当前排队总数 + 本人今日额度
  api('upload_info').then(info => {
    const el = $('#up-live');
    if (!el || !info || !info.ok) return;
    const isVip = info.vip_tier && info.vip_tier !== '普通用户';
    const tierHtml = isVip ? `<b style="color:${info.vip_color}">${info.vip_tier}</b>` : '普通用户';
    let s = `您是${tierHtml} · 今日已上传 ${info.today_used} / ${info.daily_limit} 套，还可上传 ${info.remaining} 套`;
    if (info.queue_total > 0) {
      s += ` · 当前共 ${info.queue_total} 套在排队`;
      s += isVip ? '，您是贵宾，按等级优先处理（同等级按提交顺序）' : '（贵宾优先），您的排队位置见下方「我的上传」';
    } else {
      s += ' · 当前没有排队，上传后很快就能处理';
    }
    el.innerHTML = s;
  }).catch(() => {});
}
function fillSubjectList() {
  // 科目/专业改为下拉选择：选项随上面选的考试类别自动匹配（规范清单来自 /api/meta）
  const cat = $('#up-category').value;
  const sel = $('#up-subject'); sel.innerHTML = '';
  let titles = categorySubjectsMap[cat] || [];
  if (!titles.length)
    titles = subjectsMeta.filter(s => (s.category || 'zj-anquan') === cat).map(s => s.title);
  titles.forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t; sel.appendChild(o);
  });
}
$('#up-category').addEventListener('change', fillSubjectList);

async function loadMyUploads() {
  const box = $('#up-list'); box.innerHTML = '';
  let rows = [];
  try { rows = await api('my_uploads'); } catch (e) { return; }
  if (!rows.length) { box.innerHTML = '<div class="up-m" style="color:#8a877f;font-size:13px">还没有上传过题库</div>'; return; }
  rows.forEach(r => {
    const st = UP_STATUS[r.status] || [r.status, ''];
    const div = document.createElement('div'); div.className = 'up-item';
    const sm = r.summary || {};
    let meta = r.subject_title + ' · ' + (r.filename || '') + (r.answer_filename ? ' + 答案：' + r.answer_filename : '');
    if (r.status === 'ready' || r.status === 'done') meta += `<br>共 ${sm.total || 0} 题（单选 ${sm.single || 0} / 多选 ${sm.multi || 0}）`;
    if (sm.warnings && sm.warnings.length) meta += '<br>⚠ ' + sm.warnings.join('；');
    if (r.status === 'need_review' && typeof r.queue_ahead === 'number')
      meta += `<br>⏳ 人工审核排队中：前面还有 ${r.queue_ahead} 套，预计约 ${r.eta_hours} 小时内完成${r.is_vip ? ' · 贵宾优先' : ''}`;
    if (r.status === 'defect') {
      const ps = (r.problems && r.problems.length) ? r.problems : ['原文件有问题，详见审核结果'];
      meta += '<br>⚠ 审核发现这份卷子本身有问题，需要你确认：' + ps.map(p => '<br>· ' + p).join('');
      meta += '<br>请核对原文件：确实有问题就点「放弃上传」；确认原文件无误就点「已确认，题目无误」，我们会再复核一遍。';
    }
    if (r.status === 'owner_review') meta += '<br>⏳ 你已确认题目无误，正在复核中…';
    if (r.status === 'owner_final') meta += '<br>⏳ 复核后仍有问题，已转站长亲自审核，请等站长处理';
    div.innerHTML = '<div class="up-t"></div><div class="up-m"></div>';
    div.querySelector('.up-t').innerHTML = '';
    div.querySelector('.up-t').textContent = r.title;
    const chip = document.createElement('span'); chip.className = 'up-chip ' + st[1]; chip.textContent = st[0];
    div.querySelector('.up-t').appendChild(chip);
    div.querySelector('.up-m').innerHTML = meta;
    const acts = document.createElement('div'); acts.className = 'up-actions';
    if (r.status === 'ready') {
      const b1 = document.createElement('button'); b1.textContent = '生成套题';
      b1.onclick = async () => {
        const res = await api('upload/' + r.id + '/confirm', { method: 'POST' });
        if (res.ok) {
          alert('已生成套题（仅你可见），共 ' + res.total + ' 题');
          loadMyUploads();
        }
        else alert(res.msg || '生成失败');
      };
      acts.appendChild(b1);
    }
    if (r.status === 'done' && r.set_id) {
      const bOpen = document.createElement('button'); bOpen.textContent = '打开套题'; bOpen.className = 'ghost';
      bOpen.onclick = async () => {
        curSet = r.set_id;
        localStorage.setItem('quiz_set', curSet);
        await loadHome();
        const s = setsMeta.find(x => x.id === curSet);
        if (s) {
          curCategory = s.category || curCategory;
          curSubject = s.subject || curSubject;
          localStorage.setItem('quiz_category', curCategory);
          localStorage.setItem('quiz_subject', curSubject);
        }
        show('set'); renderSetPage();
      };
      acts.appendChild(bOpen);
    }
    if (r.status === 'defect') {
      const bOk = document.createElement('button'); bOk.textContent = '已确认，题目无误';
      bOk.onclick = async () => {
        if (!confirm('确认原文件题目无误？提交后我们会再复核一遍。')) return;
        const res = await api('upload/' + r.id + '/confirm_ok', { method: 'POST' });
        if (res.ok && res.status === 'ready') alert('复核通过，已恢复为待确认生成');
        else if (res.ok) alert('已提交站长终审');
        else alert(res.msg || '提交失败');
        loadMyUploads();
      };
      acts.appendChild(bOk);
    }
    if (r.status === 'ready' || r.status === 'need_review' || r.status === 'defect') {
      const b2 = document.createElement('button'); b2.textContent = r.status === 'defect' ? '放弃上传' : '放弃'; b2.className = 'ghost';
      b2.onclick = async () => {
        if (!confirm('放弃这份上传？')) return;
        await api('upload/' + r.id + '/discard', { method: 'POST' });
        loadMyUploads();
      };
      acts.appendChild(b2);
    }
    if (acts.children.length) div.appendChild(acts);
    box.appendChild(div);
  });
}

// 文件一选中就把内容读进内存：部分手机浏览器（鸿蒙上的 Chrome/Edge）
// 选完第二个文件后，第一个文件的读取许可会失效，提交时再回头读文件
// 会直接报错「网络异常」且请求发不出去。提前读进内存，提交时从内存发，
// 不再碰可能已失效的文件句柄。
const _upCache = {};
function _captureUploadFile(inputSel, key) {
  const inp = $(inputSel);
  if (!inp) return;
  inp.addEventListener('change', () => {
    const f = inp.files && inp.files[0];
    if (!f) { delete _upCache[key]; return; }
    const entry = { name: f.name, size: f.size, blob: null, promise: null };
    entry.promise = f.arrayBuffer().then(buf => {
      entry.blob = new Blob([buf], { type: 'application/pdf' });
      return entry.blob;
    }).catch(() => null);
    _upCache[key] = entry;
  });
}
_captureUploadFile('#up-file', 'main');
_captureUploadFile('#up-file-ans', 'ans');
async function _pickedFile(inputSel, key) {
  const inp = $(inputSel);
  const f = inp && inp.files && inp.files[0];
  if (!f) return null;
  const c = _upCache[key];
  if (c && c.name === f.name && c.size === f.size) {
    const blob = await c.promise;
    if (blob) return { blob: blob, name: f.name };
  }
  return { blob: f, name: f.name };
}

$('#up-submit').onclick = async () => {
  const err = $('#up-err'); err.textContent = '';
  const subject = $('#up-subject').value.trim();
  if (!subject) { err.textContent = '请选择科目 / 专业'; return; }
  if (!($('#up-file').files && $('#up-file').files[0])) { err.textContent = '请选择 PDF 文件'; return; }
  $('#up-submit').disabled = true;
  try {
    const main = await _pickedFile('#up-file', 'main');
    if (!main) { err.textContent = '请选择 PDF 文件'; return; }
    const fd = new FormData();
    fd.append('file', main.blob, main.name);
    const ans = await _pickedFile('#up-file-ans', 'ans');
    if (ans) fd.append('answer_file', ans.blob, ans.name);
    fd.append('category', $('#up-category').value);
    fd.append('subject_title', subject);
    fd.append('title', $('#up-title').value.trim());
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const res = await r.json();
    if (!res.ok) { err.textContent = res.msg || '上传失败'; return; }
    $('#up-reward').classList.remove('hidden');
    if (res.status === 'ready') {
      alert('解析完成：共 ' + res.summary.total + ' 题，请在下方「我的上传」里确认生成套题');
    }
    else alert('这份 PDF 没能自动解析，已转人工审核，处理完会出现在你的上传列表里');
    loadMyUploads();
  } catch (e) { err.textContent = '网络异常，请稍后重试'; }
  finally { $('#up-submit').disabled = false; }
};

// 答题字号调节（15/17/19/21 四档，记住选择）
const FS_LEVELS = [15, 17, 19, 21];
let fsIdx = FS_LEVELS.indexOf(parseInt(localStorage.getItem('qfs') || '17', 10));
if (fsIdx < 0) fsIdx = 1;
function applyFs() {
  document.documentElement.style.setProperty('--qfs', FS_LEVELS[fsIdx] + 'px');
  localStorage.setItem('qfs', String(FS_LEVELS[fsIdx]));
}
$('#fs-dec').onclick = () => { if (fsIdx > 0) { fsIdx--; applyFs(); } };
$('#fs-inc').onclick = () => { if (fsIdx < FS_LEVELS.length - 1) { fsIdx++; applyFs(); } };
applyFs();

// 页面加载：按 URL hash 恢复刷新前的页面——#quiz=模式 回答题页原位置，
// #page=页面 回对应页（完成页数据无法重建，刷新后回套题页），无 hash 则停在首页
(async () => {
  const hm = (location.hash || '').match(/quiz=(seq|rand|wrong|fav|essay)/);
  const pm = (location.hash || '').match(/page=(practice|set|result|upload|auth)/);
  try { await loadHome(); }
  catch (e) { $('#set-desc').textContent = '服务连接失败，请稍后重试'; return; }
  if (hm) {
    const st = await api(withSet('state')).catch(() => null);
    const p = !st ? 0 : hm[1] === 'seq' ? st.seq_pos : hm[1] === 'rand' ? st.rand_pos : 0;
    startQuiz(hm[1], p);
  } else if (pm) {
    const page = pm[1];
    if (page === 'practice') { show('practice'); renderPractice(); }
    else if (page === 'set' || page === 'result') { show('set'); renderSetPage(); }
    else if (page === 'upload') {
      const me = await api('me').catch(() => null);
      if (me && me.logged_in) { show('upload'); renderUpload(); }
    } else if (page === 'auth') {
      const me = await api('me').catch(() => null);
      if (!me || !me.logged_in) { setAuthMode('login'); show('auth'); }
    }
  }
})();

// 打赏公告轮换播报（首页与刷题页共用）
const _esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let tickerItems = [], tickerIdx = 0, tickerTimer = null;
function renderTickerItem() {
  if (!tickerItems.length) return;
  const it = tickerItems[tickerIdx % tickerItems.length];
  tickerIdx++;
  const html = `🎉 恭喜 <b style="color:${it.color}">${_esc(it.display)}</b> 为本站捐献 ${it.amount} 元，成为${it.tier}，感谢支持！`;
  ['#ticker-home', '#ticker-practice'].forEach(s => {
    const el = $(s);
    if (!el) return;
    el.innerHTML = html;
    el.classList.remove('tick-anim'); void el.offsetWidth; el.classList.add('tick-anim');
  });
}
async function loadTicker() {
  let items = [];
  try { items = await api('donations/recent'); } catch (e) { return; }
  if (!items || !items.length) return;
  tickerItems = items;
  ['#ticker-home', '#ticker-practice'].forEach(s => { const el = $(s); if (el) el.classList.remove('hidden'); });
  renderTickerItem();
  if (tickerTimer) clearInterval(tickerTimer);
  tickerTimer = setInterval(renderTickerItem, 5000);
}
loadTicker();
