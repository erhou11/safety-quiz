const $ = s => document.querySelector(s);
const LETTERS = 'ABCDEFGH';
let mode = 'seq', order = [], pos = 0, roundMap = {}, t0 = 0, picked = [];
let curSet = localStorage.getItem('quiz_set') || 's1';
let curSubject = localStorage.getItem('quiz_subject') || 'jishu';
let setsMeta = [];
let subjectsMeta = [];

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
const withSet = (p, body) => {
  if (body) { const b = JSON.parse(body); b.set = curSet; return JSON.stringify(b); }
  return p + (p.includes('?') ? '&' : '?') + 'set=' + curSet;
};

function subjectSets() {
  return setsMeta.filter(s => s.subject === curSubject);
}

function renderSubjectTabs() {
  const box = $('#subject-tabs'); box.innerHTML = '';
  subjectsMeta.forEach(s => {
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
      loadHome();
    };
    box.appendChild(b);
  });
}

function renderSetTabs() {
  const box = $('#set-tabs'); box.innerHTML = '';
  subjectSets().forEach(s => {
    const b = document.createElement('button');
    b.className = 'set-tab' + (s.id === curSet ? ' active' : '');
    b.innerHTML = '<div class="st-k"></div><div class="st-t"></div><div class="st-c"></div>';
    b.querySelector('.st-k').textContent = s.kicker;
    b.querySelector('.st-t').textContent = s.title;
    b.querySelector('.st-c').textContent = s.total + ' 题';
    b.onclick = () => {
      if (curSet === s.id) return;
      curSet = s.id;
      localStorage.setItem('quiz_set', curSet);
      loadHome();
    };
    box.appendChild(b);
  });
}

async function loadHome() {
  loadMe().catch(() => {});
  const meta = await api('meta');
  subjectsMeta = meta.subjects || [];
  setsMeta = meta.sets;
  if (!subjectsMeta.some(s => s.id === curSubject)) curSubject = (subjectsMeta[0] || {}).id || 'jishu';
  renderSubjectTabs();
  const ss = subjectSets();
  if (!ss.some(s => s.id === curSet)) curSet = ss.length ? ss[0].id : null;
  renderSetTabs();
  const subj = subjectsMeta.find(x => x.id === curSubject) || {};
  const hasSets = ss.length > 0;
  document.querySelector('.hero').classList.toggle('hidden', !hasSets);
  document.querySelector('.cards').classList.toggle('hidden', !hasSets);
  $('#subject-empty').classList.toggle('hidden', hasSets);
  if (!hasSets) {
    $('#empty-title').textContent = (subj.title || '') + '题库整理中';
    return;
  }
  const s = setsMeta.find(x => x.id === curSet);
  $('#set-kicker').textContent = s.kicker;
  $('#set-title').textContent = s.title;
  $('#set-desc').textContent = s.desc;
  $('#st-total').textContent = s.total;
  $('#st-single').textContent = s.single;
  $('#st-multi').textContent = s.multi;
  const st = await api(withSet('state'));
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
  order = await api(withSet('questions?mode=' + m));
  if (!order.length) return;
  roundMap = await api(withSet('round'));
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
$('#r-retry').onclick = async () => { await api('reset', { method: 'POST', body: withSet(null, JSON.stringify({ mode })) }); startQuiz(mode, 0); };
$('#r-home').onclick = () => { show('home'); loadHome(); };

let authMode = 'login';
async function loadMe() {
  const me = await api('me');
  const logged = !!me.logged_in;
  $('#user-info').textContent = logged ? me.email : '';
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
  localStorage.removeItem('quiz_set'); localStorage.removeItem('quiz_subject');
  curSubject = 'jishu'; curSet = null;
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

loadHome().catch(e => { $('#set-desc').textContent = '服务连接失败，请稍后重试'; });
