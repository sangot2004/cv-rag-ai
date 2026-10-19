/* Offline design prototype. No API, storage, credentials, or model calls. */
(() => {
  'use strict';
  const root = document.querySelector('[data-preview-root]');
  if (!root) return;
  const params = new URLSearchParams(location.search);
  const role = params.get('role') === 'tester' || (!params.has('role') && document.body.dataset.page === 'forbidden') ? 'tester' : 'admin';
  const page = document.body.dataset.page;
  const paths = {
    login: '../auth_01_ng_nh_p_h_th_ng/code.html',
    chat: '../chat_02_kh_ng_gian_h_i_tho_i_x_c_nh_n_jd/code.html',
    forbidden: '../sys_01_kh_ng_quy_n_truy_c_p_403/code.html',
    gallery: '../index.html',
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
  const iconPaths = {
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m16 16 4 4"/>',
    trash: '<path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M14 8l4 4-4 4M8 12h10"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    send: '<path d="m22 2-7 20-4-9-9-4 20-7zM22 2 11 13"/>',
    lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    alert: '<path d="m12 3 10 18H2L12 3zM12 9v5M12 17h.01"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    up: '<path d="M7 10v11H3V10h4zm0 1 5-8h1a2 2 0 0 1 2 2l-1 5h5a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 2H7"/>',
    down: '<path d="M7 14V3H3v11h4zm0-1 5 8h1a2 2 0 0 0 2-2l-1-5h5a2 2 0 0 0 2-2l-2-7a2 2 0 0 0-2-2H7"/>',
    eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.8 5.2A11 11 0 0 1 12 5c7 0 10 7 10 7a17 17 0 0 1-3 4M6.3 6.3C3.5 8.2 2 12 2 12s3 7 10 7a12 12 0 0 0 5-1.1"/>',
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5M6.1 6.1A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.9"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.9"/><circle cx="9" cy="7" r="4"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
    chart: '<path d="M3 3v18h18M8 16v-4M13 16V7M18 16v-7"/>',
    spark: '<path d="m12 3 2.7 6.3L21 12l-6.3 2.7L12 21l-2.7-6.3L3 12l6.3-2.7L12 3z"/>',
  };
  const icon = (name, extra = '') => `<span class="icon ${extra}" aria-hidden="true"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${iconPaths[name] || iconPaths.info}</svg></span>`;
  const brand = `<span class="brand-mark">${icon('file')}</span><span><strong>CV RAG AI</strong><small>Trợ lý tuyển dụng</small></span>`;
  const user = {username: role === 'admin' ? 'sang' : 'tester_a', role,
    label: role === 'admin' ? 'Quản trị viên' : 'Tài khoản thử nghiệm',
    scope: role === 'admin' ? 'Tra cứu theo quyền quản trị' : 'CV thuộc phòng ban được cấp'};
  function href(target, values = {}) {
    const url = new URL(paths[target], location.href);
    url.search = new URLSearchParams({role, ...values}).toString();
    return url.href;
  }
  function toast(text) {
    const element = document.querySelector('#toast');
    element.textContent = text;
    element.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { element.hidden = true; }, 3600);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast('Đã sao chép.'); }
    catch { toast('Trình duyệt chưa cho phép sao chép. Vui lòng chọn và sao chép nội dung.'); }
  }
  function announce(text) {
    document.querySelector('#announcer').textContent = text;
  }
  const globalHelpers = '<div id="toast" class="toast" role="status" hidden></div><div id="announcer" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>';

  if (page === 'login') {
    renderLogin();
    return;
  }

  const knownStates = new Set(['empty', 'answer', 'pending', 'multiple', 'running', 'failed', 'interrupted', 'unavailable', 'timeout', 'recovering', 'loading', 'not-found', 'cleanup', 'stale']);
  let state = knownStates.has(params.get('state')) ? params.get('state') : 'pending';
  if (params.get('state') === 'expired') {
    location.replace(href('login', {mode: 'expired'}));
    return;
  }
  const generatedId = () => crypto.randomUUID();
  let conversations = [
    {id: 'b321c9ad-7c28-4776-aabc-d2f20c245b8f', title: 'Tìm ứng viên Data Engineer', state: 'pending', label: 'Đang chờ xác nhận'},
    {id: 'e254a1c0-465e-49dc-9c1a-91d45c82443b', title: 'Ứng viên có kinh nghiệm Python', state: 'answer', label: 'Gần đây'},
    {id: 'd5f62434-6d5e-4ff4-9074-6495cdc6d10e', title: 'Tra cứu kinh nghiệm và kỹ năng', state: 'answer', label: 'Gần đây'},
  ];
  let activeId = ['empty', 'not-found', 'cleanup'].includes(state) ? null : conversations[0].id;
  let pending = [];
  let messages = [];
  let voted = new Set();
  let criteriaDrafts = new Map();
  const threadData = new Map();
  let draft = '';
  let busy = false;
  let deleteTarget = null;
  let cleanupId = state === 'cleanup' ? 'a1ad10a4-e3ba-4491-8339-3968c3eb08a8' : null;
  let actionVersion = 0;
  const defaults = {position_title: 'Data Engineer', required_skills: ['Python', 'SQL'], min_years_experience: 1, preferred_education: null, top_k: 3};
  const confirmationId = '37e3d978cb8f4a33a23152b425021980';
  const requestId = '28254935-553e-413a-bdda-bf692d82a430';
  let lastAction = null;
  root.innerHTML = shell();
  setupShell();
  if (page === 'forbidden') {
    renderForbidden();
  } else {
    setScenario(state);
  }
  // Inspection hook for the offline review only; contains no credentials.
  window.CVRagPreview = {getSnapshot: () => structuredClone({state, role, activeId, pending, messages, cleanupId, lastAction})};

  function shell() {
    const adminModules = role === 'admin' ? `<section class="admin-preview" aria-label="Các phân hệ quản trị sắp ra mắt"><p>Quản trị<span class="badge">Sắp ra mắt</span></p><button disabled>${icon('users')}Quản lý tài khoản</button><button disabled>${icon('chart')}System Ops</button></section>` : '';
    return `<a href="#main-content" class="skip-link">Đến nội dung chính</a>
      <div class="workspace">
        <div class="drawer-backdrop" id="drawer-backdrop" hidden></div>
        <aside class="sidebar" id="sidebar" aria-label="Danh sách hội thoại">
          <div class="sidebar-top"><a href="${esc(href('chat', {state: 'empty'}))}" class="brand" aria-label="CV RAG AI — Chat mới">${brand}</a><button class="icon-button mobile-only" id="close-menu" aria-label="Đóng danh sách hội thoại">${icon('close')}</button></div>
          <div class="sidebar-new"><button class="btn primary full" data-action="new">${icon('plus')}Cuộc trò chuyện mới</button></div>
          <div class="sidebar-content"><div class="sidebar-label"><span>Hội thoại gần đây</span><span id="history-count"></span></div>
            <label class="history-search">${icon('search')}<span class="sr-only">Tìm trong hội thoại gần đây</span><input id="history-search" placeholder="Tìm trong hội thoại gần đây" type="search" maxlength="100"></label>
            <nav id="conversation-list" aria-label="Hội thoại của bạn"></nav><p class="sidebar-note">Tối đa 50 hội thoại gần đây của bạn.</p>${adminModules}
          </div>
          <div class="sidebar-footer"><div class="user-block"><span class="avatar" aria-hidden="true">${role === 'admin' ? 'SA' : 'TA'}</span><div class="user-info"><strong>${esc(user.username)}</strong><small>${esc(user.label)}</small></div><button class="icon-button" id="logout" aria-label="Đăng xuất">${icon('logout')}</button></div><p class="scope-caption">${esc(user.scope)}</p><a class="preview-link" href="${paths.gallery}">Bản xem trước thiết kế</a></div>
        </aside>
        <div class="main-panel" id="main-panel">
          <header class="workspace-header"><button id="open-menu" class="icon-button mobile-only" aria-label="Mở danh sách hội thoại" aria-expanded="false" aria-controls="sidebar">${icon('menu')}</button><div class="header-title"><p class="eyebrow">Không gian tuyển dụng</p><h1 id="chat-title">Hỏi đáp cùng CV RAG AI</h1><p class="header-subtitle" id="chat-subtitle">${esc(user.scope)}</p></div><div class="header-actions"><span class="badge" id="status-badge"></span><button class="btn compact" data-action="new" title="Cuộc trò chuyện mới">${icon('plus')}<span class="action-label">Chat mới</span></button><button class="icon-button destructive" id="delete-active" aria-label="Xóa hội thoại đang mở">${icon('trash')}</button></div></header>
          <main class="scroll-region" id="main-content" tabindex="-1"><div class="chat-content" id="chat-content"></div></main>
          <footer class="composer-area" id="composer-area"><div class="composer-inner"><div class="composer-guard" id="composer-guard" hidden></div><form id="composer-form"><div class="composer-box" id="composer-box"><label class="sr-only" for="question">Câu hỏi cho trợ lý AI</label><textarea id="question" rows="2" maxlength="20000" aria-describedby="question-help question-count" placeholder="Hỏi về kỹ năng, kinh nghiệm hoặc dán mô tả công việc…"></textarea><div class="composer-bottom"><span class="char-count" id="question-count">0 / 20.000 ký tự</span><button class="btn primary compact" id="send-message" type="submit">Gửi${icon('send')}</button></div></div></form><p class="composer-caption" id="question-help">Hãy kiểm tra lại thông tin trong CV trước khi đưa ra quyết định tuyển dụng.</p></div></footer>
        </div>
      </div>
      <dialog id="delete-dialog" aria-labelledby="delete-heading"><h2 id="delete-heading">Xóa hội thoại này?</h2><p id="delete-description"></p><p>Lịch sử sẽ biến mất khỏi danh sách và bạn không thể mở lại hội thoại này.</p><div class="dialog-actions"><button class="btn" id="cancel-delete">Giữ lại</button><button class="btn danger" id="confirm-delete">Xóa hội thoại</button></div></dialog>
      ${globalHelpers}`;
  }

  function setupShell() {
    root.querySelectorAll('[data-action="new"]').forEach(button => button.addEventListener('click', newChat));
    root.querySelector('#history-search').addEventListener('input', renderSidebar);
    root.querySelector('#logout').addEventListener('click', () => {
      actionVersion += 1; messages = []; pending = []; draft = ''; conversations = [];
      location.assign(href('login', {mode: 'signed-out'}));
    });
    root.querySelector('#delete-active').addEventListener('click', () => openDelete(activeId));
    const dialog = root.querySelector('#delete-dialog');
    root.querySelector('#cancel-delete').addEventListener('click', () => dialog.close());
    root.querySelector('#confirm-delete').addEventListener('click', () => {
      const id = deleteTarget;
      dialog.close();
      if (!id) return;
      conversations = conversations.filter(item => item.id !== id);
      if (id === activeId) newChat();
      else renderSidebar();
      toast('Đã xóa hội thoại.');
      lastAction = {type: 'delete', thread_id: id};
    });
    root.querySelector('#composer-form').addEventListener('submit', sendMessage);
    const input = root.querySelector('#question');
    input.addEventListener('input', () => {
      draft = input.value;
      renderComposer();
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault();
        if (draft.trim() && !input.disabled) root.querySelector('#composer-form').requestSubmit();
      }
    });
    setupDrawer();
  }

  function setupDrawer() {
    const sidebar = root.querySelector('#sidebar');
    const panel = root.querySelector('#main-panel');
    const backdrop = root.querySelector('#drawer-backdrop');
    const open = root.querySelector('#open-menu');
    const close = root.querySelector('#close-menu');
    const small = matchMedia('(max-width: 767px)');
    function setDrawer(visible) {
      sidebar.classList.toggle('open', visible);
      backdrop.classList.toggle('open', visible);
      backdrop.hidden = !visible;
      panel.inert = visible;
      open.setAttribute('aria-expanded', String(visible));
      sidebar.inert = small.matches && !visible;
      if (visible) {
        sidebar.setAttribute('role', 'dialog'); sidebar.setAttribute('aria-modal', 'true');
        close.focus();
      } else {
        sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal');
      }
    }
    open.addEventListener('click', () => setDrawer(true));
    close.addEventListener('click', () => { setDrawer(false); open.focus(); });
    backdrop.addEventListener('click', () => { setDrawer(false); open.focus(); });
    sidebar.addEventListener('keydown', event => {
      if (!sidebar.classList.contains('open')) return;
      if (event.key === 'Escape') { setDrawer(false); open.focus(); }
      if (event.key === 'Tab') {
        const elements = [...sidebar.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled)')].filter(element => element.getClientRects().length);
        const first = elements[0], last = elements.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    small.addEventListener('change', () => setDrawer(false));
    setDrawer(false);
    window.closePreviewDrawer = () => setDrawer(false);
  }

  function renderSidebar() {
    const query = root.querySelector('#history-search').value.trim().toLocaleLowerCase('vi');
    const items = conversations.filter(item => item.title.toLocaleLowerCase('vi').includes(query));
    root.querySelector('#history-count').textContent = String(conversations.length);
    root.querySelector('#conversation-list').innerHTML = items.map(item => `<div class="history-item ${item.id === activeId ? 'active' : ''}"><button class="history-open" data-thread="${esc(item.id)}" ${item.id === activeId ? 'aria-current="page"' : ''}><strong>${esc(item.title)}</strong><small>${esc(item.label)}</small></button><button class="icon-button destructive" data-delete="${esc(item.id)}" aria-label="Xóa hội thoại: ${esc(item.title)}">${icon('trash')}</button></div>`).join('') || `<p class="sidebar-note">${query ? 'Không có hội thoại khớp từ khóa.' : 'Chưa có hội thoại. Hãy bắt đầu một cuộc trò chuyện mới.'}</p>`;
    root.querySelectorAll('[data-thread]').forEach(button => button.addEventListener('click', () => {
      if (page === 'forbidden') { location.assign(href('chat', {state: 'answer'})); return; }
      if (busy) { toast('Vui lòng chờ lượt hiện tại hoàn tất.'); return; }
      saveThread();
      const item = conversations.find(item => item.id === button.dataset.thread);
      activeId = item.id;
      const saved = threadData.get(item.id);
      if (saved) {
        ({state, messages, pending, draft} = structuredClone(saved));
        voted = new Set(saved.voted);
        criteriaDrafts = new Map(structuredClone(saved.criteriaDrafts));
        root.querySelector('#question').value = draft;
        setUrlState(); renderAll();
      } else {
        voted = new Set();
        setScenario(item.state, true);
      }
      window.closePreviewDrawer();
      root.querySelector('#main-content').focus();
    }));
    root.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', () => openDelete(button.dataset.delete)));
  }

  function openDelete(id) {
    if (!id) return;
    if (busy || (state === 'running' && id === activeId)) { toast('Hội thoại đang được xử lý. Vui lòng kiểm tra lại trạng thái sau.'); return; }
    deleteTarget = id;
    const item = conversations.find(item => item.id === id);
    root.querySelector('#delete-description').textContent = item ? `Bạn sắp xóa “${item.title}”.` : 'Bạn sắp xóa hội thoại đã chọn.';
    root.querySelector('#delete-dialog').showModal();
    root.querySelector('#cancel-delete').focus();
  }

  function newChat() {
    if (page === 'forbidden') { location.assign(href('chat', {state: 'empty'})); return; }
    if (busy) { toast('Vui lòng chờ lượt hiện tại hoàn tất.'); return; }
    saveThread();
    actionVersion += 1;
    activeId = null; state = 'empty'; draft = ''; messages = []; pending = []; voted = new Set(); criteriaDrafts = new Map();
    root.querySelector('#question').value = '';
    root.querySelector('#history-search').value = '';
    setUrlState();
    renderAll();
    window.closePreviewDrawer();
    root.querySelector('#question').focus();
  }

  function setUrlState() {
    const url = new URL(location.href);
    url.searchParams.set('state', state); url.searchParams.set('role', role);
    history.replaceState(null, '', url);
  }

  function saveThread() {
    if (activeId) threadData.set(activeId, structuredClone({state, messages, pending, draft,
      voted: [...voted], criteriaDrafts: [...criteriaDrafts]}));
  }

  function setScenario(next, keepActive = false) {
    state = next; busy = false; pending = []; messages = []; draft = ''; criteriaDrafts = new Map();
    root.querySelector('#question').value = '';
    const completed = [
      {id: 'sample-human-1', role: 'user', content: 'Liệt kê ứng viên có kinh nghiệm Python và SQL.'},
      {id: 'sample-assistant-1', role: 'assistant', content: 'Ứng viên An có kinh nghiệm phát triển pipeline dữ liệu với Python và SQL. Ứng viên Bình có kinh nghiệm phân tích dữ liệu và xây dựng truy vấn SQL.\n\nBạn có thể cung cấp JD cụ thể để mình tìm kiếm theo tiêu chí tuyển dụng.'},
    ];
    const question = {id: 'sample-human-2', role: 'user', content: 'Tìm 3 ứng viên Data Engineer, biết Python và SQL, tối thiểu 1 năm kinh nghiệm.'};
    if (next === 'answer') messages = completed;
    if (['pending', 'multiple', 'stale'].includes(next)) {
      messages = [question];
      pending = [{confirmation_id: confirmationId, criteria: structuredClone(defaults)}];
      if (next === 'multiple') pending.push({confirmation_id: 'd156e098437448e092d16bf41629d4b1', criteria: {...structuredClone(defaults), position_title: 'Backend Developer', required_skills: ['Python', 'FastAPI'], top_k: 1}});
    }
    if (['running', 'failed', 'interrupted', 'unavailable', 'timeout', 'recovering'].includes(next)) messages = [question];
    if (!keepActive && ['empty', 'cleanup', 'not-found'].includes(next)) activeId = null;
    setUrlState();
    renderAll();
  }

  function renderAll() {
    renderSidebar();
    const current = conversations.find(item => item.id === activeId);
    root.querySelector('#chat-title').textContent = current?.title || 'Hỏi đáp cùng CV RAG AI';
    root.querySelector('#chat-subtitle').textContent = user.scope;
    const badge = root.querySelector('#status-badge');
    const badges = {
      empty: ['', ''], answer: ['Sẵn sàng', 'success'], pending: ['Cần xác nhận', 'pending'], multiple: ['Cần xác nhận', 'pending'], stale: ['Tiêu chí đã thay đổi', 'pending'],
      running: ['Đang xử lý', ''], loading: ['Đang tải', ''], recovering: ['Kiểm tra trạng thái', ''],
      failed: ['Lượt xử lý bị lỗi', 'error'], interrupted: ['Lượt chưa hoàn tất', 'pending'], unavailable: ['Tạm không khả dụng', 'error'], timeout: ['Chưa nhận phản hồi', 'pending'], 'not-found': ['', ''], cleanup: ['', ''],
    };
    const [text, style] = badges[state] || ['', ''];
    badge.textContent = text; badge.className = `badge ${style}`; badge.hidden = !text;
    root.querySelector('#delete-active').hidden = !activeId;
    renderContent(); renderComposer();
  }

  function messageMarkup(message) {
    const actions = message.role === 'assistant' ? `<div class="message-actions"><button class="icon-button" data-copy-message="${esc(message.id)}" aria-label="Sao chép câu trả lời">${icon('copy')}</button><button class="icon-button" data-vote="up" data-message-id="${esc(message.id)}" aria-label="Đánh giá câu trả lời hữu ích" ${voted.has(message.id) ? 'disabled' : ''}>${icon('up')}</button><button class="icon-button" data-vote="down" data-message-id="${esc(message.id)}" aria-label="Đánh giá câu trả lời chưa hữu ích" ${voted.has(message.id) ? 'disabled' : ''}>${icon('down')}</button>${voted.has(message.id) ? '<span class="vote-status">Đã ghi nhận phản hồi</span>' : ''}</div>` : '';
    return `<article class="message ${message.role}" aria-label="${message.role === 'user' ? 'Tin nhắn của bạn' : 'Câu trả lời của trợ lý'}"><span class="avatar" aria-hidden="true">${icon('spark')}</span><div class="message-content"><p class="message-label">${message.role === 'user' ? 'Bạn' : 'CV RAG AI'}</p><div class="message-text">${esc(message.content)}</div>${actions}</div></article>`;
  }

  function welcomeMarkup() {
    return `<section class="welcome"><div class="welcome-mark">${icon('spark')}</div><p class="eyebrow">Trợ lý tuyển dụng của bạn</p><h2>Bắt đầu từ một câu hỏi.</h2><p>Tra cứu kinh nghiệm, kỹ năng trong CV hoặc đưa ra JD để tìm ứng viên phù hợp.</p><div class="suggestions"><button class="suggestion" data-question="Ứng viên nào biết Python và SQL?">${icon('search')}<span>Tìm ứng viên theo kỹ năng</span></button><button class="suggestion" data-question="Liệt kê các ứng viên mới nhất.">${icon('users')}<span>Xem các CV mới tiếp nhận</span></button><button class="suggestion" data-question="Tìm 3 ứng viên Data Engineer, biết Python và SQL, tối thiểu 1 năm kinh nghiệm.">${icon('file')}<span>Tìm ứng viên theo JD</span></button></div><p class="privacy-note">${icon('lock')}Hội thoại được lưu riêng theo tài khoản của bạn.</p></section>`;
  }

  function criteriaMarkup(item, index) {
    const c = criteriaDrafts.get(item.confirmation_id) || item.criteria, id = item.confirmation_id;
    return `<section class="criteria-card" data-confirmation="${esc(id)}"><header>${icon('file')}<div><h2>Kiểm tra tiêu chí tuyển dụng</h2><p>Xác nhận hoặc chỉnh lại trước khi tìm ứng viên.</p></div>${pending.length > 1 ? `<span class="badge">${index + 1} / ${pending.length}</span>` : ''}</header><form class="criteria-form" data-confirmation-id="${esc(id)}"><fieldset ${busy ? 'disabled' : ''}><legend class="sr-only">Tiêu chí cho ${esc(c.position_title)}</legend><div class="field"><label for="title-${id}">Vị trí tuyển dụng</label><input id="title-${id}" name="position_title" maxlength="500" value="${esc(c.position_title)}" required></div><div class="field"><label id="skills-label-${id}" for="skill-${id}">Kỹ năng yêu cầu</label><div class="skill-list" data-skills="${id}" aria-labelledby="skills-label-${id}">${skillMarkup(c.required_skills)}</div><div class="skill-input-row"><input id="skill-${id}" data-new-skill placeholder="Thêm kỹ năng, ví dụ: Docker" maxlength="200"><button type="button" class="btn compact" data-add-skill>${icon('plus')}Thêm</button></div><small>Tối đa 100 kỹ năng. Xóa kỹ năng bằng nút × bên cạnh.</small><p class="field-error" data-skill-error role="status"></p></div><div class="field-row"><div class="field"><label for="years-${id}">Kinh nghiệm tối thiểu</label><input id="years-${id}" name="min_years_experience" type="number" min="0" step="any" value="${c.min_years_experience === null ? '' : esc(c.min_years_experience)}" placeholder="Không yêu cầu"><small>Đơn vị: năm. Để trống nếu không yêu cầu.</small></div><div class="field"><label for="topk-${id}">Số ứng viên (Top-K)</label><input id="topk-${id}" name="top_k" type="number" min="1" max="10" step="1" value="${esc(c.top_k)}" required><small>Từ 1 đến 10 ứng viên.</small></div></div><div class="field"><label for="education-${id}">Học vấn ưu tiên <span class="muted">(không bắt buộc)</span></label><textarea id="education-${id}" name="preferred_education" maxlength="1000" rows="2" placeholder="Ví dụ: Công nghệ thông tin hoặc tương đương">${esc(c.preferred_education || '')}</textarea></div><p class="criteria-help">${icon('info')}Bạn có thể để trống kinh nghiệm và học vấn. Những trường còn lại sẽ giữ nguyên nếu không sửa.</p><p class="field-error" data-form-error role="alert"></p><div class="criteria-actions"><button type="button" class="btn" data-cancel-confirmation>Hủy yêu cầu</button><button type="submit" class="btn primary">${busy ? '<span class="spinner" aria-hidden="true"></span>Đang xử lý…' : `${icon('search')}Xác nhận và tìm kiếm`}</button></div></fieldset></form></section>`;
  }

  function skillMarkup(skills) {
    return skills.map((skill, index) => `<span class="skill-chip"><span>${esc(skill)}</span><button type="button" data-remove-skill="${index}" aria-label="Xóa kỹ năng ${esc(skill)}">×</button></span>`).join('');
  }

  function panelMarkup(kind, title, description, actions = '', reference = true) {
    return `<section class="status-panel ${kind}"><div class="status-heading">${icon(kind === 'error' ? 'alert' : 'info')}<h2>${esc(title)}</h2></div><p>${esc(description)}</p>${actions ? `<div class="status-actions">${actions}</div>` : ''}${reference ? `<div class="request-reference"><span>Mã hỗ trợ:</span><code>${requestId}</code><button class="icon-button" data-copy-request aria-label="Sao chép mã hỗ trợ">${icon('copy')}</button></div>` : ''}</section>`;
  }

  function renderContent() {
    let html = messages.map(messageMarkup).join('');
    if (state === 'empty' || state === 'cleanup') html = welcomeMarkup();
    if (cleanupId) html = `<section class="notice warning">${icon('info')}<div><strong>Hội thoại đã được ẩn.</strong><p>Việc dọn dữ liệu chưa hoàn tất. Bạn có thể thử lại để hoàn tất việc xóa.</p><button class="btn compact" id="retry-cleanup" style="margin-top:10px">${icon('refresh')}Thử hoàn tất xóa</button></div></section>` + html;
    if (state === 'not-found') html = panelMarkup('warning', 'Không mở được hội thoại', 'Hội thoại này không còn tồn tại hoặc tài khoản của bạn không có quyền truy cập.', '<button class="btn primary" data-new-panel>Tạo cuộc trò chuyện mới</button>');
    if (state === 'loading') html = '<div class="loading-block" role="status" aria-label="Đang tải lịch sử hội thoại"><div class="skeleton short"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
    if (pending.length) {
      html += `<p class="result-note small muted">${pending.length > 1 ? `Có ${pending.length} yêu cầu xác nhận. Xử lý từng yêu cầu để tiếp tục.` : 'JD đã được trích xuất. Vui lòng kiểm tra các tiêu chí bên dưới.'}</p>`;
      if (state === 'stale') html += panelMarkup('warning', 'Tiêu chí đã thay đổi', 'Yêu cầu xác nhận vừa chọn không còn hiệu lực. Hãy tải lại tiêu chí và kiểm tra trước khi quyết định.', '<button class="btn" id="refresh-criteria">Tải lại tiêu chí</button>');
      html += pending.map(criteriaMarkup).join('');
    }
    if (state === 'running' || busy) html += `<section class="notice">${busy ? '<span class="spinner" aria-hidden="true"></span>' : icon('spark')}<div><strong>Đang xử lý yêu cầu</strong><p>Trợ lý đang làm việc với dữ liệu CV. Bạn có thể kiểm tra lại trạng thái nếu chờ lâu.</p>${!busy ? '<button class="btn compact" id="check-progress" style="margin-top:10px">Kiểm tra trạng thái</button>' : ''}</div></section>`;
    if (state === 'failed' || state === 'interrupted') html += panelMarkup('error', state === 'failed' ? 'Lượt xử lý chưa hoàn tất' : 'Lượt xử lý đã bị gián đoạn', 'Lịch sử đã ghi nhận vẫn được giữ lại. Hãy tạo hội thoại mới để tiếp tục yêu cầu này.', '<button class="btn primary" data-new-panel>Tạo hội thoại mới</button>');
    if (state === 'unavailable') html += panelMarkup('error', 'Dịch vụ tạm thời không khả dụng', 'Chưa thể hoàn tất yêu cầu. Hãy kiểm tra trạng thái hội thoại trước khi thực hiện bước tiếp theo.', '<button class="btn" id="check-failure">Kiểm tra trạng thái</button><button class="btn primary" data-new-panel>Tạo hội thoại mới</button>');
    if (state === 'timeout' || state === 'recovering') html += panelMarkup('warning', state === 'timeout' ? 'Chưa nhận được phản hồi' : 'Cần kiểm tra lại trạng thái', 'Yêu cầu có thể vẫn đang được xử lý. Kiểm tra lại hội thoại để xem kết quả, không cần gửi lại câu hỏi.', '<button class="btn primary" id="check-recovery">Kiểm tra trạng thái hội thoại</button>');
    root.querySelector('#chat-content').innerHTML = html;
    root.querySelectorAll('[data-new-panel]').forEach(button => button.addEventListener('click', newChat));
    root.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
      draft = button.dataset.question;
      root.querySelector('#question').value = draft;
      renderComposer(); root.querySelector('#question').focus();
    }));
    root.querySelectorAll('[data-copy-message]').forEach(button => button.addEventListener('click', () => copy(messages.find(message => message.id === button.dataset.copyMessage).content)));
    root.querySelectorAll('[data-copy-request]').forEach(button => button.addEventListener('click', () => copy(requestId)));
    root.querySelectorAll('[data-vote]').forEach(button => button.addEventListener('click', () => {
      if (voted.has(button.dataset.messageId)) return;
      voted.add(button.dataset.messageId);
      lastAction = {type: 'feedback', message_id: button.dataset.messageId, feedback: button.dataset.vote};
      renderContent(); toast('Đã ghi nhận phản hồi. Cảm ơn bạn!');
    }));
    root.querySelectorAll('.criteria-form').forEach(bindCriteria);
    const refreshCriteria = root.querySelector('#refresh-criteria');
    if (refreshCriteria) {
      root.querySelectorAll('.criteria-form fieldset').forEach(fieldset => { fieldset.disabled = true; });
      refreshCriteria.addEventListener('click', () => {
        pending[0] = {confirmation_id: generatedId().replaceAll('-', ''), criteria: {...structuredClone(defaults), required_skills: ['Python', 'SQL', 'Docker']}};
        state = 'pending'; setUrlState(); renderAll(); announce('Đã tải lại tiêu chí. Vui lòng kiểm tra trước khi xác nhận.');
      });
    }
    root.querySelector('#check-progress')?.addEventListener('click', () => {
      lastAction = {type: 'get_history', thread_id: activeId};
      state = 'answer'; messages.push({id: generatedId(), role: 'assistant', content: 'Đã hoàn tất yêu cầu tra cứu. Bạn có thể tiếp tục hỏi về kỹ năng hoặc cung cấp JD để tìm ứng viên theo tiêu chí cụ thể.'});
      setUrlState(); renderAll(); announce('Đã có câu trả lời.');
    });
    root.querySelector('#check-recovery')?.addEventListener('click', () => {
      lastAction = {type: 'get_history', thread_id: activeId}; state = 'running'; setUrlState(); renderAll(); announce('Hội thoại vẫn đang được xử lý.');
    });
    root.querySelector('#check-failure')?.addEventListener('click', () => {
      lastAction = {type: 'get_history', thread_id: activeId}; state = 'failed'; setUrlState(); renderAll();
    });
    root.querySelector('#retry-cleanup')?.addEventListener('click', () => {
      lastAction = {type: 'delete', thread_id: cleanupId}; cleanupId = null; state = 'empty'; setUrlState(); renderAll(); toast('Đã hoàn tất xóa hội thoại.');
    });
  }

  function renderComposer() {
    const allowed = !busy && ['empty', 'answer', 'cleanup'].includes(state) && page !== 'forbidden';
    const input = root.querySelector('#question');
    input.disabled = !allowed;
    root.querySelector('#composer-form').hidden = !allowed;
    root.querySelector('#question-help').hidden = !allowed;
    root.querySelector('#composer-area').classList.toggle('compact', !allowed);
    root.querySelector('#send-message').disabled = !allowed || !draft.trim();
    root.querySelector('#composer-box').classList.toggle('disabled', !allowed);
    root.querySelector('#question-count').textContent = `${input.value.length.toLocaleString('vi-VN')} / 20.000 ký tự`;
    const guard = root.querySelector('#composer-guard');
    let text = '';
    if (pending.length) text = 'Xác nhận hoặc hủy các tiêu chí JD trước khi gửi câu hỏi mới.';
    else if (busy || state === 'running') text = 'Yêu cầu đang được xử lý. Bạn có thể đọc lịch sử trong lúc chờ.';
    else if (['failed', 'interrupted'].includes(state)) text = 'Hãy bắt đầu một hội thoại mới để tiếp tục.';
    else if (['timeout', 'recovering', 'unavailable'].includes(state)) text = 'Kiểm tra trạng thái để khôi phục kết quả trước khi gửi tiếp.';
    guard.innerHTML = `${icon('info')}<span>${esc(text)}</span>`; guard.hidden = !text;
    root.querySelector('#composer-area').hidden = !allowed && !text;
  }

  function bindCriteria(form) {
    const item = pending.find(candidate => candidate.confirmation_id === form.dataset.confirmationId);
    let skills = [...(criteriaDrafts.get(item.confirmation_id) || item.criteria).required_skills];
    function saveDraft() {
      const field = form.elements;
      criteriaDrafts.set(item.confirmation_id, {
        position_title: field.position_title.value,
        required_skills: [...skills],
        min_years_experience: field.min_years_experience.value === '' ? null : Number(field.min_years_experience.value),
        preferred_education: field.preferred_education.value || null,
        top_k: Number(field.top_k.value),
      });
    }
    form.addEventListener('input', saveDraft);
    function redrawSkills() {
      form.querySelector('[data-skills]').innerHTML = skillMarkup(skills);
      form.querySelectorAll('[data-remove-skill]').forEach(button => button.addEventListener('click', () => {
        skills.splice(Number(button.dataset.removeSkill), 1); saveDraft(); redrawSkills();
      }));
    }
    function addSkill() {
      const input = form.querySelector('[data-new-skill]');
      const value = input.value.trim();
      const error = form.querySelector('[data-skill-error]');
      error.textContent = '';
      if (!value) { error.textContent = 'Nhập tên kỹ năng trước khi thêm.'; return; }
      if (skills.length >= 100 || value.length > 200) { error.textContent = 'Tối đa 100 kỹ năng, mỗi kỹ năng không quá 200 ký tự.'; return; }
      if (skills.some(skill => skill.toLocaleLowerCase() === value.toLocaleLowerCase())) { error.textContent = 'Kỹ năng này đã có trong danh sách.'; return; }
      skills.push(value); input.value = ''; saveDraft(); redrawSkills(); input.focus();
    }
    redrawSkills();
    form.querySelector('[data-add-skill]').addEventListener('click', addSkill);
    form.querySelector('[data-new-skill]').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.isComposing) { event.preventDefault(); addSkill(); }
    });
    form.querySelector('[data-cancel-confirmation]').addEventListener('click', () => runConfirmation(item, false, null));
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (busy || state === 'stale') return;
      const field = form.elements;
      const title = field.position_title.value;
      field.position_title.setCustomValidity(title.trim() ? '' : 'Vui lòng nhập vị trí tuyển dụng.');
      if (!form.reportValidity()) return;
      const values = {
        position_title: title,
        required_skills: skills,
        min_years_experience: field.min_years_experience.value === '' ? null : Number(field.min_years_experience.value),
        preferred_education: field.preferred_education.value.trim() ? field.preferred_education.value : null,
        top_k: Number(field.top_k.value),
      };
      saveDraft();
      const edits = Object.fromEntries(Object.entries(values).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(item.criteria[key])));
      runConfirmation(item, true, Object.keys(edits).length ? edits : null);
    });
    form.elements.position_title.addEventListener('input', () => form.elements.position_title.setCustomValidity(''));
  }

  function runConfirmation(item, confirmed, edits) {
    if (busy || state === 'stale') return;
    busy = true;
    lastAction = {type: 'resume', thread_id: activeId, confirmation_id: item.confirmation_id, confirmed, edited_criteria: edits};
    const version = ++actionVersion;
    renderAll(); announce(confirmed ? 'Đang tìm kiếm theo tiêu chí đã xác nhận.' : 'Đang hủy yêu cầu.');
    setTimeout(() => {
      if (version !== actionVersion) return;
      busy = false;
      pending = pending.filter(candidate => candidate.confirmation_id !== item.confirmation_id);
      criteriaDrafts.delete(item.confirmation_id);
      if (pending.length) state = pending.length > 1 ? 'multiple' : 'pending';
      else {
        state = 'answer';
        messages.push({id: generatedId(), role: 'assistant', content: confirmed ? `Đã tìm kiếm theo tiêu chí ${edits?.position_title || item.criteria.position_title}. Chưa có đủ dữ liệu để kết luận ứng viên phù hợp. Bạn có thể điều chỉnh JD trong một yêu cầu mới.` : 'Đã hủy yêu cầu tìm ứng viên theo tiêu chí này.'});
      }
      const current = conversations.find(candidate => candidate.id === activeId);
      if (current) { current.state = state; current.label = pending.length ? 'Đang chờ xác nhận' : 'Gần đây'; }
      setUrlState(); renderAll(); announce(pending.length ? 'Còn yêu cầu cần xác nhận.' : 'Đã xử lý yêu cầu.');
    }, 600);
  }

  function sendMessage(event) {
    event.preventDefault();
    const question = root.querySelector('#question').value;
    if (busy || !['empty', 'answer', 'cleanup'].includes(state) || !question.trim() || question.length > 20000) return;
    if (!activeId) {
      activeId = generatedId();
      conversations.unshift({id: activeId, title: question.trim().slice(0, 40), state: 'answer', label: 'Vừa tạo'});
    }
    messages.push({id: generatedId(), role: 'user', content: question});
    lastAction = {type: 'ask', thread_id: activeId, question};
    busy = true; draft = ''; root.querySelector('#question').value = '';
    const version = ++actionVersion;
    renderAll(); announce('Đang xử lý câu hỏi.');
    setTimeout(() => {
      if (version !== actionVersion) return;
      busy = false;
      if (/\bjd\b|mô tả công việc|tìm.*data engineer/i.test(question)) {
        pending = [{confirmation_id: generatedId().replaceAll('-', ''), criteria: structuredClone(defaults)}];
        state = 'pending';
      } else {
        state = 'answer';
        messages.push({id: generatedId(), role: 'assistant', content: 'Bạn có thể tra cứu kỹ năng và kinh nghiệm trong CV, hoặc cung cấp JD để tìm ứng viên theo tiêu chí cụ thể. Hãy kiểm tra thông tin hồ sơ trước khi lựa chọn ứng viên.'});
      }
      const current = conversations.find(candidate => candidate.id === activeId);
      if (current) { current.state = state; current.label = pending.length ? 'Đang chờ xác nhận' : 'Gần đây'; }
      setUrlState(); renderAll(); announce(pending.length ? 'Có tiêu chí JD cần xác nhận.' : 'Đã có câu trả lời.');
      const scroll = root.querySelector('#main-content'); scroll.scrollTop = scroll.scrollHeight;
    }, 650);
  }

  function renderForbidden() {
    renderSidebar();
    root.querySelector('#chat-title').textContent = 'Quyền truy cập';
    root.querySelector('#chat-subtitle').textContent = user.scope;
    root.querySelector('#status-badge').hidden = true;
    root.querySelector('#delete-active').hidden = true;
    root.querySelector('#composer-area').hidden = true;
    root.querySelector('#main-content').style.display = 'flex';
    root.querySelector('#chat-content').innerHTML = `<section class="forbidden-content"><div class="welcome-mark">${icon('lock')}</div><p class="eyebrow">Không đủ quyền</p><h2>Bạn không có quyền truy cập khu vực này.</h2><p>Quyền của tài khoản hiện tại chưa cho phép thực hiện thao tác này. Bạn có thể quay lại không gian hỏi đáp để tiếp tục làm việc.</p><div class="notice">${icon('info')}<div><strong>${esc(user.username)} · ${esc(user.label)}</strong><p>${esc(user.scope)}</p></div></div><div class="status-actions"><a class="btn primary" href="${esc(href('chat', {state: 'empty'}))}">${icon('back')}Quay lại hỏi đáp AI</a><a class="btn" href="${esc(href('login'))}">Đăng nhập tài khoản khác</a></div><div class="request-reference"><span>Mã hỗ trợ:</span><code>${requestId}</code><button class="icon-button" id="copy-forbidden" aria-label="Sao chép mã hỗ trợ">${icon('copy')}</button></div></section>`;
    root.querySelector('#copy-forbidden').addEventListener('click', () => copy(requestId));
  }

  function renderLogin() {
    const modes = new Set(['error', 'unavailable', 'expired', 'pending', 'signed-out']);
    const mode = modes.has(params.get('mode')) ? params.get('mode') : 'default';
    const notices = {
      error: ['error', 'Chưa thể đăng nhập', 'Thông tin đăng nhập không hợp lệ hoặc tài khoản đang tạm khóa.'],
      unavailable: ['error', 'Dịch vụ tạm thời không khả dụng', 'Vui lòng thử lại sau. Nếu lỗi tiếp diễn, hãy liên hệ người quản trị.'],
      expired: ['warning', 'Phiên đăng nhập đã kết thúc', 'Vui lòng đăng nhập lại để tiếp tục. Lịch sử hội thoại đã lưu vẫn được giữ.'],
      'signed-out': ['success', 'Đã đăng xuất', 'Bạn có thể đăng nhập lại bằng tài khoản được cấp.'],
    };
    const notice = notices[mode];
    root.innerHTML = `<main class="login-page"><div class="login-wrap"><section class="login-card" aria-labelledby="login-title"><a class="brand" href="${paths.gallery}" aria-label="CV RAG AI — Bản xem trước">${brand}</a><h1 id="login-title">Đăng nhập hệ thống</h1><p class="login-description">Không gian tra cứu CV và hỗ trợ tuyển dụng dành cho đội ngũ của bạn.</p><div id="login-notice" ${notice ? '' : 'hidden'} class="notice ${notice?.[0] || ''}" role="${notice?.[0] === 'error' ? 'alert' : 'status'}">${icon('info')}<div><strong id="login-notice-title">${esc(notice?.[1])}</strong><p id="login-notice-text">${esc(notice?.[2])}</p></div></div><form id="login-form" class="login-form"><div class="field"><label for="username">Tên đăng nhập</label><input id="username" name="username" type="text" autocomplete="username" maxlength="100" placeholder="Tên tài khoản được cấp" required ${mode === 'pending' ? 'disabled' : ''}></div><div class="field"><label for="password">Mật khẩu</label><div class="password-wrap"><input id="password" name="password" type="password" autocomplete="current-password" maxlength="256" required aria-describedby="password-help" ${mode === 'pending' ? 'disabled' : ''}><button class="icon-button" id="toggle-password" type="button" aria-label="Hiện mật khẩu" aria-pressed="false">${icon('eye')}</button></div><small id="password-help">Nhập mật khẩu của tài khoản được cấp.</small></div><button class="btn primary full" id="login-submit" type="submit" ${mode === 'pending' ? 'disabled' : ''}>${mode === 'pending' ? '<span class="spinner" aria-hidden="true"></span>Đang đăng nhập…' : `Đăng nhập${icon('arrow')}`}</button></form><div class="login-support"><p class="small muted">Tài khoản do quản trị viên cấp. Liên hệ người quản trị nếu bạn chưa có tài khoản hoặc cần đặt lại mật khẩu.</p></div></section><p class="login-caption">Bản xem trước thiết kế · Dùng thông tin mẫu để thử.<br><a href="${paths.gallery}">Xem các màn hình và trạng thái</a></p></div></main>${globalHelpers}`;
    const input = root.querySelector('#password');
    const toggle = root.querySelector('#toggle-password');
    toggle.addEventListener('click', () => {
      const reveal = input.type === 'password'; input.type = reveal ? 'text' : 'password';
      toggle.setAttribute('aria-label', reveal ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
      toggle.setAttribute('aria-pressed', String(reveal)); toggle.innerHTML = icon(reveal ? 'eyeOff' : 'eye');
    });
    const form = root.querySelector('#login-form');
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (form.dataset.submitting === 'true') return;
      const username = form.elements.username.value.trim();
      if (!username || !input.value) return;
      form.dataset.submitting = 'true';
      const submit = root.querySelector('#login-submit');
      submit.disabled = true; submit.innerHTML = '<span class="spinner" aria-hidden="true"></span>Đang đăng nhập…';
      form.elements.username.disabled = true; input.disabled = true;
      setTimeout(() => {
        input.value = '';
        if (mode === 'error' || mode === 'unavailable') {
          form.dataset.submitting = 'false'; submit.disabled = false; submit.innerHTML = `Đăng nhập${icon('arrow')}`;
          form.elements.username.disabled = false; input.disabled = false; input.focus();
          announce('Chưa thể đăng nhập. Kiểm tra thông báo phía trên.');
        } else {
          const previewRole = username.toLowerCase().startsWith('tester') ? 'tester' : role;
          location.assign(href('chat', {state: 'empty', role: previewRole}));
        }
      }, 550);
    });
  }
})();
