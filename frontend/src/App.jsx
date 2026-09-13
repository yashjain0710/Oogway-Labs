import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { Md, ArtifactViewer } from './components.jsx';

const EXAMPLES = [
  'What are the most important lessons on product-market fit?',
  'How should a startup think about growth loops?',
  'Turn the lessons into a Ship 30 for 30-style essay.',
  'Create a Markdown product strategy document from this conversation.',
];

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [current, setCurrent] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [models, setModels] = useState(null);
  const [health, setHealth] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [artLoading, setArtLoading] = useState(false);
  const [artError, setArtError] = useState('');
  const [showArtifact, setShowArtifact] = useState(true);
  const bottom = useRef(null);

  const loadSessions = useCallback(async () => {
    try { setSessions(await api.sessions()); } catch { /* backend down: header shows it */ }
  }, []);

  useEffect(() => {
    loadSessions();
    api.models().then(setModels).catch(() => {});
    api.health().then(setHealth).catch(() => setHealth({ status: 'unreachable', database: 'unreachable', ollama: 'unreachable' }));
  }, [loadSessions]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);

  const openSession = async (id) => {
    setCurrent(id);
    setArtifact(null); setArtError('');
    try { setMessages(await api.messages(id)); } catch (e) { setErr(friendly(e)); }
  };

  const newChat = async () => {
    setCurrent(null); setMessages([]); setArtifact(null); setArtError(''); setErr('');
  };

  const removeSession = async (id) => {
    try { await api.deleteSession(id); } catch (e) { setErr(friendly(e)); return; }
    setSessions((s) => s.filter((x) => x.id !== id));
    if (current === id) { setCurrent(null); setMessages([]); }
  };

  const loadArtifact = async (id) => {
    setShowArtifact(true); setArtLoading(true); setArtError('');
    try { setArtifact(await api.artifact(id)); }
    catch (e) { setArtError(friendly(e)); }
    finally { setArtLoading(false); }
  };

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setBusy(true); setErr('');
    setMessages((m) => [...m, { id: 'tmp-u', role: 'user', content: msg, created_at: new Date().toISOString() }]);
    setInput('');
    try {
      const res = await api.chat(current, msg);
      if (!current || res.session_id !== current) {
        setCurrent(res.session_id);
        loadSessions();
      }
      setMessages((m) => [...m, { id: 'tmp-a' + Date.now(), role: 'assistant', content: res.answer, sources: res.sources, route: res.route, created_at: new Date().toISOString() }]);
      if (res.artifact_id) loadArtifact(res.artifact_id);
    } catch (e) {
      setErr(friendly(e));
      setMessages((m) => [...m, { id: 'tmp-e' + Date.now(), role: 'assistant', content: '⚠️ ' + friendly(e), created_at: new Date().toISOString() }]);
    } finally { setBusy(false); }
  };

  const degraded = health && health.status !== 'ok';

  return (
    <div className="app">
      <aside className="side" aria-label="Sessions">
        <div className="brand"><span className="logo">L</span><div><b>Lenny Growth Assistant</b><small>Grounded in Lenny’s Podcast</small></div></div>
        <button className="new" onClick={newChat}>+ New chat</button>
        <div className="sess-list">
          {sessions.map((s) => (
            <div key={s.id} className={'sess' + (s.id === current ? ' on' : '')}>
              <button className="sess-open" onClick={() => openSession(s.id)} title={s.title}>{s.title || 'Untitled'}</button>
              <button className="sess-del" onClick={() => removeSession(s.id)} aria-label={`Delete ${s.title}`}>✕</button>
            </div>
          ))}
          {sessions.length === 0 && <p className="muted">No chats yet — start one below.</p>}
        </div>
        <div className="model-chip" title="Active LLM provider/model">
          ● {models ? `${models.active_provider} / ${models.active_model}` : 'loading model…'}
        </div>
      </aside>

      <main className="chat-col">
        {degraded && (
          <div className="banner" role="alert">
            Backend {health.status}: DB {health.database} · Ollama {health.ollama}. {health.ollama?.includes('start') ? 'Run `ollama serve` + `ollama pull qwen2.5:3b`.' : 'See README troubleshooting.'}
          </div>
        )}
        <div className="thread" aria-live="polite">
          {messages.length === 0 && (
            <div className="hero">
              <h1>Ask Lenny’s Podcast anything about product &amp; growth</h1>
              <p>Every answer is grounded in transcript excerpts with source citations. Follow-ups keep session context.</p>
              <div className="examples">
                {EXAMPLES.map((e) => <button key={e} onClick={() => send(e)}>{e}</button>)}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={'msg ' + m.role}>
              <div className="bubble">
                {m.role === 'assistant' ? <Md>{m.content}</Md> : m.content}
                {m.sources?.length > 0 && (
                  <div className="sources">
                    {m.sources.map((s, i) => (
                      <details key={i} className="src"><summary><b>[S{i + 1}]</b> {s.title}</summary>
                        <p className="muted">{s.url || s.source_id}</p><p>{s.excerpt}</p>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && <div className="msg assistant"><div className="bubble typing" aria-label="Assistant is thinking"><span /><span /><span /></div></div>}
          <div ref={bottom} />
        </div>
        {err && !busy && <div className="send-err" role="alert">{err}</div>}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <label className="sr" htmlFor="chat-input">Message</label>
          <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about PMF, growth loops, onboarding… or request an essay / artifact" autoComplete="off" />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send message">Send</button>
          {!showArtifact && artifact && <button type="button" onClick={() => setShowArtifact(true)}>Show artifact</button>}
        </form>
      </main>

      {showArtifact && (
        <ArtifactViewer artifact={artifact} loading={artLoading} error={artError} onClose={() => setShowArtifact(false)} />
      )}
    </div>
  );
}

function friendly(e) {
  if (!e) return 'Something went wrong.';
  if (e.status === 503) return e.body?.error || 'Model unavailable. Start Ollama (`ollama serve`, `ollama pull qwen2.5:3b`) or configure a cloud key — see README.';
  if (e.message?.includes('Failed to fetch')) return 'Cannot reach the backend at :8000. Run `uvicorn backend.app.main:app` (see README).';
  return e.body?.error || e.message || 'Something went wrong.';
}
