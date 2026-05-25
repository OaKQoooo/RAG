const sendButton = document.getElementById('send-message');
const clearButton = document.getElementById('clear-chat');
const composerInput = document.getElementById('composer-input');
const messageStream = document.getElementById('message-stream');
const evidenceStack = document.querySelector('.evidence-stack');
const suggestionRow = document.getElementById('suggestion-row') || document.querySelector('.suggestion-row');
const evidenceToggle = document.getElementById('evidence-toggle');
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
const newChatNavButton = document.querySelector('.nav-item[data-view="chat"]');
let activeConversationId = null;
let evidenceEnabled = false;
let latestReferences = [];
let latestProfile = null;
let recentConversations = [];

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function activeUser() {
  return currentUser() || { id: 1, username: '演示用户', phone: '' };
}

function showSettingsMessage(element, text, type = '') {
  if (!element) return;
  element.textContent = text;
  element.className = `settings-message${type ? ` ${type}` : ''}`;
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
}

function showDemoCodeMessage(element, targetText) {
  showSettingsMessage(element, `${targetText}已发送，演示验证码：123456`, 'success');
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
    const profile = await requestJson(`/profile?userId=${user.id}`);
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
    const profile = await requestJson(`/profile?userId=${user.id}`, {
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
    const profile = await requestJson(`/profile/phone?userId=${user.id}`, {
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
    const result = await requestJson(`/profile/password?userId=${user.id}`, {
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
    const result = await requestJson(`/profile/conversations?userId=${user.id}`, { method: 'DELETE' });
    resetNewChatState();
    await loadConversations();
    showSettingsMessage(historyMessage, result.message || '会话历史已清空', 'success');
  } catch (error) {
    showSettingsMessage(historyMessage, `清理失败：${error.message}`, 'error');
  } finally {
    if (clearHistoryButton) clearHistoryButton.disabled = false;
  }
}

function appendMessage(role, content, meta = '') {
  if (!messageStream) return;
  const emptyState = document.getElementById('chat-empty-state');
  if (emptyState) {
    emptyState.remove();
  }
  const article = document.createElement('article');
  article.className = `message ${role === 'user' ? 'user-message' : 'ai-message'}`;
  article.innerHTML = `
    <span class="message-role">${role === 'user' ? '用户' : '助手'}</span>
    <p>${escapeHtml(content)}</p>
    ${meta ? `<div class="message-meta">${escapeHtml(meta)}</div>` : ''}
  `;
  messageStream.appendChild(article);
  messageStream.scrollTop = messageStream.scrollHeight;
}

function renderEvidence(references = []) {
  if (!evidenceStack) return;
  latestReferences = references;
  evidenceStack.innerHTML = references.length ? '' : '<p class="empty-hint">暂无原文定位结果</p>';
  references.forEach((ref) => {
    const card = document.createElement('article');
    card.className = 'evidence-card';
    const preview = ref.imageUrl
      ? `<img class="evidence-image" src="${escapeHtml(ref.imageUrl)}" alt="原文截图">`
      : `<div class="evidence-preview page-preview"><div class="page-line long"></div><div class="page-highlight"></div><div class="page-line medium"></div></div>`;
    card.innerHTML = `
      <div class="evidence-preview">${preview}</div>
      <div class="evidence-info">
        <h4>《${escapeHtml(ref.sourceFile || ref.source_file)}》</h4>
        <p>页码：${escapeHtml(ref.page)} ｜ 条款：${escapeHtml(ref.clauseId || ref.clause_id)} ｜ bbox：${escapeHtml(ref.bboxJson || ref.bbox_json || '[]')}</p>
      </div>
    `;
    evidenceStack.appendChild(card);
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

function renderConversations(conversations = []) {
  if (!conversationList) return;

  recentConversations = conversations;

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
    const conversations = await requestJson(`/conversations?userId=${user.id}`);
    renderConversations(conversations);
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

    const messages = await requestJson(`/conversations/${conversationId}/messages?userId=${user.id}`);

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
        clauses ? `引用条款：${clauses}` : ''
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

function resetNewChatState() {
  activeConversationId = null;
  latestReferences = [];
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
  renderConversations(recentConversations);
}

function statusBadgeClass(status = '') {
  if (status.includes('失败')) return 'danger';
  if (status.includes('完成') || status.includes('入库')) return 'success';
  return 'processing';
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
    await requestJson(`/documents/${documentId}?userId=${user.id}`, { method: 'DELETE' });
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
    const documents = await requestJson(`/documents/my?userId=${user.id}`);
    renderUserUploadList(documents);
    renderUserDocumentsTable(documents);
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
  composerInput.value = '';
  sendButton.disabled = true;

  try {
    const data = await requestJson('/chat', {
      method: 'POST',
      body: JSON.stringify({
        userId: user.id,
        conversationId: activeConversationId,
        question: text,
        history: [],
        enableEvidence: evidenceEnabled,
        enableSuggestions: true,
        knowledgeScope: 'ALL'
      })
    });
    activeConversationId = data.conversationId;
    if (chatSessionPill) {
      chatSessionPill.textContent = `会话编号：${data.conversationId}`;
    }
    const clauses = (data.references || []).map((ref) => ref.clauseId || ref.clause_id).filter(Boolean).join(' / ');
    appendMessage('assistant', data.answer, clauses ? `引用条款：${clauses}` : '');
    latestReferences = data.references || [];
    if (evidenceEnabled) {
      renderEvidence(latestReferences);
    }
    renderSuggestions(data.suggestions || []);
    await loadConversations();
  } catch (error) {
    appendMessage('assistant', `请求后端失败：${error.message}`);
  } finally {
    sendButton.disabled = false;
  }
}

if (sendButton && composerInput) {
  sendButton.addEventListener('click', sendMessage);
  composerInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      sendMessage();
    }
  });
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

if (evidenceToggle) {
  evidenceToggle.addEventListener('change', () => {
    evidenceEnabled = evidenceToggle.checked;
    syncEvidenceLayout();
  });
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
    if ((modalOldPhoneCodeInput?.value.trim() || '') !== '123456') {
      showSettingsMessage(modalPhoneMessage, '原手机号验证码错误', 'error');
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
  modalSendOldCodeButton.addEventListener('click', () => showDemoCodeMessage(modalPhoneMessage, '原手机号验证码'));
}

if (modalSendNewCodeButton) {
  modalSendNewCodeButton.addEventListener('click', () => showDemoCodeMessage(modalPhoneMessage, '新手机号验证码'));
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
      const response = await fetch(`${API_BASE}/documents/upload?userId=${user.id}&visibility=private`, {
        method: 'POST',
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
