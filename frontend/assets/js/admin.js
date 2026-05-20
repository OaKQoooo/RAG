const adminNavButtons = document.querySelectorAll('.admin-shell .nav-item');
const adminTitle = document.getElementById('admin-view-title');
const adminDocumentsBody = document.getElementById('admin-documents-body');
const adminUploadList = document.getElementById('admin-upload-list');

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

async function deleteAdminDocument(documentId, fileName) {
  const confirmed = window.confirm(`确认删除文档《${fileName}》吗？`);
  if (!confirmed) return;

  try {
    await requestJson(`/admin/documents/${documentId}`, { method: 'DELETE' });
    await loadDocuments();
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
        <span class="status-badge ${statusBadgeClass(doc.processStatus)}">${escapeHtml(doc.processStatus)}</span>
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

async function loadDocuments() {
  if (!adminDocumentsBody) return;
  try {
    const rows = await requestJson('/admin/documents');
    renderAdminUploadList(rows);
    adminDocumentsBody.innerHTML = '';
    if (!rows.length) {
      adminDocumentsBody.innerHTML = '<tr><td colspan="5" class="empty-table-cell">暂无文档</td></tr>';
      return;
    }
    rows.forEach((doc) => {
      const tr = document.createElement('tr');
      tr.append(cell(doc.fileName));
      tr.append(cell(doc.storedName));
      tr.append(cell(doc.uploadedBy));
      tr.append(cell(doc.uploadRole));
      const actionCell = document.createElement('td');
      const actions = document.createElement('div');
      actions.className = 'row-actions';
      actions.appendChild(createDeleteButton(() => deleteAdminDocument(doc.id, doc.fileName)));
      actionCell.appendChild(actions);
      tr.append(actionCell);
      adminDocumentsBody.appendChild(tr);
    });
  } catch (error) {
    console.warn('加载文档失败', error);
    adminDocumentsBody.innerHTML = '<tr><td colspan="5" class="empty-table-cell">文档加载失败</td></tr>';
    if (adminUploadList) {
      adminUploadList.innerHTML = '<div class="empty-hint">管理员文档加载失败</div>';
    }
  }
}

async function loadUsers() {
  const tbody = document.querySelector('[data-view-panel="users"] tbody');
  if (!tbody) return;
  try {
    const rows = await requestJson('/admin/users');
    tbody.innerHTML = '';
    rows.forEach((user) => {
      const tr = document.createElement('tr');
      tr.append(cell(user.username));
      tr.append(cell(user.role));
      const status = document.createElement('td');
      status.innerHTML = `<span class="status-badge ${user.status === 1 ? 'success' : 'danger'}">${user.status === 1 ? '启用' : '禁用'}</span>`;
      tr.append(status);
      tr.append(cell('-'));
      tbody.appendChild(tr);
    });
  } catch (error) {
    console.warn('加载用户失败', error);
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
    const user = currentUser() || { id: 1 };
    const formData = new FormData();
    [...input.files].forEach((file) => formData.append('files', file));
    try {
      const response = await fetch(`${API_BASE}/admin/documents/upload?userId=${user.id}`, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error(await response.text());
      await loadDocuments();
      alert('管理员文档已提交入库流程');
    } catch (error) {
      alert(`上传失败：${error.message}`);
    }
  });
}

loadOverview();
loadDocuments();
loadUsers();
