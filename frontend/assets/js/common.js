const API_BASE = window.API_BASE || 'http://localhost:8080/api';

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('dam_rag_user') || 'null');
  } catch {
    return null;
  }
}

function saveSession(data) {
  localStorage.setItem('dam_rag_token', data.token || '');
  localStorage.setItem('dam_rag_user', JSON.stringify(data.user));
}

function clearSession() {
  localStorage.removeItem('dam_rag_token');
  localStorage.removeItem('dam_rag_user');
}

function requireSession() {
  if (!document.querySelector('.app-shell')) return;
  const token = localStorage.getItem('dam_rag_token') || '';
  const user = currentUser();
  if (!token || !user) {
    window.DAM_RAG_LOGIN_REQUIRED = true;
    clearSession();
    window.location.href = './index.html';
  }
}

async function requestJson(path, options = {}) {
  const token = localStorage.getItem('dam_rag_token') || '';
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || `请求失败：${response.status}`;
    try {
      const payload = JSON.parse(text);
      message = payload.message || payload.error || payload.detail || message;
    } catch {
      // Keep the raw response text if it is not JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  const text = await response.text();
  return text ? text : null;
}

async function endSession() {
  try {
    if (localStorage.getItem('dam_rag_token')) {
      await requestJson('/auth/logout', { method: 'POST' });
    }
  } catch (error) {
    console.warn('退出登录接口调用失败', error);
  } finally {
    clearSession();
    window.location.href = './index.html';
  }
}

function ensureLogoutConfirmModal() {
  let modal = document.getElementById('logout-confirm-modal');
  if (modal) return modal;

  modal = document.createElement('div');
  modal.className = 'modal-backdrop hide';
  modal.id = 'logout-confirm-modal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-labelledby', 'logout-confirm-title');
  modal.innerHTML = `
    <div class="settings-modal logout-confirm-dialog">
      <div class="modal-header">
        <h3 id="logout-confirm-title">确认退出登录</h3>
        <button class="icon-text-btn" type="button" data-action="cancel-logout" aria-label="关闭">×</button>
      </div>
      <p class="modal-phone-text">退出后需要重新登录才能继续使用当前账号。</p>
      <div class="modal-actions">
        <button class="soft-btn" type="button" data-action="cancel-logout">取消</button>
        <button class="danger-btn" type="button" data-action="confirm-logout">退出登录</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  modal.addEventListener('click', (event) => {
    if (event.target === modal || event.target.closest('[data-action="cancel-logout"]')) {
      modal.classList.add('hide');
    }
  });

  modal.querySelector('[data-action="confirm-logout"]')?.addEventListener('click', endSession);
  return modal;
}

function showLogoutConfirm() {
  ensureLogoutConfirmModal().classList.remove('hide');
}

function switchAccount() {
  clearSession();
  window.location.href = './index.html';
}

function renderAccountIdentity(user = currentUser()) {
  if (!user) return;
  const displayName = user.username || user.phone || user.role || '当前账号';
  document.querySelectorAll('#current-user-name, [data-account-name]').forEach((element) => {
    element.textContent = displayName;
  });
  document.querySelectorAll('[data-account-avatar]').forEach((element) => {
    element.textContent = displayName.trim().slice(0, 1).toUpperCase() || 'U';
  });
}

requireSession();
renderAccountIdentity();

document.querySelectorAll('.account-menu').forEach((menu) => {
  const toggle = menu.querySelector('.account-menu-toggle');
  const panel = menu.querySelector('.account-menu-panel');
  if (!toggle || !panel) return;

  toggle.addEventListener('click', (event) => {
    event.stopPropagation();
    const willOpen = panel.hidden;
    document.querySelectorAll('.account-menu-panel').forEach((item) => {
      item.hidden = true;
      item.closest('.account-menu')?.querySelector('.account-menu-toggle')?.setAttribute('aria-expanded', 'false');
    });
    panel.hidden = !willOpen;
    toggle.setAttribute('aria-expanded', String(willOpen));
  });
});

document.addEventListener('click', () => {
  document.querySelectorAll('.account-menu-panel').forEach((panel) => {
    panel.hidden = true;
    panel.closest('.account-menu')?.querySelector('.account-menu-toggle')?.setAttribute('aria-expanded', 'false');
  });
});

document.querySelectorAll('[data-action="switch-account"]').forEach((button) => {
  button.addEventListener('click', switchAccount);
});

document.querySelectorAll('[data-action="logout"]').forEach((button) => {
  button.addEventListener('click', showLogoutConfirm);
});

document.querySelectorAll('.app-shell').forEach((shell, shellIndex) => {
  const toggleButton = shell.querySelector('.sidebar-toggle-btn');
  const toggleIcon = shell.querySelector('.sidebar-toggle-icon');
  if (!toggleButton) return;

  const storageKey = `dam_sidebar_collapsed_${shell.classList.contains('admin-shell') ? 'admin' : `user_${shellIndex}`}`;
  const savedState = localStorage.getItem(storageKey);
  const initialCollapsed = savedState === 'true';

  function setSidebarCollapsed(collapsed) {
    shell.classList.toggle('sidebar-collapsed', collapsed);
    toggleButton.setAttribute('aria-expanded', String(!collapsed));
    toggleButton.setAttribute('aria-label', collapsed ? '展开侧边栏' : '折叠侧边栏');
    toggleButton.setAttribute('title', collapsed ? '展开侧边栏' : '折叠侧边栏');
    if (toggleIcon) {
      toggleIcon.textContent = collapsed ? '›' : '‹';
    }
    localStorage.setItem(storageKey, String(collapsed));
  }

  setSidebarCollapsed(initialCollapsed);

  toggleButton.addEventListener('click', () => {
    setSidebarCollapsed(!shell.classList.contains('sidebar-collapsed'));
  });
});

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    const view = item.dataset.view;
    const scope = item.closest('.app-shell');
    if (!scope) return;

    scope.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active'));
    item.classList.add('active');

    scope.querySelectorAll('.view').forEach((panel) => {
      panel.classList.toggle('active', panel.dataset.viewPanel === view);
    });

    const userTitle = scope.querySelector('#view-title');
    const adminTitle = scope.querySelector('#admin-view-title');

    if (userTitle) {
      const userTitles = {
        chat: '新建对话',
        docs: '个人文档',
        settings: '个人设置'
      };
      userTitle.textContent = userTitles[view] || userTitle.textContent;
    }

    if (adminTitle) {
      const adminTitles = {
        overview: '平台总览',
        library: '文档库管理',
        users: '用户管理'
      };
      adminTitle.textContent = adminTitles[view] || adminTitle.textContent;
    }
  });
});

const tabButtons = document.querySelectorAll('.tab-btn');
const tabForms = document.querySelectorAll('.auth-form');

tabButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const target = button.dataset.tab;
    tabButtons.forEach((tab) => tab.classList.remove('active'));
    button.classList.add('active');
    tabForms.forEach((form) => {
      form.classList.toggle('active', form.dataset.form === target);
    });
  });
});

const loginForm = document.querySelector('.auth-form[data-form="login"]');
if (loginForm) {
  loginForm.querySelector('.primary-btn')?.addEventListener('click', async () => {
    const [usernameInput, passwordInput] = loginForm.querySelectorAll('input');
    const roleText = loginForm.querySelector('select')?.value || '普通用户';
    const role = roleText.includes('管理员') ? 'admin' : 'user';
    try {
      const data = await requestJson('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          username: usernameInput.value.trim(),
          password: passwordInput.value,
          role
        })
      });
      saveSession(data);
      window.location.href = role === 'admin' ? './admin.html' : './user.html';
    } catch (error) {
      alert(`登录失败：${error.message}`);
    }
  });
}

const registerForm = document.querySelector('.auth-form[data-form="register"]');
if (registerForm) {
  registerForm.querySelector('.primary-btn')?.addEventListener('click', async () => {
    const [usernameInput, passwordInput, confirmInput] = registerForm.querySelectorAll('input');
    if (passwordInput.value !== confirmInput.value) {
      alert('两次输入的密码不一致');
      return;
    }
    try {
      const data = await requestJson('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: usernameInput.value.trim(),
          password: passwordInput.value
        })
      });
      saveSession(data);
      window.location.href = './user.html';
    } catch (error) {
      alert(`注册失败：${error.message}`);
    }
  });
}
