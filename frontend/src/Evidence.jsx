import React from 'react';

export default function Evidence({ citations }) {
  if (!citations.length) return null;
  return (
    <details className="evidence-panel">
      <summary>
        <svg className="evidence-chevron" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="m5 7 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <span>View evidence</span>
        <span className="evidence-count">{citations.length} {citations.length === 1 ? 'source' : 'sources'}</span>
      </summary>
      <div className="evidence-body">
        <p className="evidence-description">Retrieved excerpts used to support this answer. Open the original page for full context.</p>
        {citations.map((hit, index) => {
          const chunk = hit.chunk;
          return (
            <section className="citation" key={chunk.id}>
              <a href={`/api/v1/documents/${chunk.document_id}/file#page=${chunk.page_number || 1}`} target="_blank" rel="noopener noreferrer">
                [{hit.source_id || index + 1}] {chunk.source} · page {chunk.page_number || 'unknown'} · {chunk.modality} ↗
              </a>
              <p>{hit.excerpt ?? chunk.content}</p>
              {chunk.metadata?.representation === 'generated_caption' && <span className="caption-note">Generated image description — check the original image.</span>}
              {chunk.file_path && <a className="media-link" href={`/api/v1/documents/${chunk.document_id}/media/${chunk.evidence_id}`} target="_blank" rel="noopener noreferrer">View source image ↗</a>}
            </section>
          );
        })}
      </div>
    </details>
  );
}
