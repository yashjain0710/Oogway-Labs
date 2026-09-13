const BASE = '';

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) {
    let body = null;
    try { body = await r.json(); } catch { /* non-json error */ }
    const err = new Error(body?.error || `Request failed (${r.status})`);
    err.status = r.status;
    err.body = body;
    throw err;
  }
  if (r.status === 204) return null;
  return r.json();
}

export const api = {
  health: () => req('/api/v1/health'),
  models: () => req('/api/v1/settings/models'),
  sessions: () => req('/api/v1/sessions'),
  createSession: (title) => req('/api/v1/sessions', { method: 'POST', body: JSON.stringify({ title: title || 'New chat' }) }),
  deleteSession: (id) => req(`/api/v1/sessions/${id}`, { method: 'DELETE' }),
  messages: (id) => req(`/api/v1/sessions/${id}/messages`),
  chat: (session_id, message) => req('/api/v1/chat', { method: 'POST', body: JSON.stringify({ session_id, message }) }),
  artifact: (id) => req(`/api/v1/artifacts/${id}`),
};
