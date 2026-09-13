import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

/** Chat markdown: safe by default (react-markdown emits no raw HTML without rehype-raw). */
export function Md({ children }) {
  return (
    <div className="md">
      <ReactMarkdown>{children || ''}</ReactMarkdown>
    </div>
  );
}

/**
 * Artifact viewer: Markdown rendered safely; HTML rendered ONLY inside a
 * sandboxed iframe with NO scripts allowed (sandbox=""). Even if sanitization
 * missed something server-side, it cannot execute or reach parent state.
 */
export function ArtifactViewer({ artifact, loading, error, onClose }) {
  const [tab, setTab] = useState('preview'); // preview | code
  const [copied, setCopied] = useState(false);

  if (!artifact && !loading && !error) {
    return (
      <aside className="artifact empty" aria-label="Artifact viewer">
        <div className="artifact-empty">
          <h3>Artifact Viewer</h3>
          <p>Ask for a strategy doc, essay, or landing page — e.g. <em>“Create a Markdown product strategy document from this conversation.”</em></p>
          <ul>
            <li>Markdown docs render here</li>
            <li>HTML/CSS renders isolated &amp; script-free</li>
            <li>Switch to <b>Code</b> to copy the source</li>
          </ul>
        </div>
      </aside>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(artifact?.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable */ }
  };

  return (
    <aside className="artifact" aria-label="Artifact viewer">
      <div className="artifact-head">
        <div>
          <div className="artifact-kind">{artifact?.kind?.toUpperCase() || 'ARTIFACT'}</div>
          <h3>{artifact?.title || 'Generating…'}</h3>
        </div>
        <div className="artifact-actions">
          <div className="tabs" role="tablist" aria-label="Artifact view">
            <button role="tab" aria-selected={tab === 'preview'} className={tab === 'preview' ? 'on' : ''} onClick={() => setTab('preview')}>Preview</button>
            <button role="tab" aria-selected={tab === 'code'} className={tab === 'code' ? 'on' : ''} onClick={() => setTab('code')}>Code</button>
          </div>
          <button onClick={copy} disabled={!artifact} aria-label="Copy artifact source">{copied ? 'Copied ✓' : 'Copy'}</button>
          <button onClick={onClose} aria-label="Close artifact viewer">✕</button>
        </div>
      </div>
      <div className="artifact-body">
        {loading && <div className="state">Generating artifact…</div>}
        {error && <div className="state error" role="alert">Couldn’t generate the artifact: {error}</div>}
        {artifact && tab === 'code' && <pre className="code">{artifact.content}</pre>}
        {artifact && tab === 'preview' && artifact.kind === 'markdown' && <Md>{artifact.content}</Md>}
        {artifact && tab === 'preview' && artifact.kind === 'html' && (
          <iframe
            title={artifact.title}
            sandbox=""
            srcDoc={`<base target="_blank">${artifact.content}`}
            className="html-frame"
          />
        )}
      </div>
    </aside>
  );
}
