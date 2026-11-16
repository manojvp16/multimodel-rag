import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import Evidence from './Evidence.jsx';

function DocumentLibrary({ documents, loading, selected, busy, onSelect, onIndex, onDelete }) {
  if (loading && !documents.length) return <p className="muted">Loading your library…</p>;
  if (!documents.length) return <p className="muted">Your library is empty.</p>;
  return documents.map(document => {
    const id = document.document_id;
    const isBusy = busy.has(id);
    return (
      <div className="doc" key={id}>
        <label>
          <input type="checkbox" checked={selected.has(id)} onChange={() => onSelect(id)} />
          <span>{document.filename}</span>
        </label>
        <p><span className={`document-status ${document.indexStatus}`}>{isBusy ? 'Working…' : document.indexStatus === 'indexed' ? 'Ready to ask' : document.indexStatus.replaceAll('_', ' ')}</span><span>{document.page_count} {document.page_count === 1 ? 'page' : 'pages'}</span></p>
        <div className="actions">
          <button disabled={isBusy} onClick={() => onIndex(id)}>{document.indexStatus === 'indexed' ? 'Reindex' : 'Index'}</button>
          <a href={`/api/v1/documents/${id}/file`} target="_blank" rel="noopener noreferrer">Open PDF ↗</a>
          <button disabled={isBusy} onClick={() => onDelete(document)}>Delete</button>
        </div>
      </div>
    );
  });
}

function Conversation({ messages, onRetry, asking }) {
  const history = useRef(null);
  const followLatest = useRef(true);
  const previousCount = useRef(messages.length);
  useEffect(() => {
    const container = history.current;
    if (container && (followLatest.current || messages.length > previousCount.current)) {
      // Only scroll the history pane; never move the composer or the document.
      container.scrollTop = container.scrollHeight;
      followLatest.current = true;
    }
    previousCount.current = messages.length;
  }, [messages]);
  return (
    <div id="messages" ref={history} tabIndex={0} role="log" aria-label="Conversation history" aria-live="polite" aria-relevant="additions text" onScroll={() => {
      const container = history.current;
      followLatest.current = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    }}>
      {!messages.length && <div className="empty-conversation"><span className="empty-icon" aria-hidden="true">◈</span><span className="badge">YOUR DOCUMENTS, EXPLAINED</span><h2>What would you like<br />to discover?</h2><p>Ask about a person, explore a finding, or compare details.<br />Every answer starts with your documents.</p><div className="welcome"><strong>Start here</strong><span>Upload a PDF → choose Index → ask a question.</span></div></div>}
      {messages.map(message => (
        <article className="message" key={message.id}>
          <div className="user-message"><h3>YOU</h3><div>{message.question}</div></div><div className="assistant-message"><h3><span aria-hidden="true">◈</span> OMNIRAG</h3>
          <div className={message.error ? 'error' : ''}>{message.answer}</div>
          {message.error && message.reference && <div className="error-reference">Error reference: {message.reference}</div>}
          {message.error && message.retryable && <button className="retry-answer" disabled={asking} onClick={() => onRetry(message)}>Retry question ↻</button>}
          <Evidence citations={message.citations} />
          </div>
        </article>
      ))}
    </div>
  );
}

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [busy, setBusy] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState({ text: '', error: false });
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState('chat');
  const [asking, setAsking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const fileInput = useRef(null);
  const refreshVersion = useRef(0);
  const operations = useRef(new Set());
  const requestInFlight = useRef(false);
  const scopedDocuments = documents.filter(document => !selected.size || selected.has(document.document_id));
  const readyCount = scopedDocuments.filter(document => document.indexStatus === 'indexed' && !busy.has(document.document_id)).length;
  const canAsk = readyCount > 0 && !loading;

  const report = (text, error = false) => setStatus({ text, error });
  const refresh = useCallback(async () => {
    const version = ++refreshVersion.current;
    setLoading(true);
    try {
      const records = await api('/documents');
      const states = await Promise.all(records.map(record => api(`/documents/${record.document_id}/index`)));
      if (version !== refreshVersion.current) return;
      setDocuments(records.map((record, index) => ({ ...record, indexStatus: states[index].status })));
      setSelected(current => new Set([...current].filter(id => records.some(record => record.document_id === id))));
    } catch (error) {
      if (version === refreshVersion.current) setStatus({ text: error.message, error: true });
    } finally {
      if (version === refreshVersion.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return () => { refreshVersion.current++; };
  }, [refresh]);

  function selectDocument(id) {
    setSelected(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function documentAction(id, action) {
    if (operations.current.has(id)) return;
    operations.current.add(id);
    setBusy(new Set(operations.current));
    try { await action(); }
    catch (error) { report(error.message, true); }
    finally {
      operations.current.delete(id);
      setBusy(new Set(operations.current));
      await refresh();
    }
  }

  function indexDocument(id) {
    return documentAction(id, async () => {
      report('Indexing document. This may take a few minutes.');
      await api(`/documents/${id}/index`, { method: 'POST' });
      report('Document is ready for questions.');
    });
  }

  function deleteDocument(document) {
    if (!window.confirm(`Delete ${document.filename} and its search index?`)) return;
    return documentAction(document.document_id, async () => {
      await api(`/documents/${document.document_id}`, { method: 'DELETE' });
      report('Document deleted.');
    });
  }

  async function uploadDocument(event) {
    event.preventDefault();
    const file = fileInput.current?.files[0];
    if (!file || uploading) return;
    if (file.size > 50 * 1024 * 1024) return report('PDF exceeds the 50 MB upload limit.', true);
    setUploading(true);
    report('Extracting document…');
    const data = new FormData(); data.append('file', file);
    try {
      await api('/documents/upload', { method: 'POST', body: data });
      fileInput.current.value = '';
      await refresh();
      report('Uploaded. Choose Index to enable questions.');
    } catch (error) { report(error.message, true); }
    finally { setUploading(false); }
  }

  async function askQuestion(event) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || requestInFlight.current || !canAsk) return;
    setQuestion('');
    await submitQuestion(prompt, mode, [...selected]);
  }

  async function submitQuestion(prompt, requestedMode, documentIds, retryId) {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setAsking(true);
    const id = retryId || crypto.randomUUID();
    const update = result => setMessages(current => current.map(message => message.id === id ? { ...message, ...result } : message));
    const pending = { id, question: prompt, mode: requestedMode, documentIds, answer: 'Looking through your sources…', citations: [], error: false, retryable: false, reference: null };
    if (retryId) update(pending);
    else setMessages(current => [...current, pending]);
    try {
      const data = await api('/' + requestedMode, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: prompt, document_ids: documentIds }),
      });
      update({
        answer: requestedMode === 'chat' ? data.answer : (data.results.length ? 'Matching evidence' : 'No matching evidence. Index a document or try another question.'),
        citations: requestedMode === 'chat' ? data.citations : data.results,
      });
    } catch (error) {
      update({ answer: error.message, error: true, retryable: error.retryable, reference: error.reference });
      if (!retryId) setQuestion(current => current || prompt);
    } finally { requestInFlight.current = false; setAsking(false); }
  }

  return (
    <>
      <aside className={libraryOpen ? 'library-open' : ''}>
        <div className="sidebar-top">
        <a className="brand" href="/">◈ OmniRAG</a>
        <button className="quiet library-toggle" aria-expanded={libraryOpen} aria-controls="library-content" onClick={() => setLibraryOpen(current => !current)}>{libraryOpen ? 'Close library' : 'Library'}</button>
        </div>
        <div id="library-content">
        <p className="eyebrow">DOCUMENT LIBRARY</p>
        <h1>Your knowledge.<br />One conversation.</h1>
        <p className="muted">Add your PDFs and turn information into answers.</p>
        <form id="upload" onSubmit={uploadDocument}>
          <label className="drop">Add a PDF
            <input ref={fileInput} type="file" accept=".pdf,application/pdf" required disabled={uploading} />
            <span>Text, tables & embedded images · up to 50 MB</span>
          </label>
          <button disabled={uploading}>{uploading ? 'Uploading…' : 'Upload document'}</button>
        </form>
        <div className="library-heading"><h2>Library</h2><button className="quiet" onClick={refresh} disabled={loading} aria-label="Refresh library">↻</button></div>
        <p className="muted small">Select PDFs to focus your questions, or search all ready documents.</p>
        <div id="documents" aria-busy={loading}><DocumentLibrary documents={documents} loading={loading} selected={selected} busy={busy} onSelect={selectDocument} onIndex={indexDocument} onDelete={deleteDocument} /></div>
        <p id="library-status" role="status" className={status.error ? 'error' : ''}>{status.text}</p>
        </div>
        <div className="sidebar-footer"><span className="status-dot" />Local document workspace</div>
      </aside>
      <main>
        <header><div><span className="eyebrow">DOCUMENT WORKSPACE</span><h2>Ask your library <span className="badge">EVIDENCE FIRST</span></h2></div><a href="/docs" target="_blank" rel="noopener noreferrer">API docs ↗</a></header>
        <div className="conversation-toolbar"><span><span className={`status-dot ${readyCount ? '' : 'pending'}`} />{loading ? 'Checking library…' : `${readyCount} ready ${readyCount === 1 ? 'document' : 'documents'}${selected.size ? ' selected' : ''}`}</span><button className="quiet" disabled={!messages.length || asking} onClick={() => setMessages([])}>New conversation</button></div>
        <Conversation messages={messages} asking={asking} onRetry={message => submitQuestion(message.question, message.mode, message.documentIds, message.id)} />
        <div className="composer-area">
        <p id="readiness" className={`readiness ${!canAsk && !loading ? 'needs-index' : ''}`} role="status">{loading ? 'Checking your documents…' : !documents.length ? 'Upload a PDF in the library, then choose Index to get started.' : !readyCount ? 'Choose Index next to a selected PDF before asking questions.' : `Searching ${selected.size ? 'selected' : 'all ready'} documents. Source citations appear with each answer.`}</p>
        <form id="question" onSubmit={askQuestion} aria-busy={asking}>
          <label htmlFor="prompt">Your question</label>
          <textarea id="prompt" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask a question about your documents…" aria-describedby="readiness" maxLength={4000} required rows={2} onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              event.currentTarget.form.requestSubmit();
            }
          }} />
          <div className="composer-footer">
            <select value={mode} onChange={event => setMode(event.target.value)} aria-label="Response mode"><option value="chat">Answer with citations</option><option value="search">Search evidence</option></select>
            <button disabled={asking || !question.trim() || !canAsk}>{asking ? 'Searching…' : 'Ask OmniRAG ↗'}</button>
          </div>
        </form>
        <p className="footnote">Enter to send · Shift + Enter for a new line · Check cited pages for context.</p>
        </div>
      </main>
    </>
  );
}
