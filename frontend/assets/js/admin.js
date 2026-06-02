const adminNavButtons = document.querySelectorAll('.admin-shell .nav-item');
const adminTitle = document.getElementById('admin-view-title');
const adminDocumentsBody = document.getElementById('admin-documents-body');
const adminUploadList = document.getElementById('admin-upload-list');
const adminDocumentSearch = document.getElementById('admin-document-search');
const adminUsersBody = document.getElementById('admin-users-body');
const adminUserSearch = document.getElementById('admin-user-search');
const adminActivityList = document.getElementById('admin-activity-list');
const ragDebugQuestion = document.getElementById('rag-debug-question');
const ragDebugTopK = document.getElementById('rag-debug-topk');
const ragDebugRun = document.getElementById('rag-debug-run');
const ragDebugStatus = document.getElementById('rag-debug-status');
const ragDebugResults = document.getElementById('rag-debug-results');
const ragQualityRefresh = document.getElementById('rag-quality-refresh');
const ragQualityMetrics = document.getElementById('rag-quality-metrics');
const ragQualityDuplicates = document.getElementById('rag-quality-duplicates');
const ragQualityCrossDocument = document.getElementById('rag-quality-cross-document');
const ragQualityLongTexts = document.getElementById('rag-quality-long-texts');
const ragQualityStatus = document.getElementById('rag-quality-status');
const ragOpsRefresh = document.getElementById('rag-ops-refresh');
const ragOpsState = document.getElementById('rag-ops-state');
const ragOpsUpdated = document.getElementById('rag-ops-updated');
const ragOpsMetrics = document.getElementById('rag-ops-metrics');
const ragOpsWarnings = document.getElementById('rag-ops-warnings');
const ragOpsLastOperation = document.getElementById('rag-ops-last-operation');
let adminDocumentRows = [];
let adminUserRows = [];
let adminDocumentPollTimer = null;
const RAG_SERVICE_BASE = window.RAG_SERVICE_BASE || 'http://127.0.0.1:8000';

const loginUser = currentUser();
if (window.DAM_RAG_LOGIN_REQUIRED || !localStorage.getItem('dam_rag_token') || !loginUser || loginUser.role !== 'admin') {
  window.location.replace('./index.html');
  throw new Error('Login required');
}

const adminTitles = {
  overview: '平台总览',
  library: '文档库管理',
  operations: 'RAG 运维',
  users: '用户管理'
};

adminNavButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const target = button.dataset.view;
    if (adminTitle && adminTitles[target]) {
      adminTitle.textContent = adminTitles[target];
    }
    if (target === 'operations') {
      loadOperationalStatus();
      loadQualityReport();
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
      await loadQualityReport();
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

function createRetryButton(documentId) {
  const button = document.createElement('button');
  button.className = 'soft-btn action-btn';
  button.type = 'button';
  button.textContent = '重新入库';
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await requestJson(`/admin/documents/${documentId}/retry`, { method: 'POST' });
      await loadDocuments();
      await loadActivities();
    } catch (error) {
      showAppAlert(`重新入库失败：${error.message}`, '重新入库失败');
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

function createPageOffsetButton(doc) {
  const button = document.createElement('button');
  button.className = 'soft-btn action-btn';
  button.type = 'button';
  button.textContent = '页码校正';
  button.title = doc.pageOffset === null || doc.pageOffset === undefined
    ? '设置文档印刷页码与 PDF 页码的对应关系'
    : `当前页码偏移量：${doc.pageOffset}`;
  button.addEventListener('click', async () => {
    const pdfPageValue = await showAppPrompt('输入 PDF 阅读器显示的页码，用于定位截图。', {
      title: '校正 PDF 页码',
      label: 'PDF 页码',
      placeholder: '例如：13',
      validate: (value) => Number.isInteger(Number(value)) && Number(value) > 0 ? '' : '请输入大于 0 的整数'
    });
    if (pdfPageValue === null) return;
    const pdfPage = Number(pdfPageValue);
    const documentPageValue = await showAppPrompt('输入同一页在文档正文中印刷的页码。', {
      title: '校正文档页码',
      label: '文档页码',
      placeholder: '例如：5',
      validate: (value) => Number.isInteger(Number(value)) && Number(value) > 0 ? '' : '请输入大于 0 的整数'
    });
    if (documentPageValue === null) return;
    const documentPage = Number(documentPageValue);

    button.disabled = true;
    try {
      await requestJson(`/admin/documents/${doc.id}/page-offset`, {
        method: 'PATCH',
        body: JSON.stringify({ pdfPage, documentPage })
      });
      await loadDocuments();
      await loadActivities();
      showAppAlert('页码校正已保存，文档正在重新入库');
    } catch (error) {
      showAppAlert(`页码校正失败：${error.message}`, '页码校正失败');
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

function ensureDeleteConfirmModal() {
  let modal = document.getElementById('document-delete-confirm-modal');
  if (modal) return modal;

  modal = document.createElement('div');
  modal.className = 'modal-backdrop hide';
  modal.id = 'document-delete-confirm-modal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-labelledby', 'document-delete-confirm-title');
  modal.innerHTML = `
    <div class="settings-modal">
      <div class="modal-header">
        <h3 id="document-delete-confirm-title">确认删除文档</h3>
        <button class="icon-text-btn" type="button" data-action="cancel-document-delete" aria-label="关闭">×</button>
      </div>
      <p class="modal-phone-text" data-delete-document-name></p>
      <p class="settings-message" data-delete-document-status></p>
      <div class="modal-actions">
        <button class="soft-btn" type="button" data-action="cancel-document-delete">取消</button>
        <button class="danger-btn" type="button" data-action="confirm-document-delete">确认删除</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  modal.addEventListener('click', (event) => {
    if (event.target === modal || event.target.closest('[data-action="cancel-document-delete"]')) {
      modal.classList.add('hide');
    }
  });
  return modal;
}

function showDeleteConfirmModal(documentId, fileName) {
  const modal = ensureDeleteConfirmModal();
  const name = modal.querySelector('[data-delete-document-name]');
  const status = modal.querySelector('[data-delete-document-status]');
  const confirmButton = modal.querySelector('[data-action="confirm-document-delete"]');
  const nextButton = confirmButton.cloneNode(true);

  name.textContent = `确认删除文档《${fileName}》吗？删除后系统会同步移除对应的向量数据。`;
  status.textContent = '';
  nextButton.disabled = false;
  nextButton.textContent = '确认删除';
  confirmButton.replaceWith(nextButton);
  nextButton.addEventListener('click', () => deleteAdminDocument(documentId, modal));
  modal.classList.remove('hide');
}

async function deleteAdminDocument(documentId, modal) {
  const confirmButton = modal.querySelector('[data-action="confirm-document-delete"]');
  const status = modal.querySelector('[data-delete-document-status]');

  confirmButton.disabled = true;
  confirmButton.textContent = '正在删除';
  status.textContent = '';
  try {
    await requestJson(`/admin/documents/${documentId}`, { method: 'DELETE' });
    await loadDocuments();
    await loadOverview();
    await loadActivities();
    modal.classList.add('hide');
  } catch (error) {
    status.textContent = `删除失败：${error.message}`;
    confirmButton.disabled = false;
    confirmButton.textContent = '确认删除';
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
    if (String(doc.processStatus || '').includes('失败')) {
      actions.appendChild(createRetryButton(doc.id));
    }
    actions.appendChild(createPageOffsetButton(doc));
    actions.appendChild(createDeleteButton(() => showDeleteConfirmModal(doc.id, doc.fileName)));
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
    if (String(doc.processStatus || '').includes('失败')) {
      actions.appendChild(createRetryButton(doc.id));
    }
    actions.appendChild(createPageOffsetButton(doc));
    actions.appendChild(createDeleteButton(() => showDeleteConfirmModal(doc.id, doc.fileName)));
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

function qualityMetric(label, value, tone = '') {
  return `
    <div class="quality-metric ${tone}">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
    </div>
  `;
}

function renderOperationalStatus(report = {}) {
  const stateMap = {
    ok: ['正常', 'success'],
    warning: ['注意', 'processing'],
    error: ['异常', 'danger']
  };
  const [stateText, stateClass] = stateMap[report.status] || stateMap.error;
  if (ragOpsState) {
    ragOpsState.textContent = stateText;
    ragOpsState.className = `status-badge ${stateClass}`;
  }
  if (ragOpsUpdated) {
    ragOpsUpdated.textContent = `最近检查：${new Date().toLocaleString('zh-CN')}`;
  }
  if (ragOpsMetrics) {
    ragOpsMetrics.innerHTML = [
      qualityMetric('结构化文档', report.structured_documents ?? '-'),
      qualityMetric('结构化条款', report.structured_clauses ?? '-'),
      qualityMetric('预期向量块', report.expected_chunks ?? '-'),
      qualityMetric('实际向量块', report.actual_chunks ?? '-', report.consistent === false ? 'danger' : ''),
      qualityMetric('模型配置', report.dashscope_configured ? '已配置' : '未配置', report.dashscope_configured ? '' : 'danger'),
      qualityMetric('数据一致性', report.consistent ? '一致' : '需检查', report.consistent ? '' : 'danger')
    ].join('');
  }

  const warnings = report.warnings || [];
  if (ragOpsWarnings) {
    ragOpsWarnings.innerHTML = warnings.length
      ? warnings.map((item) => `<span>${escapeHtml(item)}</span>`).join('')
      : '<span class="quality-empty">未发现异常</span>';
  }

  const operation = report.last_operation || {};
  if (ragOpsLastOperation) {
    ragOpsLastOperation.innerHTML = `
      <strong>${escapeHtml(operation.action || '-')} · ${escapeHtml(operation.status || '-')}</strong>
      <span>${escapeHtml(operation.message || '-')}</span>
      <span>${escapeHtml(operation.updated_at || '尚无写操作记录')}</span>
    `;
  }
}

async function loadOperationalStatus() {
  if (!ragOpsMetrics) return;
  if (ragOpsState) {
    ragOpsState.textContent = '正在检查';
    ragOpsState.className = 'status-badge processing';
  }
  try {
    const response = await fetch(`${RAG_SERVICE_BASE}/health`);
    if (!response.ok) throw new Error(await response.text());
    renderOperationalStatus(await response.json());
  } catch (error) {
    renderOperationalStatus({
      status: 'error',
      consistent: false,
      warnings: [`RAG 服务连接失败：${error.message}`]
    });
  }
}

function renderQualityChipList(element, items = []) {
  if (!element) return;
  if (!items.length) {
    element.innerHTML = '<span class="quality-empty">无</span>';
    return;
  }
  element.innerHTML = items
    .map((item) => `<span>${escapeHtml(formatQualityChip(item))}</span>`)
    .join('');
}

function formatQualityChip(item) {
  if (typeof item !== 'object' || item === null) return item;
  if (item.document_key) {
    return `${item.document_key} · ${item.clause_id} × ${item.count}`;
  }
  if (item.document_count) {
    return `${item.clause_id} · ${item.document_count} 份文档`;
  }
  return JSON.stringify(item);
}

function renderQualityLongTexts(items = []) {
  if (!ragQualityLongTexts) return;
  if (!items.length) {
    ragQualityLongTexts.innerHTML = '<span class="quality-empty">无</span>';
    return;
  }
  ragQualityLongTexts.innerHTML = items.map((item) => `
    <article>
      <strong>${escapeHtml(item.clause_id || '-')} · ${escapeHtml(item.length || '-')} 字</strong>
      <span>${escapeHtml(item.chapter || '-')}</span>
      <p>${escapeHtml(item.preview || '')}</p>
    </article>
  `).join('');
}

function renderQualityReport(report = {}) {
  if (ragQualityMetrics) {
    ragQualityMetrics.innerHTML = [
      qualityMetric('条文节点', report.total_clauses ?? '-'),
      qualityMetric('文档内重复', report.duplicate_within_document_count ?? report.duplicate_clause_id_count ?? '-', report.duplicate_clause_id_count ? 'danger' : ''),
      qualityMetric('跨文档同编号', report.duplicate_across_documents_count ?? '-'),
      qualityMetric('空内容', report.empty_content_count ?? '-', report.empty_content_count ? 'danger' : ''),
      qualityMetric('缺失 page', report.missing_page_count ?? '-', report.missing_page_count ? 'danger' : ''),
      qualityMetric('缺失 bbox', report.missing_bbox_count ?? '-', report.missing_bbox_count ? 'danger' : ''),
      qualityMetric('长文本', report.long_text_count ?? '-', report.long_text_count ? 'warn' : ''),
    ].join('');
  }
  renderQualityChipList(ragQualityDuplicates, report.sample_duplicate_clause_ids || []);
  renderQualityChipList(ragQualityCrossDocument, report.sample_cross_document_clause_ids || []);
  renderQualityLongTexts(report.sample_long_texts || []);
}

async function loadQualityReport() {
  if (!ragQualityMetrics) return;
  if (ragQualityStatus) ragQualityStatus.textContent = '正在加载质量报告...';
  try {
    const response = await fetch(`${RAG_SERVICE_BASE}/api/rag/quality`);
    if (!response.ok) throw new Error(await response.text());
    const report = await response.json();
    renderQualityReport(report);
    if (ragQualityStatus) {
      ragQualityStatus.textContent = `报告已更新：${report.json_path || ''}`;
    }
  } catch (error) {
    if (ragQualityStatus) ragQualityStatus.textContent = `质量报告加载失败：${error.message}`;
    if (ragQualityMetrics) {
      ragQualityMetrics.innerHTML = '<div class="empty-hint">请确认 RAG 服务已启动并完成至少一次入库。</div>';
    }
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

function debugMetaValue(metadata = {}, key) {
  const value = metadata[key];
  return value === undefined || value === null || value === '' ? '-' : String(value);
}

function displayDebugSourceName(value = '') {
  return String(value || '-')
    .replace(/\.pdf$/i, '')
    .replace(/^(user|admin)_\d+_\d{14}_/, '')
    .replace(/\+/g, ' ')
    .replace(/^DLT\s+/i, 'DL/T ');
}

function renderRagDebugResults(results = []) {
  if (!ragDebugResults) return;
  if (!results.length) {
    ragDebugResults.innerHTML = '<div class="empty-hint">没有召回结果</div>';
    return;
  }

  ragDebugResults.innerHTML = '';
  results.forEach((item) => {
    const metadata = item.metadata || {};
    const card = document.createElement('article');
    card.className = 'rag-debug-card';
    card.innerHTML = `
      <div class="rag-debug-card-head">
        <strong>#${escapeHtml(item.rank || '-')} ${escapeHtml(displayDebugSourceName(debugMetaValue(metadata, 'source_file')))}</strong>
        <span>${escapeHtml(debugMetaValue(metadata, 'clause_id'))}</span>
      </div>
      <div class="rag-debug-meta">
        <span>document_page: ${escapeHtml(debugMetaValue(metadata, 'document_page'))}</span>
        <span>pdf_page: ${escapeHtml(debugMetaValue(metadata, 'page'))}</span>
        <span>document_id: ${escapeHtml(debugMetaValue(metadata, 'document_id'))}</span>
        <span>chunk: ${escapeHtml(debugMetaValue(metadata, 'chunk_index'))}</span>
      </div>
      <p>${escapeHtml(item.content_preview || '')}</p>
      <details>
        <summary>查看 metadata</summary>
        <pre>${escapeHtml(JSON.stringify(metadata, null, 2))}</pre>
      </details>
    `;
    ragDebugResults.appendChild(card);
  });
}

async function ragDebugError(response) {
  const text = await response.text();
  try {
    const payload = JSON.parse(text);
    const detail = payload.detail || {};
    if (typeof detail === 'object') {
      const code = detail.error_code || 'RAG_ERROR';
      return `[${code}] ${detail.message || 'RAG 服务调用失败'}\n${detail.detail || ''}`.trim();
    }
  } catch {
    // Keep the raw response when the service does not return structured JSON.
  }
  return text || `RAG HTTP ${response.status}`;
}

async function runRagDebugSearch() {
  if (!ragDebugQuestion || !ragDebugRun) return;
  const question = ragDebugQuestion.value.trim();
  const topK = Math.min(Math.max(Number(ragDebugTopK?.value || 5), 1), 20);

  if (!question) {
    if (ragDebugStatus) ragDebugStatus.textContent = '请输入测试问题';
    return;
  }

  ragDebugRun.disabled = true;
  if (ragDebugStatus) ragDebugStatus.textContent = '正在检索...';
  if (ragDebugResults) {
    ragDebugResults.innerHTML = '<div class="empty-hint">正在召回向量片段...</div>';
  }

  try {
    const response = await fetch(`${RAG_SERVICE_BASE}/api/rag/debug/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, topK })
    });
    if (!response.ok) throw new Error(await ragDebugError(response));
    const data = await response.json();
    renderRagDebugResults(data.results || []);
    if (ragDebugStatus) {
      ragDebugStatus.textContent = `完成：召回 ${(data.results || []).length} 条`;
    }
  } catch (error) {
    if (ragDebugStatus) ragDebugStatus.textContent = `调试失败：${error.message}`;
    if (ragDebugResults) {
      ragDebugResults.innerHTML = '<div class="empty-hint">调试接口调用失败，请确认 RAG 服务已启动。</div>';
    }
  } finally {
    ragDebugRun.disabled = false;
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
  const confirmed = await showAppConfirm(`确认${actionText}用户「${user.username || user.phone}」吗？`, '用户状态变更');
  if (!confirmed) return;

  try {
    await requestJson(`/admin/users/${user.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: nextStatus })
    });
    await loadUsers();
    await loadOverview();
    await loadActivities();
    showAppAlert(`用户已${actionText}`);
  } catch (error) {
    showAppAlert(`${actionText}失败：${error.message}`, '操作失败');
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
      showAppAlert('管理员文档已提交入库流程');
    } catch (error) {
      showAppAlert(`上传失败：${error.message}`, '上传失败');
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

if (ragDebugRun) {
  ragDebugRun.addEventListener('click', runRagDebugSearch);
}

if (ragDebugQuestion) {
  ragDebugQuestion.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      runRagDebugSearch();
    }
  });
}

if (ragQualityRefresh) {
  ragQualityRefresh.addEventListener('click', loadQualityReport);
}

if (ragOpsRefresh) {
  ragOpsRefresh.addEventListener('click', loadOperationalStatus);
}

function initializeAdminPage() {
  document.documentElement.classList.remove('auth-checking');
  loadOverview();
  loadActivities();
  loadDocuments();
  loadUsers();
  loadQualityReport();
}

(window.DAM_RAG_AUTH_READY || Promise.resolve(loginUser))
  .then((user) => {
    if (!user || user.role !== 'admin' || window.DAM_RAG_LOGIN_REQUIRED) {
      clearSession();
      window.location.replace('./index.html');
      return;
    }
    initializeAdminPage();
  })
  .catch(() => {});
