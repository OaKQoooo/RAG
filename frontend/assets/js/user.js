const sendButton = document.getElementById('send-message');
const clearButton = document.getElementById('clear-chat');
const composerInput = document.getElementById('composer-input');
const messageStream = document.getElementById('message-stream');
const evidenceStack = document.querySelector('.evidence-stack');
const suggestionRow = document.getElementById('suggestion-row') || document.querySelector('.suggestion-row');
const closeEvidenceButton = document.getElementById('close-evidence-panel');
const exportChatButton = document.getElementById('export-chat-records');
const exportAllRecordsButton = document.getElementById('export-all-records-btn');
const chatWorkspace = document.getElementById('chat-workspace');
const chatSessionPill = document.getElementById('chat-session-pill');
const conversationList = document.getElementById('conversation-list');
const userUploadList = document.getElementById('user-upload-list');
const userDocumentsBody = document.getElementById('user-documents-body');
const currentUserName = document.getElementById('current-user-name');
const profileUsernameInput = document.getElementById('profile-username');
const profilePhoneDisplay = document.getElementById('profile-phone-display');
const themeToggle = document.getElementById('theme-toggle');
const saveProfileButton = document.getElementById('save-profile-btn');
const cancelProfileButton = document.getElementById('cancel-profile-btn');
const profileMessage = document.getElementById('profile-message');
const openPhoneModalButton = document.getElementById('open-phone-modal-btn');
const phoneModal = document.getElementById('phone-modal');
const closePhoneModalButton = document.getElementById('close-phone-modal-btn');
const modalCancelPhoneButton = document.getElementById('modal-cancel-phone-btn');
const modalNextPhoneButton = document.getElementById('modal-next-phone-btn');
const modalBackPhoneButton = document.getElementById('modal-back-phone-btn');
const modalFinishPhoneButton = document.getElementById('modal-finish-phone-btn');
const openPasswordModalButton = document.getElementById('open-password-modal-btn');
const passwordModal = document.getElementById('password-modal');
const closePasswordModalButton = document.getElementById('close-password-modal-btn');
const modalCancelPasswordButton = document.getElementById('modal-cancel-password-btn');
const modalFinishPasswordButton = document.getElementById('modal-finish-password-btn');
const modalOldPasswordInput = document.getElementById('modal-old-password');
const modalNewPasswordInput = document.getElementById('modal-new-password');
const modalConfirmPasswordInput = document.getElementById('modal-confirm-password');
const modalPasswordMessage = document.getElementById('modal-password-message');
const modalCurrentPhone = document.getElementById('modal-current-phone');
const modalOldPhoneCodeInput = document.getElementById('modal-old-phone-code');
const modalNewPhoneInput = document.getElementById('modal-new-phone');
const modalNewPhoneCodeInput = document.getElementById('modal-new-phone-code');
const modalSendOldCodeButton = document.getElementById('modal-send-old-code-btn');
const modalSendNewCodeButton = document.getElementById('modal-send-new-code-btn');
const modalPhoneMessage = document.getElementById('modal-phone-message');
const clearHistoryButton = document.getElementById('clear-history-btn');
const historyMessage = document.getElementById('history-message');
const dataConversationCount = document.getElementById('data-conversation-count');
const dataMessageCount = document.getElementById('data-message-count');
const dataLastConversation = document.getElementById('data-last-conversation');
const dataLatestConversationTitle = document.getElementById('data-latest-conversation-title');
const conversationManageList = document.getElementById('conversation-manage-list');
const selectAllConversationsCheckbox = document.getElementById('select-all-conversations');
const deleteSelectedConversationsButton = document.getElementById('delete-selected-conversations-btn');
const newChatNavButton = document.querySelector('.nav-item[data-view="chat"]');
let activeConversationId = null;
let evidenceEnabled = false;
let latestReferences = [];
let activeEvidenceIndex = 0;
let latestProfile = null;
let recentConversations = [];
const selectedConversationIds = new Set();
let userDocumentPollTimer = null;

if (window.DAM_RAG_LOGIN_REQUIRED || !currentUser()) {
  window.location.href = './index.html';
  throw new Error('Login required');
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderMessageMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\r?\n/g, '<br>');
}

function activeUser() {
  return currentUser();
}

function showSettingsMessage(element, text, type = '') {
  if (!element) return;
  element.textContent = text;
  element.className = `settings-message${type ? ` ${type}` : ''}`;
}

function setText(element, value) {
  if (element) element.textContent = value;
}

function maskPhone(phone = '') {
  const value = String(phone || '');
  if (!/^1[3-9]\d{9}$/.test(value)) return value || '未绑定';
  return `${value.slice(0, 3)}******${value.slice(-2)}`;
}

function refreshStoredUser(profile) {
  const oldUser = currentUser() || {};
  const nextUser = {
    ...oldUser,
    id: profile.id,
    phone: profile.phone,
    username: profile.username,
    role: profile.role,
    status: profile.status,
    avatarUrl: profile.avatarUrl,
    theme: profile.theme
  };
  localStorage.setItem('dam_rag_user', JSON.stringify(nextUser));
}

function applyTheme(theme) {
  const normalized = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = normalized;
}

function renderProfile(profile) {
  if (!profile) return;
  latestProfile = profile;
  if (profileUsernameInput) profileUsernameInput.value = profile.username || '';
  if (profilePhoneDisplay) profilePhoneDisplay.textContent = maskPhone(profile.phone);
  if (themeToggle) themeToggle.checked = profile.theme === 'dark';
  applyTheme(profile.theme);
  if (currentUserName) currentUserName.textContent = profile.username || profile.phone || '未登录';
  if (typeof renderAccountIdentity === 'function') {
    renderAccountIdentity(profile);
  }
}

function validPhone(phone = '') {
  return /^1[3-9]\d{9}$/.test(String(phone || '').trim());
}

async function sendSmsCodeForPhone(phone, scene, targetText) {
  const normalizedPhone = String(phone || '').trim();
  if (!validPhone(normalizedPhone)) {
    showSettingsMessage(modalPhoneMessage, '请输入正确的手机号', 'error');
    return;
  }
  try {
    const data = await requestJson('/auth/sms-code', {
      method: 'POST',
      body: JSON.stringify({ phone: normalizedPhone, scene })
    });
    showSettingsMessage(
      modalPhoneMessage,
      `${targetText}已发送，测试验证码：${data.smsCode}`,
      'success'
    );
  } catch (error) {
    showSettingsMessage(modalPhoneMessage, `验证码发送失败：${error.message}`, 'error');
  }
}

function setPhoneModalStep(step) {
  document.querySelectorAll('.phone-modal-step').forEach((panel) => {
    const shouldShow = panel.dataset.phoneStep === step;
    panel.classList.toggle('hide', !shouldShow);
    panel.hidden = !shouldShow;
  });
  const title = document.getElementById('phone-modal-title');
  if (title) {
    title.textContent = step === 'verify-current' ? '验证当前手机号' : '绑定新手机号';
  }
}

function openPhoneModal() {
  if (!phoneModal) return;
  if (modalCurrentPhone) modalCurrentPhone.textContent = maskPhone(latestProfile?.phone || activeUser().phone);
  if (modalOldPhoneCodeInput) modalOldPhoneCodeInput.value = '';
  if (modalNewPhoneInput) modalNewPhoneInput.value = '';
  if (modalNewPhoneCodeInput) modalNewPhoneCodeInput.value = '';
  showSettingsMessage(modalPhoneMessage, '');
  setPhoneModalStep('verify-current');
  phoneModal.classList.remove('hide');
  modalOldPhoneCodeInput?.focus();
}

function closePhoneModal() {
  phoneModal?.classList.add('hide');
}

function openPasswordModal() {
  if (!passwordModal) return;
  if (modalOldPasswordInput) modalOldPasswordInput.value = '';
  if (modalNewPasswordInput) modalNewPasswordInput.value = '';
  if (modalConfirmPasswordInput) modalConfirmPasswordInput.value = '';
  showSettingsMessage(modalPasswordMessage, '');
  passwordModal.classList.remove('hide');
  modalOldPasswordInput?.focus();
}

function closePasswordModal() {
  passwordModal?.classList.add('hide');
}

async function loadProfile() {
  const user = activeUser();
  try {
    const profile = await requestJson('/profile');
    refreshStoredUser(profile);
    renderProfile(profile);
  } catch (error) {
    renderProfile(user);
    showSettingsMessage(profileMessage, `资料加载失败：${error.message}`, 'error');
  }
}

async function saveProfile() {
  const user = activeUser();
  const username = profileUsernameInput?.value.trim() || '';
  const theme = themeToggle?.checked ? 'dark' : 'light';
  applyTheme(theme);

  if (saveProfileButton) saveProfileButton.disabled = true;
  showSettingsMessage(profileMessage, '保存中...');
  try {
    const profile = await requestJson('/profile', {
      method: 'PATCH',
      body: JSON.stringify({ username, theme })
    });
    refreshStoredUser(profile);
    renderProfile(profile);
    showSettingsMessage(profileMessage, '资料已保存', 'success');
  } catch (error) {
    showSettingsMessage(profileMessage, `保存失败：${error.message}`, 'error');
  } finally {
    if (saveProfileButton) saveProfileButton.disabled = false;
  }
}

async function changePhone() {
  const user = activeUser();
  const oldPhoneSmsCode = modalOldPhoneCodeInput?.value.trim() || '';
  const newPhone = modalNewPhoneInput?.value.trim() || '';
  const newPhoneSmsCode = modalNewPhoneCodeInput?.value.trim() || '';
  if (!/^\d{6}$/.test(oldPhoneSmsCode)) {
    showSettingsMessage(modalPhoneMessage, '请输入原手机号收到的6位验证码', 'error');
    return;
  }
  if (!/^1[3-9]\d{9}$/.test(newPhone)) {
    showSettingsMessage(modalPhoneMessage, '请输入正确的新手机号', 'error');
    return;
  }
  if (!/^\d{6}$/.test(newPhoneSmsCode)) {
    showSettingsMessage(modalPhoneMessage, '请输入新手机号收到的6位验证码', 'error');
    return;
  }
  if (modalFinishPhoneButton) modalFinishPhoneButton.disabled = true;
  showSettingsMessage(modalPhoneMessage, '换绑中...');
  try {
    const profile = await requestJson('/profile/phone', {
      method: 'POST',
      body: JSON.stringify({ oldPhoneSmsCode, newPhone, newPhoneSmsCode })
    });
    refreshStoredUser(profile);
    renderProfile(profile);
    closePhoneModal();
    showSettingsMessage(profileMessage, '手机号已更换', 'success');
  } catch (error) {
    showSettingsMessage(modalPhoneMessage, `换绑失败：${error.message}`, 'error');
  } finally {
    if (modalFinishPhoneButton) modalFinishPhoneButton.disabled = false;
  }
}

async function changePassword() {
  const user = activeUser();
  const oldPassword = modalOldPasswordInput?.value || '';
  const newPassword = modalNewPasswordInput?.value || '';
  const confirmPassword = modalConfirmPasswordInput?.value || '';

  if (!oldPassword.trim()) {
    showSettingsMessage(modalPasswordMessage, '请输入原密码', 'error');
    return;
  }
  if (newPassword.length < 6) {
    showSettingsMessage(modalPasswordMessage, '新密码至少6位', 'error');
    return;
  }
  if (newPassword !== confirmPassword) {
    showSettingsMessage(modalPasswordMessage, '两次新密码输入不一致', 'error');
    return;
  }
  if (oldPassword === newPassword) {
    showSettingsMessage(modalPasswordMessage, '新密码不能与原密码相同', 'error');
    return;
  }

  if (modalFinishPasswordButton) modalFinishPasswordButton.disabled = true;
  showSettingsMessage(modalPasswordMessage, '保存中...');
  try {
    const result = await requestJson('/profile/password', {
      method: 'POST',
      body: JSON.stringify({ oldPassword, newPassword, confirmPassword })
    });
    closePasswordModal();
    showSettingsMessage(profileMessage, result.message || '密码已修改', 'success');
  } catch (error) {
    showSettingsMessage(modalPasswordMessage, `修改失败：${error.message}`, 'error');
  } finally {
    if (modalFinishPasswordButton) modalFinishPasswordButton.disabled = false;
  }
}

async function clearConversationHistory() {
  const user = activeUser();
  if (!window.confirm('确认清空所有会话历史吗？')) return;
  if (clearHistoryButton) clearHistoryButton.disabled = true;
  showSettingsMessage(historyMessage, '清理中...');
  try {
    const result = await requestJson('/profile/conversations', { method: 'DELETE' });
    selectedConversationIds.clear();
    resetNewChatState();
    await loadConversations();
    await refreshDataManagementSummary();
    showSettingsMessage(historyMessage, result.message || '会话历史已清空', 'success');
  } catch (error) {
    showSettingsMessage(historyMessage, `清理失败：${error.message}`, 'error');
  } finally {
    if (clearHistoryButton) clearHistoryButton.disabled = false;
  }
}

async function deleteSelectedConversations() {
  const user = activeUser();
  const conversationIds = [...selectedConversationIds];
  if (!conversationIds.length) return;

  const confirmed = window.confirm(`确认删除选中的 ${conversationIds.length} 条会话吗？`);
  if (!confirmed) return;

  if (deleteSelectedConversationsButton) deleteSelectedConversationsButton.disabled = true;
  showSettingsMessage(historyMessage, '删除中...');
  try {
    const result = await requestJson('/conversations', {
      method: 'DELETE',
      body: JSON.stringify({ conversationIds })
    });

    if (conversationIds.some((id) => String(id) === String(activeConversationId))) {
      resetNewChatState();
    }
    selectedConversationIds.clear();
    await loadConversations();
    await refreshDataManagementSummary();
    showSettingsMessage(historyMessage, result.message || '已删除选中的会话', 'success');
  } catch (error) {
    showSettingsMessage(historyMessage, `删除失败：${error.message}`, 'error');
  } finally {
    syncConversationSelectionControls();
  }
}

function showMessageEvidence(references = []) {
  latestReferences = references;
  activeEvidenceIndex = 0;
  evidenceEnabled = true;
  syncEvidenceLayout();
  evidenceStack?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function hideEvidencePanel() {
  evidenceEnabled = false;
  syncEvidenceLayout();
}

function createEvidenceAction(references = []) {
  const actions = document.createElement('div');
  actions.className = 'message-actions';

  const evidenceButton = document.createElement('button');
  evidenceButton.className = 'message-evidence-btn';
  evidenceButton.type = 'button';
  evidenceButton.textContent = '查看原文';
  evidenceButton.addEventListener('click', () => showMessageEvidence(references));

  actions.appendChild(evidenceButton);
  return actions;
}

function appendMessage(role, content, meta = '', references = []) {
  if (!messageStream) return;
  const emptyState = document.getElementById('chat-empty-state');
  if (emptyState) {
    emptyState.remove();
  }
  const article = document.createElement('article');
  article.className = `message ${role === 'user' ? 'user-message' : 'ai-message'}`;
  article.innerHTML = `
    <span class="message-role">${role === 'user' ? '用户' : '助手'}</span>
    <p class="message-content">${renderMessageMarkdown(content)}</p>
    ${meta ? `<div class="message-meta">${escapeHtml(meta)}</div>` : ''}
  `;
  if (role === 'assistant' && references.length) {
    article.appendChild(createEvidenceAction(references));
  }
  messageStream.appendChild(article);
  messageStream.scrollTop = messageStream.scrollHeight;
  return article;
}

function updateMessage(article, content, meta = '', references = []) {
  if (!article) return;
  const contentElement = article.querySelector('.message-content');
  if (contentElement) {
    contentElement.innerHTML = renderMessageMarkdown(content);
  }
  article.querySelector('.message-meta')?.remove();
  article.querySelector('.message-actions')?.remove();
  if (meta) {
    const metaElement = document.createElement('div');
    metaElement.className = 'message-meta';
    metaElement.textContent = meta;
    article.appendChild(metaElement);
  }
  if (references.length) {
    article.appendChild(createEvidenceAction(references));
  }
  messageStream.scrollTop = messageStream.scrollHeight;
}

function displaySourceName(value = '') {
  return String(value || '未知规范')
    .replace(/\.pdf$/i, '')
    .replace(/^(user|admin)_\d+_\d{14}_/, '')
    .replace(/\+/g, ' ')
    .replace(/^DLT\s+/i, 'DL/T ');
}

function referenceImageUrl(ref = {}) {
  return ref.imageUrl || ref.image_url || '';
}

function renderEvidence(references = []) {
  if (!evidenceStack) return;
  latestReferences = references;
  if (!references.length) {
    evidenceStack.innerHTML = '<p class="empty-hint">暂无原文定位结果</p>';
    return;
  }

  activeEvidenceIndex = Math.min(Math.max(activeEvidenceIndex, 0), references.length - 1);
  const ref = references[activeEvidenceIndex];
  const imageUrl = referenceImageUrl(ref);
  const sourceName = displaySourceName(ref.sourceFile || ref.source_file || ref.standardName);
  const clauseId = ref.clauseId || ref.clause_id || '';
  const documentPage = ref.documentPage || ref.document_page || ref.page || '-';
  const contentPreview = ref.contentPreview || ref.content_preview || '';
  const preview = imageUrl
    ? `<img class="evidence-image" src="${escapeHtml(imageUrl)}" alt="原文${activeEvidenceIndex + 1}截图">`
    : `<div class="evidence-missing-image">原文页面截图暂不可用</div>`;

  evidenceStack.innerHTML = `
    <article class="evidence-card">
      <div class="evidence-page ${references.length > 1 ? 'clickable' : ''}" ${references.length > 1 ? 'title="点击查看下一条原文"' : ''}>${preview}</div>
      <div class="evidence-info">
        <p class="evidence-source">原文${activeEvidenceIndex + 1}：《${escapeHtml(sourceName)}》 ｜ 页码：${escapeHtml(documentPage)} ｜ 条款：${escapeHtml(clauseId)}</p>
        ${contentPreview ? `<p class="evidence-snippet">${escapeHtml(contentPreview)}</p>` : ''}
      </div>
      <div class="evidence-nav">
        <button class="soft-btn evidence-nav-btn" type="button" data-evidence-nav="prev" ${activeEvidenceIndex === 0 ? 'disabled' : ''}>上一条</button>
        <span>${activeEvidenceIndex + 1} / ${references.length}</span>
        <button class="soft-btn evidence-nav-btn" type="button" data-evidence-nav="next" ${activeEvidenceIndex >= references.length - 1 ? 'disabled' : ''}>下一条</button>
      </div>
    </article>
  `;

  evidenceStack.querySelector('[data-evidence-nav="prev"]')?.addEventListener('click', () => {
    activeEvidenceIndex -= 1;
    renderEvidence(latestReferences);
  });
  evidenceStack.querySelector('[data-evidence-nav="next"]')?.addEventListener('click', () => {
    activeEvidenceIndex += 1;
    renderEvidence(latestReferences);
  });
  evidenceStack.querySelector('.evidence-page.clickable')?.addEventListener('click', () => {
    activeEvidenceIndex = (activeEvidenceIndex + 1) % latestReferences.length;
    renderEvidence(latestReferences);
  });
}

function syncEvidenceLayout() {
  if (!chatWorkspace) return;
  chatWorkspace.classList.toggle('evidence-enabled', evidenceEnabled);
  if (evidenceEnabled) {
    renderEvidence(latestReferences);
  }
}

function renderSuggestions(suggestions = []) {
  if (!suggestionRow) return;
  suggestionRow.innerHTML = '';
  suggestions.forEach((text) => {
    const button = document.createElement('button');
    button.className = 'suggestion-chip';
    button.textContent = text;
    button.addEventListener('click', () => {
      composerInput.value = text;
      sendButton.click();
    });
    suggestionRow.appendChild(button);
  });
}

function formatConversationTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatExportTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatShortDateTime(value) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function safeFilePart(value) {
  return String(value || 'chat-records')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 48) || 'chat-records';
}

function downloadTextFile(fileName, content, mimeType) {
  const blob = new Blob([`\uFEFF${content}`], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function wordText(value) {
  return escapeHtml(value).replace(/\r?\n/g, '<br>');
}

function wordTable(rows = []) {
  if (!rows.length) return '';
  const [headers, ...bodyRows] = rows;
  return `
    <table>
      <thead>
        <tr>${headers.map((cell) => `<th>${wordText(cell)}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${bodyRows.map((row) => `
          <tr>${row.map((cell) => `<td>${wordText(cell)}</td>`).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function buildWordDocument(title, summaryRows, detailRows) {
  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${wordText(title)}</title>
  <style>
    body {
      font-family: "Microsoft YaHei", Arial, sans-serif;
      color: #18363f;
      line-height: 1.65;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 24px;
    }
    h2 {
      margin: 24px 0 10px;
      font-size: 18px;
      color: #1f5d6b;
    }
    .meta {
      margin: 0 0 18px;
      color: #65727a;
      font-size: 12px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 18px;
      table-layout: fixed;
    }
    th,
    td {
      border: 1px solid #cfd9dd;
      padding: 8px 10px;
      vertical-align: top;
      word-break: break-word;
      font-size: 12px;
    }
    th {
      background: #e8f1f2;
      color: #18363f;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <h1>${wordText(title)}</h1>
  <p class="meta">导出时间：${wordText(formatExportTime(new Date()))}</p>
  <h2>会话总结</h2>
  ${wordTable(summaryRows)}
  <h2>对话明细</h2>
  ${wordTable(detailRows)}
</body>
</html>`;
}

function referencesSummary(references = []) {
  return references
    .map((ref) => {
      const page = ref.documentPage || ref.document_page || ref.page;
      return [ref.sourceFile || ref.standardName || '', ref.clauseId || '', page ? `P${page}` : '']
        .filter(Boolean)
        .join(' ');
    })
    .filter(Boolean)
    .join('；');
}

function compactText(value, maxLength = 90) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

function uniqueValues(values = []) {
  return [...new Set(values.filter(Boolean))];
}

function renderDataManagementSummary({ conversations = recentConversations, messageCount = null } = {}) {
  setText(dataConversationCount, conversations.length);
  setText(dataLastConversation, conversations[0]?.updatedAt ? formatShortDateTime(conversations[0].updatedAt) : '--');
  setText(dataLatestConversationTitle, conversations[0]?.title || '--');
  if (messageCount !== null) {
    setText(dataMessageCount, messageCount);
  } else if (dataMessageCount && dataMessageCount.textContent === '--') {
    setText(dataMessageCount, '统计中');
  }
}

function syncConversationSelectionControls() {
  const total = recentConversations.length;
  const selectedCount = selectedConversationIds.size;
  if (deleteSelectedConversationsButton) {
    deleteSelectedConversationsButton.disabled = selectedCount === 0;
    deleteSelectedConversationsButton.textContent = selectedCount ? `删除选中（${selectedCount}）` : '删除选中';
  }
  if (selectAllConversationsCheckbox) {
    selectAllConversationsCheckbox.checked = total > 0 && selectedCount === total;
    selectAllConversationsCheckbox.indeterminate = selectedCount > 0 && selectedCount < total;
  }
}

function renderConversationManageList(conversations = recentConversations) {
  if (!conversationManageList) return;

  selectedConversationIds.forEach((id) => {
    if (!conversations.some((conversation) => String(conversation.id) === String(id))) {
      selectedConversationIds.delete(id);
    }
  });

  if (!conversations.length) {
    conversationManageList.innerHTML = '<p class="empty-hint">暂无历史会话</p>';
    syncConversationSelectionControls();
    return;
  }

  conversationManageList.innerHTML = '';
  conversations.forEach((conversation) => {
    const label = document.createElement('label');
    label.className = 'conversation-manage-row';
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(conversation.id)}" ${selectedConversationIds.has(conversation.id) ? 'checked' : ''}>
      <span class="conversation-manage-main">
        <strong>${escapeHtml(conversation.title || '新会话')}</strong>
        <small>更新时间：${escapeHtml(formatShortDateTime(conversation.updatedAt))}</small>
      </span>
    `;
    const checkbox = label.querySelector('input');
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        selectedConversationIds.add(conversation.id);
      } else {
        selectedConversationIds.delete(conversation.id);
      }
      syncConversationSelectionControls();
    });
    conversationManageList.appendChild(label);
  });

  syncConversationSelectionControls();
}

async function refreshDataManagementSummary() {
  const user = activeUser();
  if (!user?.id) return;

  try {
    const conversations = recentConversations.length
      ? recentConversations
      : await requestJson('/conversations');
    recentConversations = conversations;

    renderDataManagementSummary({ conversations });

    let messageCount = 0;
    for (const conversation of conversations) {
      const messages = await requestJson(`/conversations/${conversation.id}/messages`);
      messageCount += messages.length;
    }

    renderDataManagementSummary({ conversations, messageCount });
  } catch (error) {
    console.warn('加载数据管理概览失败', error);
    setText(dataMessageCount, '--');
  }
}

function conversationExportSummary(conversation, messages = []) {
  const userMessages = messages.filter((message) => message.role === 'user');
  const assistantMessages = messages.filter((message) => message.role === 'assistant');
  const questions = userMessages.map((message) => compactText(message.content, 48)).filter(Boolean);
  const references = messages.flatMap((message) => message.references || []);
  const clauses = uniqueValues(references.map((ref) => ref.clauseId).filter(Boolean)).slice(0, 6);
  const sources = uniqueValues(references.map((ref) => ref.sourceFile || ref.standardName).filter(Boolean)).slice(0, 3);
  const topic = conversation.title || questions[0] || '未命名会话';

  const parts = [
    `本次会话主题为“${topic}”`,
    `共包含 ${userMessages.length} 个用户问题和 ${assistantMessages.length} 条助手回复`
  ];

  if (questions.length) {
    parts.push(`主要问题包括：${questions.slice(0, 3).join('；')}`);
  }
  if (clauses.length) {
    parts.push(`回答中引用的重点条款包括：${clauses.join('、')}`);
  }
  if (sources.length) {
    parts.push(`涉及资料来源：${sources.join('、')}`);
  }

  return `${parts.join('。')}。`;
}

function renderConversations(conversations = []) {
  if (!conversationList) return;

  recentConversations = conversations;
  renderConversationManageList(conversations);

  if (!conversations.length) {
    conversationList.innerHTML = '<p class="empty-hint">暂无历史会话</p>';
    return;
  }

  conversationList.innerHTML = '';

  conversations.forEach((conversation) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'history-chip';
    button.dataset.conversationId = conversation.id;

    if (String(conversation.id) === String(activeConversationId)) {
      button.classList.add('active');
    }

    button.innerHTML = `
      <span class="history-title">${escapeHtml(conversation.title || '新会话')}</span>
      <small class="history-time">${escapeHtml(formatConversationTime(conversation.updatedAt))}</small>
    `;

    button.addEventListener('click', () => {
      loadConversationMessages(conversation.id);
    });

    conversationList.appendChild(button);
  });
}

async function loadConversations() {
  const user = activeUser();

  try {
    const conversations = await requestJson('/conversations');
    renderConversations(conversations);
    renderDataManagementSummary({ conversations });
  } catch (error) {
    console.warn('加载最近对话失败', error);
    if (conversationList) {
      conversationList.innerHTML = '<p class="empty-hint">最近对话加载失败</p>';
    }
  }
}

async function loadConversationMessages(conversationId) {
  const user = activeUser();

  try {
    activeConversationId = conversationId;
    latestReferences = [];
    renderSuggestions([]);

    if (chatSessionPill) {
      chatSessionPill.textContent = `会话编号：${conversationId}`;
    }

    if (messageStream) {
      messageStream.innerHTML = '';
    }

    const messages = await requestJson(`/conversations/${conversationId}/messages`);

    if (!messages.length && messageStream) {
      messageStream.innerHTML = `
        <div class="chat-empty-state" id="chat-empty-state">
          <strong>这个会话暂无消息</strong>
          <p>你可以继续输入新的工程问题。</p>
        </div>
      `;
    }

    messages.forEach((message) => {
      const references = message.references || [];
      const clauses = references
        .map((ref) => ref.clauseId)
        .filter(Boolean)
        .join(' / ');

      appendMessage(
        message.role === 'user' ? 'user' : 'assistant',
        message.content || '',
        clauses ? `引用条款：${clauses}` : '',
        references
      );

      if (message.role === 'assistant' && references.length) {
        latestReferences = references;
      }
    });

    if (evidenceEnabled) {
      renderEvidence(latestReferences);
    }

    renderConversations(recentConversations);
  } catch (error) {
    appendMessage('assistant', `加载会话失败：${error.message}`);
  }
}

async function exportChatRecords(exportAll = false) {
  const user = activeUser();
  if (!user?.id) return;

  const oldText = exportChatButton?.textContent || '';
  if (exportChatButton) {
    exportChatButton.disabled = true;
    exportChatButton.textContent = '导出中...';
  }

  try {
    let conversations = recentConversations;
    if (!conversations.length) {
      conversations = await requestJson('/conversations');
      renderConversations(conversations);
    }

    if (!conversations.length) {
      alert('暂无可导出的会话记录');
      return;
    }

    const selectedConversation = !exportAll && activeConversationId
      ? conversations.find((item) => String(item.id) === String(activeConversationId))
      : null;
    const exportConversations = selectedConversation
      ? [selectedConversation]
      : conversations;

    const summaryRows = [[
      '导出部分',
      '会话ID',
      '会话标题',
      '创建时间',
      '更新时间',
      '用户问题数',
      '助手回复数',
      '对话总结'
    ]];

    const detailRows = [[
      '导出部分',
      '会话ID',
      '会话标题',
      '消息序号',
      '角色',
      '发送时间',
      '内容',
      '引用信息'
    ]];

    for (const conversation of exportConversations) {
      const messages = await requestJson(`/conversations/${conversation.id}/messages`);
      const userMessageCount = messages.filter((message) => message.role === 'user').length;
      const assistantMessageCount = messages.filter((message) => message.role === 'assistant').length;

      summaryRows.push([
        '会话摘要',
        conversation.id,
        conversation.title || '新会话',
        formatExportTime(conversation.createdAt),
        formatExportTime(conversation.updatedAt),
        userMessageCount,
        assistantMessageCount,
        conversationExportSummary(conversation, messages)
      ]);

      messages.forEach((message) => {
        detailRows.push([
          '消息明细',
          conversation.id,
          conversation.title || '新会话',
          message.seqNo || '',
          message.role === 'user' ? '用户' : '助手',
          formatExportTime(message.createdAt),
          message.content || '',
          referencesSummary(message.references || [])
        ]);
      });
    }

    if (detailRows.length === 1) {
      alert('当前会话暂无可导出的消息');
      return;
    }

    const today = new Date().toISOString().slice(0, 10);
    const fileScope = selectedConversation
      ? safeFilePart(selectedConversation.title || `conversation-${selectedConversation.id}`)
      : 'all-conversations';
    const documentTitle = selectedConversation
      ? `大坝智能问答记录 - ${selectedConversation.title || `会话${selectedConversation.id}`}`
      : '大坝智能问答记录 - 全部会话';
    const wordDocument = buildWordDocument(documentTitle, summaryRows, detailRows);
    downloadTextFile(`dam-rag-${fileScope}-${today}.doc`, wordDocument, 'application/msword;charset=utf-8');
  } catch (error) {
    alert(`导出失败：${error.message}`);
  } finally {
    if (exportChatButton) {
      exportChatButton.disabled = false;
      exportChatButton.textContent = oldText || '导出记录';
    }
  }
}

function resetNewChatState() {
  activeConversationId = null;
  latestReferences = [];
  evidenceEnabled = false;
  if (chatSessionPill) {
    chatSessionPill.textContent = '当前为新对话';
  }
  if (messageStream) {
    messageStream.innerHTML = `
      <div class="chat-empty-state" id="chat-empty-state">
        <strong>开始一段新对话</strong>
        <p>输入你的工程问题后，系统会在这里返回回答。</p>
      </div>
    `;
  }
  renderSuggestions([]);
  renderEvidence([]);
  syncEvidenceLayout();
  renderConversations(recentConversations);
}

function statusBadgeClass(status = '') {
  if (status.includes('失败')) return 'danger';
  if (status.includes('完成') || status.includes('入库')) return 'success';
  return 'processing';
}

function statusBadgeClass(status = '') {
  const value = String(status || '');
  if (value.includes('失败') || value.includes('澶辫触')) return 'danger';
  if (value.includes('完成') || value.includes('已完成') || value.includes('入库成功')
      || value.includes('瀹屾垚') || value.includes('鍏ュ簱')) {
    return 'success';
  }
  return 'processing';
}

function isIngestingStatus(status = '') {
  const value = String(status || '');
  return ['等待入库', '正在入库', '正在解析', '处理中'].some((item) => value.includes(item))
    || ['寰呭', '姝ｅ湪', '瑙ｆ瀽', '澶勭悊涓'].some((item) => value.includes(item));
}

function syncDocumentPolling(documents = []) {
  const hasProcessingDocument = documents.some((doc) => isIngestingStatus(doc.processStatus));
  if (hasProcessingDocument && !userDocumentPollTimer) {
    userDocumentPollTimer = window.setInterval(loadMyDocuments, 3000);
  }
  if (!hasProcessingDocument && userDocumentPollTimer) {
    window.clearInterval(userDocumentPollTimer);
    userDocumentPollTimer = null;
  }
}

function createDeleteButton(onClick) {
  const button = document.createElement('button');
  button.className = 'danger-btn action-btn';
  button.type = 'button';
  button.textContent = '删除';
  button.addEventListener('click', onClick);
  return button;
}

async function deleteUserDocument(documentId, fileName) {
  const user = activeUser();
  const confirmed = window.confirm(`确认删除文档《${fileName}》吗？`);
  if (!confirmed) return;

  try {
    await requestJson(`/documents/${documentId}`, { method: 'DELETE' });
    await loadMyDocuments();
    alert('文档已删除');
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

function renderUserUploadList(documents = []) {
  if (!userUploadList) return;
  if (!documents.length) {
    userUploadList.innerHTML = '<div class="empty-hint">暂未上传个人文档</div>';
    return;
  }

  userUploadList.innerHTML = '';
  documents.slice(0, 5).forEach((doc) => {
    const row = document.createElement('div');
    row.className = 'upload-row';
    row.innerHTML = `
      <div class="upload-row-main">
        <span>${escapeHtml(doc.fileName)}</span>
        <span class="status-badge ${statusBadgeClass(doc.processStatus)}">${escapeHtml(doc.processStatus)}</span>
      </div>
    `;
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    actions.appendChild(createDeleteButton(() => deleteUserDocument(doc.id, doc.fileName)));
    row.appendChild(actions);
    userUploadList.appendChild(row);
  });
}

function renderUserDocumentsTable(documents = []) {
  if (!userDocumentsBody) return;
  if (!documents.length) {
    userDocumentsBody.innerHTML = '<tr><td colspan="3" class="empty-table-cell">暂无个人文档</td></tr>';
    return;
  }

  userDocumentsBody.innerHTML = '';
  documents.forEach((doc) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(doc.fileName)}</td>
      <td><span class="status-badge ${statusBadgeClass(doc.processStatus)}">${escapeHtml(doc.processStatus)}</span></td>
      <td></td>
    `;
    const actionCell = tr.lastElementChild;
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    actions.appendChild(createDeleteButton(() => deleteUserDocument(doc.id, doc.fileName)));
    actionCell.appendChild(actions);
    userDocumentsBody.appendChild(tr);
  });
}

async function loadMyDocuments() {
  const user = activeUser();
  try {
    const documents = await requestJson('/documents/my');
    renderUserUploadList(documents);
    renderUserDocumentsTable(documents);
    syncDocumentPolling(documents);
  } catch (error) {
    console.warn('加载个人文档失败', error);
    if (userUploadList) {
      userUploadList.innerHTML = '<div class="empty-hint">个人文档加载失败</div>';
    }
    if (userDocumentsBody) {
      userDocumentsBody.innerHTML = '<tr><td colspan="3" class="empty-table-cell">个人文档加载失败</td></tr>';
    }
  }
}

async function sendMessage() {
  const text = composerInput.value.trim();
  if (!text) return;
  const user = activeUser();
  appendMessage('user', text);
  const pendingMessage = appendMessage('assistant', '正在生成内容，请稍候...', '生成中');
  composerInput.value = '';
  sendButton.disabled = true;

  try {
    const data = await requestJson('/chat', {
      method: 'POST',
      body: JSON.stringify({
        conversationId: activeConversationId,
        question: text,
        history: [],
        enableEvidence: true,
        enableSuggestions: true,
        knowledgeScope: 'ALL'
      })
    });
    activeConversationId = data.conversationId;
    if (chatSessionPill) {
      chatSessionPill.textContent = `会话编号：${data.conversationId}`;
    }
    const clauses = (data.references || []).map((ref) => ref.clauseId || ref.clause_id).filter(Boolean).join(' / ');
    updateMessage(pendingMessage, data.answer, clauses ? `引用条款：${clauses}` : '', data.references || []);
    latestReferences = data.references || [];
    if (evidenceEnabled) {
      renderEvidence(latestReferences);
    }
    renderSuggestions(data.suggestions || []);
    await loadConversations();
    await refreshDataManagementSummary();
  } catch (error) {
    updateMessage(pendingMessage, error.message || '知识库服务暂时不可用，请稍后重试。');
  } finally {
    sendButton.disabled = false;
  }
}

if (sendButton && composerInput) {
  sendButton.addEventListener('click', sendMessage);
  composerInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.isComposing) {
      return;
    }

    if (event.shiftKey) {
      return;
    }

    event.preventDefault();
    if (!sendButton.disabled) {
      sendMessage();
    }
  });
}

if (exportChatButton) {
  exportChatButton.addEventListener('click', () => exportChatRecords(false));
}

if (exportAllRecordsButton) {
  exportAllRecordsButton.addEventListener('click', () => exportChatRecords(true));
}

if (selectAllConversationsCheckbox) {
  selectAllConversationsCheckbox.addEventListener('change', () => {
    selectedConversationIds.clear();
    if (selectAllConversationsCheckbox.checked) {
      recentConversations.forEach((conversation) => selectedConversationIds.add(conversation.id));
    }
    renderConversationManageList(recentConversations);
  });
}

if (deleteSelectedConversationsButton) {
  deleteSelectedConversationsButton.addEventListener('click', deleteSelectedConversations);
}

if (clearButton && messageStream) {
  clearButton.addEventListener('click', () => {
    resetNewChatState();
  });
}

if (newChatNavButton) {
  newChatNavButton.addEventListener('click', () => {
    resetNewChatState();
  });
}

if (closeEvidenceButton) {
  closeEvidenceButton.addEventListener('click', hideEvidencePanel);
}

if (saveProfileButton) {
  saveProfileButton.addEventListener('click', saveProfile);
}

if (cancelProfileButton) {
  cancelProfileButton.addEventListener('click', () => {
    renderProfile(latestProfile || activeUser());
    showSettingsMessage(profileMessage, '已取消修改');
  });
}

if (openPhoneModalButton) {
  openPhoneModalButton.addEventListener('click', openPhoneModal);
}

if (openPasswordModalButton) {
  openPasswordModalButton.addEventListener('click', openPasswordModal);
}

if (closePhoneModalButton) {
  closePhoneModalButton.addEventListener('click', closePhoneModal);
}

if (closePasswordModalButton) {
  closePasswordModalButton.addEventListener('click', closePasswordModal);
}

if (modalCancelPhoneButton) {
  modalCancelPhoneButton.addEventListener('click', closePhoneModal);
}

if (modalCancelPasswordButton) {
  modalCancelPasswordButton.addEventListener('click', closePasswordModal);
}

if (modalNextPhoneButton) {
  modalNextPhoneButton.addEventListener('click', () => {
    if (!/^\d{6}$/.test(modalOldPhoneCodeInput?.value.trim() || '')) {
      showSettingsMessage(modalPhoneMessage, '请输入原手机号收到的6位验证码', 'error');
      return;
    }
    showSettingsMessage(modalPhoneMessage, '');
    setPhoneModalStep('bind-new');
    modalNewPhoneInput?.focus();
  });
}

if (modalBackPhoneButton) {
  modalBackPhoneButton.addEventListener('click', () => {
    showSettingsMessage(modalPhoneMessage, '');
    setPhoneModalStep('verify-current');
  });
}

if (modalFinishPhoneButton) {
  modalFinishPhoneButton.addEventListener('click', changePhone);
}

if (modalFinishPasswordButton) {
  modalFinishPasswordButton.addEventListener('click', changePassword);
}

if (passwordModal) {
  passwordModal.addEventListener('click', (event) => {
    if (event.target === passwordModal) {
      closePasswordModal();
    }
  });
}

if (modalSendOldCodeButton) {
  modalSendOldCodeButton.addEventListener('click', () => {
    const phone = latestProfile?.phone || activeUser().phone;
    sendSmsCodeForPhone(phone, 'login', '原手机号验证码');
  });
}

if (modalSendNewCodeButton) {
  modalSendNewCodeButton.addEventListener('click', () => {
    const phone = modalNewPhoneInput?.value.trim() || '';
    sendSmsCodeForPhone(phone, 'register', '新手机号验证码');
  });
}

if (phoneModal) {
  phoneModal.addEventListener('click', (event) => {
    if (event.target === phoneModal) {
      closePhoneModal();
    }
  });
}

if (clearHistoryButton) {
  clearHistoryButton.addEventListener('click', clearConversationHistory);
}

if (themeToggle) {
  themeToggle.addEventListener('change', () => {
    applyTheme(themeToggle.checked ? 'dark' : 'light');
  });
}

syncEvidenceLayout();
resetNewChatState();

const uploadButton = document.querySelector('.upload-dropzone .primary-btn');
if (uploadButton) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.pdf';
  input.multiple = true;
  input.hidden = true;
  document.body.appendChild(input);
  uploadButton.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const user = activeUser();
    const formData = new FormData();
    [...input.files].forEach((file) => formData.append('files', file));
    try {
      const response = await fetch(`${API_BASE}/documents/upload?visibility=private`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData
      });
      if (!response.ok) throw new Error(await response.text());
      await loadMyDocuments();
      alert('文档已提交入库流程');
    } catch (error) {
      alert(`上传失败：${error.message}`);
    }
  });
}

applyTheme(activeUser().theme || 'light');
loadProfile();
loadMyDocuments();
loadConversations();
refreshDataManagementSummary();
