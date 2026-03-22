const state = {
  accessToken: sessionStorage.getItem('assistantDemoAccessToken') || '',
  userLogin: sessionStorage.getItem('assistantDemoUserLogin') || '',
  userId: sessionStorage.getItem('assistantDemoUserId') || '',
  sessionId: sessionStorage.getItem('assistantDemoSessionId') || crypto.randomUUID(),
  voiceEnabled: sessionStorage.getItem('assistantDemoVoiceEnabled') !== '0',
  catalogMode: 'feed',
  catalogPage: 1,
  catalogPageSize: Number(sessionStorage.getItem('assistantDemoCatalogPageSize') || '24'),
  catalogGenre: '',
  catalogQuery: '',
  catalogHasNextPage: false,
  lastRepeatableQuery: '',
};
sessionStorage.setItem('assistantDemoSessionId', state.sessionId);

const elements = {
  searchForm: document.getElementById('search-form'),
  searchInput: document.getElementById('search-input'),
  searchSubmitBtn: document.getElementById('search-submit-btn'),
  catalogResults: document.getElementById('catalog-results'),
  catalogMeta: document.getElementById('catalog-meta'),
  catalogTitle: document.getElementById('catalog-title'),
  catalogSubtitle: document.getElementById('catalog-subtitle'),
  catalogModeChip: document.getElementById('catalog-mode-chip'),
  catalogResetBtn: document.getElementById('catalog-reset-btn'),
  catalogGenreSelect: document.getElementById('catalog-genre-select'),
  catalogPageSizeSelect: document.getElementById('catalog-page-size-select'),
  catalogPrevBtn: document.getElementById('catalog-prev-btn'),
  catalogNextBtn: document.getElementById('catalog-next-btn'),
  catalogPageInfo: document.getElementById('catalog-page-info'),
  userStatus: document.getElementById('user-status'),
  loginOpenBtn: document.getElementById('login-open-btn'),
  logoutBtn: document.getElementById('logout-btn'),
  loginModal: document.getElementById('login-modal'),
  loginCloseBtn: document.getElementById('login-close-btn'),
  loginForm: document.getElementById('login-form'),
  loginInput: document.getElementById('login-input'),
  passwordInput: document.getElementById('password-input'),
  loginError: document.getElementById('login-error'),
  talkBtn: document.getElementById('talk-btn'),
  assistantQuery: document.getElementById('assistant-query'),
  assistantAskBtn: document.getElementById('assistant-ask-btn'),
  assistantRepeatBtn: document.getElementById('assistant-repeat-btn'),
  assistantStatus: document.getElementById('assistant-status'),
  transcriptOutput: document.getElementById('transcript-output'),
  assistantAnswer: document.getElementById('assistant-answer'),
  assistantResult: document.getElementById('assistant-result'),
  exampleChips: document.getElementById('example-chips'),
  voiceToggle: document.getElementById('voice-toggle'),
  personalSection: document.getElementById('personal-section'),
  personalStatus: document.getElementById('personal-status'),
  personalBookmarks: document.getElementById('personal-bookmarks'),
  personalLikes: document.getElementById('personal-likes'),
};

async function loadDemoConfig() {
  try {
    const response = await fetch('./demo-config.json', { credentials: 'same-origin' });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    renderExampleButtons(payload.assistantExamples || []);
  } catch {
    // noop
  }
}

function renderExampleButtons(items) {
  elements.exampleChips.innerHTML = '';
  items.forEach((query) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'example-chip';
    button.dataset.exampleQuery = query;
    button.textContent = query;
    button.addEventListener('click', () => {
      elements.assistantQuery.value = query;
      setTranscript(query);
      updateActionButtons();
      elements.assistantQuery.focus();
    });
    elements.exampleChips.appendChild(button);
  });
}

function setUserUi() {
  const loggedIn = Boolean(state.accessToken);
  elements.userStatus.textContent = loggedIn ? `Пользователь: ${state.userLogin}` : 'Гость';
  elements.loginOpenBtn.classList.toggle('hidden', loggedIn);
  elements.logoutBtn.classList.toggle('hidden', !loggedIn);
  elements.personalSection.classList.toggle('hidden', !loggedIn);
  if (elements.voiceToggle) {
    elements.voiceToggle.checked = state.voiceEnabled;
  }
}

function setAssistantStatus(text) {
  elements.assistantStatus.textContent = text;
}

function setTranscript(text) {
  elements.transcriptOutput.textContent = text || 'Пока нет распознанного текста.';
}

function setAnswer(text) {
  elements.assistantAnswer.textContent = text || 'Пока нет ответа.';
}

function setCatalogMode(mode, metaText = '') {
  state.catalogMode = mode;
  const isSearch = mode === 'search';
  elements.catalogTitle.textContent = 'Каталог';
  elements.catalogSubtitle.textContent = isSearch
    ? 'Режим поиска по каталогу с постраничной навигацией. Жанровый фильтр доступен в обычном режиме каталога.'
    : 'Полноценный просмотр каталога по страницам. Можно листать дальше и фильтровать по жанрам.';
  elements.catalogModeChip.textContent = isSearch ? 'Результаты поиска' : 'Каталог по страницам';
  elements.catalogMeta.textContent = metaText || (isSearch ? 'Показываю результаты поиска.' : 'Показываю каталог.');
  updateCatalogControls();
}

function setRepeatableQuery(query, enabled) {
  state.lastRepeatableQuery = enabled ? query : '';
  elements.assistantRepeatBtn.classList.toggle('hidden', !enabled);
}

function clearAuthState() {
  state.accessToken = '';
  state.userLogin = '';
  state.userId = '';
  sessionStorage.removeItem('assistantDemoAccessToken');
  sessionStorage.removeItem('assistantDemoUserLogin');
  sessionStorage.removeItem('assistantDemoUserId');
  setUserUi();
}

async function bootstrapAuthState() {
  if (!state.accessToken) {
    setUserUi();
    return null;
  }

  try {
    const profile = await apiJson('/api/v1/auth/me', { method: 'GET' });
    state.userId = String(profile?.id || '');
    state.userLogin = profile?.login || state.userLogin;
    sessionStorage.setItem('assistantDemoUserId', state.userId);
    sessionStorage.setItem('assistantDemoUserLogin', state.userLogin);
    setUserUi();
    return profile;
  } catch {
    clearAuthState();
    setAssistantStatus('Сессия истекла. Войдите снова для персональных сценариев.');
    return null;
  }
}

function updateActionButtons() {
  elements.assistantAskBtn.disabled = !elements.assistantQuery.value.trim();
  elements.searchSubmitBtn.disabled = !elements.searchInput.value.trim();
}

function updateCatalogControls() {
  if (elements.catalogPageSizeSelect) {
    elements.catalogPageSizeSelect.value = String(state.catalogPageSize);
  }
  if (elements.catalogGenreSelect) {
    elements.catalogGenreSelect.value = state.catalogGenre;
    elements.catalogGenreSelect.disabled = state.catalogMode === 'search';
  }
  if (elements.catalogPrevBtn) {
    elements.catalogPrevBtn.disabled = state.catalogPage <= 1;
  }
  if (elements.catalogNextBtn) {
    elements.catalogNextBtn.disabled = !state.catalogHasNextPage;
  }
  if (elements.catalogPageInfo) {
    elements.catalogPageInfo.textContent = `Страница ${state.catalogPage}`;
  }

  const shouldShowReset = Boolean(
    state.catalogMode === 'search'
      || state.catalogPage > 1
      || state.catalogGenre
      || elements.searchInput.value.trim(),
  );
  elements.catalogResetBtn.classList.toggle('hidden', !shouldShowReset);
}

function renderCatalogItems(items, emptyText) {
  if (!Array.isArray(items) || items.length === 0) {
    elements.catalogResults.className = 'result-grid empty-state';
    elements.catalogResults.textContent = emptyText;
    return;
  }

  elements.catalogResults.className = 'result-grid';
  elements.catalogResults.innerHTML = items.map(renderMovieCard).join('');
}

function renderMovieCard(item) {
  const genres = Array.isArray(item.genre) && item.genre.length ? item.genre.join(', ') : '—';
  const directors = Array.isArray(item.directors) && item.directors.length ? item.directors.join(', ') : '—';
  const originalTitle = item.original_title ? `<div class="movie-subtitle">${escapeHtml(item.original_title)}</div>` : '';
  const description = item.description ? `<p class="movie-description">${escapeHtml(item.description)}</p>` : '';
  return `
    <article class="movie-card">
      <h3>${escapeHtml(item.title || 'Без названия')}</h3>
      ${originalTitle}
      ${description}
      <dl>
        <dt>Рейтинг</dt><dd>${escapeHtml(String(item.imdb_rating ?? '—'))}</dd>
        <dt>Жанры</dt><dd>${escapeHtml(genres)}</dd>
        <dt>Режиссёр</dt><dd>${escapeHtml(directors)}</dd>
      </dl>
    </article>
  `;
}

function renderSidebarList(target, items, emptyText, extraFormatter = null) {
  if (!Array.isArray(items) || items.length === 0) {
    target.className = 'sidebar-list empty-state';
    target.textContent = emptyText;
    return;
  }

  target.className = 'sidebar-list';
  target.innerHTML = items
    .map((item) => {
      const extra = extraFormatter ? extraFormatter(item) : '';
      return `
        <article class="sidebar-card">
          <div class="sidebar-card-title">${escapeHtml(item.title || 'Без названия')}</div>
          ${item.original_title ? `<div class="sidebar-card-subtitle">${escapeHtml(item.original_title)}</div>` : ''}
          ${extra ? `<div class="sidebar-card-meta">${extra}</div>` : ''}
        </article>
      `;
    })
    .join('');
}

function renderAssistantResult(payload) {
  elements.assistantResult.textContent = JSON.stringify(payload?.result ?? {}, null, 2);
}

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }
  return headers;
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = body?.detail || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

async function login(login, password) {
  const body = await apiJson('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login, password }),
  });

  state.accessToken = body.access_token;
  state.userLogin = login;
  sessionStorage.setItem('assistantDemoAccessToken', state.accessToken);
  sessionStorage.setItem('assistantDemoUserLogin', state.userLogin);
  await bootstrapAuthState();
  setUserUi();
  await refreshPersonalSection();
}

async function searchFilms(query) {
  return apiJson(`/assistant/api/v1/search?query=${encodeURIComponent(query)}`, { method: 'GET' });
}

async function fetchCatalogGenres() {
  return apiJson('/api/v1/genres?page_number=1&page_size=200', { method: 'GET' });
}

async function fetchCatalogPage(pageNumber, pageSize, genreId = '') {
  const params = new URLSearchParams({
    sort: '-imdb_rating',
    page_number: String(pageNumber),
    page_size: String(pageSize),
  });
  if (genreId) {
    params.set('genre', genreId);
  }
  return apiJson(`/api/v1/films?${params.toString()}`, { method: 'GET' });
}

async function searchCatalogPage(query, pageNumber, pageSize) {
  const params = new URLSearchParams({
    query,
    page_number: String(pageNumber),
    page_size: String(pageSize),
  });
  return apiJson(`/api/v1/films/search?${params.toString()}`, { method: 'GET' });
}

async function askAssistant(query) {
  return apiJson('/assistant/api/v1/ask', {
    method: 'POST',
    body: JSON.stringify({ query, session_id: state.sessionId }),
  });
}

async function fetchFilmDetails(filmIds) {
  const ids = [...new Set((filmIds || []).filter(Boolean))];
  const details = await Promise.all(
    ids.map(async (filmId) => {
      try {
        return await apiJson(`/api/v1/films/${encodeURIComponent(filmId)}`, { method: 'GET' });
      } catch {
        return null;
      }
    }),
  );
  return details.filter(Boolean);
}

async function fetchGenreNames(genreIds) {
  const ids = [...new Set((genreIds || []).filter(Boolean))];
  const genres = await Promise.all(
    ids.map(async (genreId) => {
      try {
        return await apiJson(`/api/v1/genres/${encodeURIComponent(genreId)}`, { method: 'GET' });
      } catch {
        return null;
      }
    }),
  );
  return Object.fromEntries(
    genres.filter(Boolean).map((item) => [item.id || item.uuid, item.name]),
  );
}

async function enrichCatalogItems(listItems) {
  const genreNamesById = await fetchGenreNames(
    (listItems || []).flatMap((item) => item.genre || []),
  );

  return (listItems || []).map((item) => ({
    ...item,
    genre: (item.genre || []).map((genreId) => genreNamesById[genreId] || genreId),
    directors: item.directors || [],
  }));
}

async function loadGenreOptions() {
  try {
    const genres = await fetchCatalogGenres();
    const options = ['<option value="">Все жанры</option>']
      .concat(
        (genres || [])
          .map((genre) => ({ uuid: genre.id || genre.uuid, name: genre.name }))
          .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
          .map((genre) => `<option value="${escapeHtml(genre.uuid)}">${escapeHtml(genre.name)}</option>`),
      )
      .join('');
    elements.catalogGenreSelect.innerHTML = options;
    elements.catalogGenreSelect.value = state.catalogGenre;
  } catch {
    const currentOptions = elements.catalogGenreSelect.innerHTML || '';
    if (!currentOptions.trim()) {
      elements.catalogGenreSelect.innerHTML = '<option value="">Все жанры</option>';
    }
  }
}

async function refreshCatalog() {
  const isSearch = state.catalogMode === 'search' && state.catalogQuery.trim();

  try {
    setCatalogMode(isSearch ? 'search' : 'feed', isSearch ? 'Ищу по каталогу…' : 'Загружаю каталог…');

    const pageItems = isSearch
      ? await searchCatalogPage(state.catalogQuery, state.catalogPage, state.catalogPageSize)
      : await fetchCatalogPage(state.catalogPage, state.catalogPageSize, state.catalogGenre);

    if (state.catalogPage > 1 && (!Array.isArray(pageItems) || pageItems.length === 0)) {
      state.catalogPage -= 1;
      state.catalogHasNextPage = false;
      updateCatalogControls();
      return await refreshCatalog();
    }

    state.catalogHasNextPage = Array.isArray(pageItems) && pageItems.length === state.catalogPageSize;
    const items = await enrichCatalogItems(pageItems || []);
    renderCatalogItems(
      items,
      isSearch ? 'Ничего не найдено. Попробуйте другой запрос.' : 'Каталог пока не вернул ни одного фильма.',
    );

    if (isSearch) {
      setCatalogMode(
        'search',
        `Поиск: «${state.catalogQuery}». Страница ${state.catalogPage}, на этой странице ${items.length} фильм(ов).`,
      );
    } else if (state.catalogGenre) {
      const genreName = elements.catalogGenreSelect.options[elements.catalogGenreSelect.selectedIndex]?.text || 'выбранный жанр';
      setCatalogMode(
        'feed',
        `Жанр: ${genreName}. Страница ${state.catalogPage}, на этой странице ${items.length} фильм(ов).`,
      );
    } else {
      setCatalogMode(
        'feed',
        `Каталог: страница ${state.catalogPage}, на этой странице ${items.length} фильм(ов).`,
      );
    }
  } catch (error) {
    state.catalogHasNextPage = false;
    renderCatalogItems([], isSearch ? 'Не удалось выполнить поиск.' : 'Не удалось загрузить каталог.');
    setCatalogMode(isSearch ? 'search' : 'feed', String(error.message || error));
  }
}

async function refreshCatalogFeed() {
  state.catalogMode = 'feed';
  state.catalogQuery = '';
  state.catalogPage = 1;
  await refreshCatalog();
}

async function runCatalogSearch(query) {
  state.catalogMode = 'search';
  state.catalogQuery = query.trim();
  state.catalogPage = 1;
  await refreshCatalog();
}

async function refreshPersonalSection() {
  if (!state.accessToken || !state.userId) {
    renderSidebarList(elements.personalBookmarks, [], 'Войдите, чтобы видеть закладки.');
    renderSidebarList(elements.personalLikes, [], 'Войдите, чтобы видеть лайки.');
    elements.personalStatus.textContent = 'Скрыто';
    return;
  }

  try {
    elements.personalStatus.textContent = 'Обновляется…';
    const [bookmarks, likes] = await Promise.all([
      apiJson(`/ugc/api/v1/bookmarks/by-user?user_id=${encodeURIComponent(state.userId)}&limit=8&offset=0`, { method: 'GET' }),
      apiJson(`/ugc/api/v1/likes/by-user?user_id=${encodeURIComponent(state.userId)}&limit=8&offset=0`, { method: 'GET' }),
    ]);

    const bookmarkDetails = await fetchFilmDetails(bookmarks.map((item) => item.film_id));
    const likeDetails = await fetchFilmDetails(likes.map((item) => item.film_id));
    const likeValueById = Object.fromEntries(likes.map((item) => [item.film_id, item.value]));

    renderSidebarList(
      elements.personalBookmarks,
      bookmarkDetails,
      'У вас пока нет закладок.',
      (item) => `Рейтинг: ${escapeHtml(String(item.imdb_rating ?? '—'))}`,
    );
    renderSidebarList(
      elements.personalLikes,
      likeDetails,
      'У вас пока нет лайков.',
      (item) => `Ваша оценка: ${escapeHtml(String(likeValueById[item.uuid] ?? '—'))}`,
    );
    elements.personalStatus.textContent = 'Обновлено';
  } catch {
    elements.personalStatus.textContent = 'Ошибка';
    renderSidebarList(elements.personalBookmarks, [], 'Не удалось загрузить закладки.');
    renderSidebarList(elements.personalLikes, [], 'Не удалось загрузить лайки.');
  }
}

function speak(text) {
  if (!state.voiceEnabled || !('speechSynthesis' in window) || !text) {
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'ru-RU';
  window.speechSynthesis.speak(utterance);
}

function openLoginModal() {
  elements.loginModal.classList.remove('hidden');
  elements.loginError.textContent = '';
  setTimeout(() => elements.loginInput.focus(), 30);
}

function closeLoginModal() {
  elements.loginModal.classList.add('hidden');
}

function logout() {
  clearAuthState();
  window.speechSynthesis?.cancel?.();
  void refreshPersonalSection();
}

function attachSpeechRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    elements.talkBtn.textContent = '🎤 Голосовой ввод не поддерживается';
    elements.talkBtn.disabled = true;
    return;
  }

  const recognition = new Recognition();
  recognition.lang = 'ru-RU';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.addEventListener('start', () => setAssistantStatus('Слушаю...'));
  recognition.addEventListener('result', async (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript?.trim() || '';
    if (!transcript) {
      setAssistantStatus('Речь не распознана');
      return;
    }
    setTranscript(transcript);
    elements.assistantQuery.value = transcript;
    updateActionButtons();
    await runAssistantQuery(transcript);
  });
  recognition.addEventListener('error', (event) => {
    setAssistantStatus(`Ошибка голосового ввода: ${event.error}`);
  });
  recognition.addEventListener('end', () => {
    if (elements.assistantStatus.textContent === 'Слушаю...') {
      setAssistantStatus('Готов');
    }
  });

  elements.talkBtn.addEventListener('click', () => recognition.start());
}

async function runAssistantQuery(query) {
  if (!query?.trim()) {
    setAssistantStatus('Сначала введите вопрос или нажмите кнопку микрофона.');
    return;
  }

  try {
    setAssistantStatus('Ищу ответ...');
    const payload = await askAssistant(query.trim());
    setAnswer(payload.answer_text || payload.answer || 'Нет ответа');
    renderAssistantResult(payload);
    setAssistantStatus(payload.requires_auth ? 'Нужна авторизация' : 'Готово');
    speak(payload.speak_text || payload.answer_text || payload.answer || '');
    const repeatable = Boolean(payload?.result?.can_repeat || payload?.metadata?.can_repeat);
    setRepeatableQuery(query.trim(), repeatable);
  } catch (error) {
    const message = String(error.message || error);
    if (/token expired|invalid bearer token/i.test(message)) {
      clearAuthState();
      setAnswer('Сессия истекла. Войдите снова для персональных сценариев.');
      setAssistantStatus('Нужна авторизация');
      renderAssistantResult({});
      setRepeatableQuery('', false);
      void refreshPersonalSection();
      return;
    }
    setAnswer(message);
    renderAssistantResult({});
    setAssistantStatus('Ошибка');
    setRepeatableQuery('', false);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function bindUi() {
  await bootstrapAuthState();
  attachSpeechRecognition();
  updateActionButtons();
  await loadDemoConfig();
  await loadGenreOptions();
  await refreshCatalog();
  updateCatalogControls();
  await refreshPersonalSection();

  elements.loginOpenBtn.addEventListener('click', openLoginModal);
  elements.loginCloseBtn.addEventListener('click', closeLoginModal);
  elements.logoutBtn.addEventListener('click', logout);
  elements.catalogResetBtn.addEventListener('click', async () => {
    elements.searchInput.value = '';
    state.catalogGenre = '';
    state.catalogPage = 1;
    updateActionButtons();
    await refreshCatalogFeed();
  });
  elements.catalogPrevBtn.addEventListener('click', async () => {
    if (state.catalogPage <= 1) {
      return;
    }
    state.catalogPage -= 1;
    await refreshCatalog();
  });
  elements.catalogNextBtn.addEventListener('click', async () => {
    if (!state.catalogHasNextPage) {
      return;
    }
    state.catalogPage += 1;
    await refreshCatalog();
  });
  elements.catalogPageSizeSelect.addEventListener('change', async (event) => {
    state.catalogPageSize = Number(event.target.value || 24);
    sessionStorage.setItem('assistantDemoCatalogPageSize', String(state.catalogPageSize));
    state.catalogPage = 1;
    await refreshCatalog();
  });
  elements.catalogGenreSelect.addEventListener('change', async (event) => {
    state.catalogGenre = event.target.value || '';
    state.catalogPage = 1;
    if (state.catalogMode === 'search') {
      return;
    }
    await refreshCatalog();
  });
  elements.assistantRepeatBtn.addEventListener('click', async () => {
    if (state.lastRepeatableQuery) {
      await runAssistantQuery(state.lastRepeatableQuery);
    }
  });
  elements.loginModal.addEventListener('click', (event) => {
    if (event.target === elements.loginModal) {
      closeLoginModal();
    }
  });

  elements.loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    elements.loginError.textContent = '';
    try {
      await login(elements.loginInput.value.trim(), elements.passwordInput.value);
      closeLoginModal();
    } catch (error) {
      elements.loginError.textContent = String(error.message || error);
    }
  });

  elements.searchInput.addEventListener('input', async () => {
    updateActionButtons();
    if (!elements.searchInput.value.trim() && state.catalogMode === 'search') {
      await refreshCatalogFeed();
    }
  });
  elements.assistantQuery.addEventListener('input', updateActionButtons);
  elements.voiceToggle?.addEventListener('change', (event) => {
    state.voiceEnabled = Boolean(event.target.checked);
    sessionStorage.setItem('assistantDemoVoiceEnabled', state.voiceEnabled ? '1' : '0');
    if (!state.voiceEnabled) {
      window.speechSynthesis?.cancel?.();
    }
  });

  elements.searchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = elements.searchInput.value.trim();
    if (!query) {
      await refreshCatalogFeed();
      return;
    }
    await runCatalogSearch(query);
  });

  elements.assistantAskBtn.addEventListener('click', async () => {
    const query = elements.assistantQuery.value.trim();
    setTranscript(query);
    await runAssistantQuery(query);
  });
}

void bindUi();
