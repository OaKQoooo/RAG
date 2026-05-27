const adminNavButtons = document.querySelectorAll('.admin-shell .nav-item');
const adminTitle = document.getElementById('admin-view-title');
const adminDocumentsBody = document.getElementById('admin-documents-body');
const adminUploadList = document.getElementById('admin-upload-list');
const adminDocumentSearch = document.getElementById('admin-document-search');
const adminUsersBody = document.getElementById('admin-users-body');
const adminUserSearch = document.getElementById('admin-user-search');
const adminActivityList = document.getElementById('admin-activity-list');
let adminDocumentRows = [];
let adminUserRows = [];
let adminDocumentPollTimer = null;

const loginUser = currentUser();
if (window.DAM_RAG_LOGIN_REQUIRED || !loginUser || loginUser.role !== 'admin') {
  window.location.href = './index.html';
  throw new Error('Login required');
}

const adminTitles = {
  overview: '平台总览',
  library: '文档库管理',
  users: '用户管理'
};

adminNavButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const target = button.dataset.view;
    if (adminTitle && adminTitles[target]) {
      adminTitle.textContent = adminTitles[target];
    }
  });
});

function cell(text) {
  const td = document.createElement('td');
  td.textContent = text ?? '';
  return td;
}

function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function roleText(role) {
  if (role === 'admin') return '管理员';
  if (role === 'user') return '用户';
  return role || '-';
}

function statusText(status) {
  return status === 1 ? '启用' : '禁用';
}

function visibilityText(visibility) {
  if (visibility === 'public') return '公共知识库';
  if (visibility === 'private') return '个人文档';
  return visibility || '-';
}

function textIncludes(value, keyword) {
  return String(value || '').toLowerCase().includes(keyword);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function statusBadgeClass(status = '') {
  if (status.includes('失败')) return 'danger';
  if (status.includes('完成') || status.includes('已完成') || status.includes('入库')) return 'success';
  if (status.includes('解析') || status.includes('处理中') || status.includes('正在')) return 'processing';
  return 'processing';
}

function statusBadgeClass(status = '') {
  const value = String(status || '');
  if (value.includes('失败') || value.includes('澶辫触')) return 'danger';
  if (value.includes('完成') || value.includes('已完成') || value.includes('入库成功')
      || value.includes('瀹屾垚') || value.includes('宸插畬鎴?') || value.includes('鍏ュ簱')) {
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
  if (hasProcessingDocument && !adminDocumentPollTimer) {
    adminDocumentPollTimer = window.setInterval(async () => {
      await loadDocuments();
      await loadOverview();
      await loadActivities();
    }, 3000);
  }
  if (!hasProcessingDocument && adminDocumentPollTimer) {
    window.clearInterval(adminDocumentPollTimer);
    adminDocumentPollTimer = null;
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

async function deleteAdminDocument(documentId, fileName) {
  const confirmed = window.confirm(
    `确认删除文档《${fileName}》吗？\n\n删除后系统会重新构建知识库，过程可能需要一段时间。`
  );
  if (!confirmed) return;

  try {
    await requestJson(`/admin/documents/${documentId}`, { method: 'DELETE' });
    await loadDocuments();
    await loadOverview();
    await loadActivities();
    alert('文档已删除');
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

function renderAdminUploadList(documents = []) {
  if (!adminUploadList) return;
  const adminDocs = documents.filter((doc) => doc.uploadRole === 'admin');
  if (!adminDocs.length) {
    adminUploadList.innerHTML = '<div class="empty-hint">暂无管理员上传文档</div>';
    return;
  }

  adminUploadList.innerHTML = '';
  adminDocs.slice(0, 5).forEach((doc) => {
    const row = document.createElement('div');
    row.className = 'upload-row';
    row.innerHTML = `
      <div class="upload-row-main">
        <span>${escapeHtml(doc.fileName)}</span>
        <span>${formatDateTime(doc.createdAt)}</span>
        <span class="status-badge ${statusBadgeClass(doc.processStatus)}">
          ${escapeHtml(doc.processStatus || '待处理')}
        </span>
      </div>
    `;
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    actions.appendChild(createDeleteButton(() => deleteAdminDocument(doc.id, doc.fileName)));
    row.appendChild(actions);
    adminUploadList.appendChild(row);
  });
}

async function loadOverview() {
  try {
    const data = await requestJson('/admin/overview');
    const cards = document.querySelectorAll('.metric-card strong');
    const values = [data.documentCount, data.userCount, data.clauseCount, data.chunkCount];
    cards.forEach((card, index) => {
      if (values[index] !== undefined) card.textContent = values[index];
    });
  } catch (error) {
    console.warn('加载总览失败', error);
  }
}

function createStatusButton(user) {
  const isSelf = Number(user.id) === Number(loginUser.id);
  const nextStatus = user.status === 1 ? 0 : 1;
  const button = document.createElement('button');
  button.className = `${nextStatus === 1 ? 'soft-btn' : 'danger-btn'} action-btn`;
  button.type = 'button';
  button.textContent = nextStatus === 1 ? '启用' : '禁用';
  button.disabled = isSelf;
  button.title = isSelf ? '不能操作当前登录账号' : '';
  button.addEventListener('click', () => updateUserStatus(user, nextStatus));
  return button;
}

function renderAdminDocumentTable(rows = []) {
  if (!adminDocumentsBody) return;

  adminDocumentsBody.innerHTML = '';

  if (!rows.length) {
    adminDocumentsBody.innerHTML = '<tr><td colspan="8" class="empty-table-cell">暂无文档</td></tr>';
    return;
  }

  rows.forEach((doc) => {
    const tr = document.createElement('tr');

    tr.append(cell(doc.fileName));
    tr.append(cell(doc.uploadedBy));
    tr.append(cell(roleText(doc.uploadRole)));
    tr.append(cell(visibilityText(doc.visibility)));

    const statusCell = document.createElement('td');
    statusCell.innerHTML = `
      <span class="status-badge ${statusBadgeClass(doc.processStatus)}">
        ${escapeHtml(doc.processStatus || '待处理')}
      </span>
    `;
    tr.append(statusCell);

    tr.append(cell(formatDateTime(doc.createdAt)));

    const errorCell = document.createElement('td');
    errorCell.className = 'error-text';
    errorCell.title = doc.errorMessage || '';
    errorCell.textContent = doc.errorMessage || '-';
    tr.append(errorCell);

    const actionCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    actions.appendChild(createDeleteButton(() => deleteAdminDocument(doc.id, doc.fileName)));
    actionCell.appendChild(actions);
    tr.append(actionCell);

    adminDocumentsBody.appendChild(tr);
  });
}

function applyDocumentSearch() {
  const keyword = (adminDocumentSearch?.value || '').trim().toLowerCase();

  if (!keyword) {
    renderAdminDocumentTable(adminDocumentRows);
    return;
  }

  const filtered = adminDocumentRows.filter((doc) => (
    textIncludes(doc.fileName, keyword)
      || textIncludes(doc.storedName, keyword)
      || textIncludes(doc.uploadedBy, keyword)
      || textIncludes(doc.uploadRole, keyword)
      || textIncludes(doc.visibility, keyword)
      || textIncludes(doc.processStatus, keyword)
      || textIncludes(doc.errorMessage, keyword)
  ));

  renderAdminDocumentTable(filtered);
}

async function loadDocuments() {
  if (!adminDocumentsBody) return;
  try {
    const rows = await requestJson('/admin/documents');
    adminDocumentRows = rows;
    renderAdminUploadList(rows);
    applyDocumentSearch();
    syncDocumentPolling(rows);
  } catch (error) {
    console.warn('加载文档失败', error);
    adminDocumentsBody.innerHTML = '<tr><td colspan="8" class="empty-table-cell">文档加载失败</td></tr>';
    if (adminUploadList) {
      adminUploadList.innerHTML = '<div class="empty-hint">管理员文档加载失败</div>';
    }
  }
}

async function loadUsers() {
  if (!adminUsersBody) return;
  try {
    const rows = await requestJson('/admin/users');
    adminUserRows = rows;
    applyUserSearch();
  } catch (error) {
    console.warn('加载用户失败', error);
    adminUsersBody.innerHTML = '<tr><td colspan="6" class="empty-table-cell">用户加载失败</td></tr>';
  }
}

function renderActivities(rows = []) {
  if (!adminActivityList) return;

  adminActivityList.innerHTML = '';

  if (!rows.length) {
    adminActivityList.innerHTML = '<div class="empty-hint">暂无近期活动</div>';
    return;
  }

  rows.forEach((activity) => {
    const row = document.createElement('div');
    row.className = 'activity-row';
    row.innerHTML = `
      <strong>${escapeHtml(activity.actorName || 'system')}</strong>
      <div class="activity-detail">
        <span>${escapeHtml(activity.message || activity.action || '-')}</span>
        <small>${formatDateTime(activity.createdAt)}</small>
      </div>
    `;
    adminActivityList.appendChild(row);
  });
}

async function loadActivities() {
  if (!adminActivityList) return;

  try {
    const rows = await requestJson('/admin/activities');
    renderActivities(rows);
  } catch (error) {
    console.warn('加载近期活动失败', error);
    adminActivityList.innerHTML = '<div class="empty-hint">近期活动加载失败</div>';
  }
}

function renderAdminUserTable(rows = []) {
  if (!adminUsersBody) return;

  adminUsersBody.innerHTML = '';

  if (!rows.length) {
    adminUsersBody.innerHTML = '<tr><td colspan="6" class="empty-table-cell">暂无用户</td></tr>';
    return;
  }

  rows.forEach((user) => {
    const tr = document.createElement('tr');

    tr.append(cell(user.username || '-'));
    tr.append(cell(user.phone || '-'));
    tr.append(cell(roleText(user.role)));

    const statusCell = document.createElement('td');
    statusCell.innerHTML = `
      <span class="status-badge ${user.status === 1 ? 'success' : 'danger'}">
        ${statusText(user.status)}
      </span>
    `;
    tr.append(statusCell);

    tr.append(cell(formatDateTime(user.createdAt)));

    const actionCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    actions.appendChild(createStatusButton(user));
    actionCell.appendChild(actions);
    tr.append(actionCell);

    adminUsersBody.appendChild(tr);
  });
}

function applyUserSearch() {
  const keyword = (adminUserSearch?.value || '').trim().toLowerCase();

  if (!keyword) {
    renderAdminUserTable(adminUserRows);
    return;
  }

  const filtered = adminUserRows.filter((user) => (
    textIncludes(user.username, keyword)
      || textIncludes(user.phone, keyword)
      || textIncludes(user.role, keyword)
      || textIncludes(roleText(user.role), keyword)
      || textIncludes(statusText(user.status), keyword)
  ));

  renderAdminUserTable(filtered);
}

async function updateUserStatus(user, nextStatus) {
  const actionText = nextStatus === 1 ? '启用' : '禁用';
  const confirmed = window.confirm(`确认${actionText}用户「${user.username || user.phone}」吗？`);
  if (!confirmed) return;

  try {
    await requestJson(`/admin/users/${user.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: nextStatus })
    });
    await loadUsers();
    await loadOverview();
    await loadActivities();
    alert(`用户已${actionText}`);
  } catch (error) {
    alert(`${actionText}失败：${error.message}`);
  }
}

const adminUploadButton = document.querySelector('.admin-dropzone .primary-btn');
if (adminUploadButton) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.pdf';
  input.multiple = true;
  input.hidden = true;
  document.body.appendChild(input);
  adminUploadButton.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    if (!input.files.length) return;
    const formData = new FormData();
    [...input.files].forEach((file) => formData.append('files', file));
    try {
      const response = await fetch(`${API_BASE}/admin/documents/upload`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData
      });
      if (!response.ok) throw new Error(await response.text());
      await loadDocuments();
      await loadOverview();
      await loadActivities();
      alert('管理员文档已提交入库流程');
    } catch (error) {
      alert(`上传失败：${error.message}`);
    } finally {
      input.value = '';
    }
  });
}

if (adminDocumentSearch) {
  adminDocumentSearch.addEventListener('input', applyDocumentSearch);
}

if (adminUserSearch) {
  adminUserSearch.addEventListener('input', applyUserSearch);
}

loadOverview();
loadActivities();
loadDocuments();
loadUsers();
