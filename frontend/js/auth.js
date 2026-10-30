/**
 * CapTax AI — Auth Client Utility
 * Handles session management, route guarding, and authenticated fetch.
 */

const AUTH_API = (window.CAPTAX_API_BASE || 'http://localhost:8001');

/**
 * Check if the current session is valid.
 * @returns {Promise<{authenticated: boolean, id: string|null}>}
 */
export async function getSession() {
  try {
    const res = await fetch(`${AUTH_API}/auth/me`, {
      credentials: 'include',
      headers: { 'Accept': 'application/json' },
    });
    if (res.ok) return await res.json();
    return { authenticated: false, id: null };
  } catch {
    return { authenticated: false, id: null };
  }
}

/**
 * Log in with ID and password.
 * @param {string} id
 * @param {string} password
 * @returns {Promise<{ok: boolean, error: string|null, retryAfter: number|null}>}
 */
export async function login(id, password) {
  try {
    const res = await fetch(`${AUTH_API}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, password }),
    });
    if (res.ok) return { ok: true, error: null, retryAfter: null };
    const body = await res.json().catch(() => ({}));
    const retryAfter = res.status === 429
      ? parseInt(res.headers.get('Retry-After') || '60', 10)
      : null;
    return { ok: false, error: body.detail || 'Invalid ID or password', retryAfter };
  } catch {
    return { ok: false, error: 'Cannot reach server — is the backend running?', retryAfter: null };
  }
}

/**
 * Log out and clear session cookie.
 */
export async function logout() {
  try {
    await fetch(`${AUTH_API}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch { /* ignore */ }
}

/**
 * Route guard for protected pages.
 * Call on /app pages: if not authenticated, redirects to /login?next=<currentPath>.
 * @returns {Promise<string|null>} user_id if authenticated, null if redirected
 */
export async function requireAuth() {
  const session = await getSession();
  if (!session.authenticated) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`/login?next=${next}`);
    return null;
  }
  return session.id;
}

/**
 * Authenticated fetch — adds credentials, handles 401 globally.
 * On 401: clears session, shows toast, redirects to /login.
 */
export async function authFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Accept': 'application/json',
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) {
    // Show toast if available
    if (typeof window.showToast === 'function') {
      window.showToast('Session expired — please log in again.', 'error');
    }
    const next = encodeURIComponent(window.location.pathname);
    setTimeout(() => window.location.replace(`/login?next=${next}`), 1200);
    throw new Error('Unauthorized — session expired');
  }

  return res;
}

/**
 * Theme helpers — shared across landing, login, and app.
 */
export function getTheme() {
  const saved = localStorage.getItem('captax-theme') || 'system';
  if (saved === 'system') {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  return saved;
}

export function applyTheme(theme) {
  const effective = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : theme;

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!prefersReduced) {
    document.documentElement.classList.add('theme-transitioning');
    setTimeout(() => document.documentElement.classList.remove('theme-transitioning'), 220);
  }

  document.documentElement.setAttribute('data-theme', effective);
  document.documentElement.style.colorScheme = effective;
  localStorage.setItem('captax-theme', theme);

  const meta = document.getElementById('metaThemeColor');
  if (meta) meta.setAttribute('content', effective === 'light' ? '#F3F1EE' : '#0c0c0e');
}

