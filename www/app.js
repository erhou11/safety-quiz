const $ = s => document.querySelector(s);
const LETTERS = 'ABCDEFGH';
let mode = 'seq', order = [], pos = 0, roundMap = {}, t0 = 0, picked = [];

function show(id) {
  document.querySelectorAll('.screen').forEach(e => e.classList.remove('active'));
  $('#screen-' + id).classList.add('active');
  window.scrollTo(0, 0);
}
async function api(p, o = {}) {
  const r = await fetch('/api/' + p, Object.assign({ headers: { 'Content-Type': 'application/json' } }, o));
  if (!r.ok) throw new Error('api ' + r.status);
  return r.json();
}

async function loadHome() {
  const meta = await api('meta'), st = await api('state');
  $('#st-total').textContent = meta.total;
  $('#st-single').textContent = meta.single;
  $('#st-multi').textContent = meta.multi;
  $('#seq-hint').textContent = st.seq_pos > 0 ? `上次做到第 ${st.seq_pos + 1} 题，点击继续` : '从第 1 题开始，完整练完一套';
  $('#rand-hint').textContent = st.rand_pos > 0 ? `上次做到第 ${st.rand_pos + 1} 题，点击继续` : '打乱顺序，随机抽题练习';
  $('#wrong-hint').textContent = st.wrong_count > 0 ? `共 ${st.wrong_count} 道错题，点击重练` : '答错的题目会自动收录在这里';
  $('#btn-seq').onclick = () => startQuiz('seq', st.seq_pos);
  $('#btn-rand').onclick = () => startQuiz('rand', st.rand_pos);
  const bw = $('#btn-wrong');
  bw.classList.toggle('disabled', st.wrong_count === 0);
  bw.onclick = () => { if (st.wrong_count > 0) startQuiz('wrong', 0); };
}

async function startQuiz(m, resumePos) {
  mode = m; t0 = Date.now(); picked = [];
  order = await api('questions?mode=' + m);
  if (!order.length) return;
  roundMap = await api('round');
  pos = Math.min(resumePos || 0, order.length - 1);
  show('quiz');
  renderQ();
}

async function renderQ() {
  const q = order[pos];
  $('#q-count').textContent = (pos + 1) + '/' + order.length;
  $('#q-prog-fill').style.width = ((pos + 1) / order.length * 100) + '%';
  $('#q-cat').textContent = '分类 ' + q.cat;
  $('#q-type').textContent = q.type === 'single' ? '单选题' : '多选题';
  $('#q-stem').textContent = q.n + '．' + q.stem;
  const im = $('#q-imgs'); im.innerHTML = '';
  q.images.forEach(u => { const i = document.createElement('img'); i.src = '/' + u; i.loading = 'lazy'; im.appendChild(i); });
  const box = $('#q-opts'); box.innerHTML = '';
  const prev = roundMap[q.n];
  q.options.forEach((o, i) => {
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
  api('visit', { method: 'POST', body: JSON.stringify({ mode, pos }) }).catch(() => {});
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
  const r = await api('answer', { method: 'POST', body: JSON.stringify({ n: q.n, selected: sel, mode }) });
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
  $('#q-submit').classList.add('hidden');
  const fb = $('#q-feedback'); fb.classList.remove('hidden');
  const t = document.createElement('div');
  t.className = 'fb-title ' + (res.correct ? 'ok' : 'no');
  t.textContent = res.correct ? '回答正确' : '回答错误';
  const row = document.createElement('div');
  row.className = 'fb-row'; row.innerHTML = '正确答案：<b></b>';
  row.querySelector('b').textContent = res.answer.join('、');
  const exp = document.createElement('div');
  exp.className = 'fb-exp'; exp.textContent = res.explanation;
  fb.append(t, row, exp);
  res.exp_images.forEach(u => { const i = document.createElement('img'); i.src = '/' + u; fb.appendChild(i); });
}

$('#q-submit').onclick = () => { if (picked.length) submit(picked); };
$('#q-prev').onclick = () => { if (pos > 0) { pos--; picked = []; renderQ(); } };
$('#q-next').onclick = () => {
  if (pos < order.length - 1) { pos++; picked = []; renderQ(); }
  else finishRound();
};
$('#q-back').onclick = () => { show('home'); loadHome(); };

function finishRound() {
  const total = order.length;
  let ok = 0;
  order.forEach(q => { if (roundMap[q.n] && roundMap[q.n].correct) ok++; });
  const mins = Math.max(1, Math.round((Date.now() - t0) / 60000));
  $('#r-score').textContent = ok + ' / ' + total;
  $('#r-detail').textContent = `正确率 ${Math.round(ok / total * 100)}% · 用时约 ${mins} 分钟`;
  show('result');
}
$('#r-retry').onclick = async () => { await api('reset', { method: 'POST', body: JSON.stringify({ mode }) }); startQuiz(mode, 0); };
$('#r-home').onclick = () => { show('home'); loadHome(); };

loadHome().catch(e => { $('#seq-hint').textContent = '服务连接失败，请稍后重试'; });
