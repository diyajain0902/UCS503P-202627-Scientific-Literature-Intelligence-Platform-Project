/**
 * Decorative 12 s loop for the landing hero: a question types in, three papers are cited, the answer's claims appear
 * with their chips. Illustrative only (hidden from assistive tech); reduced motion shows the final frame.
 */
const CITED = [
  { n: 1, tone: 'lav', id: '1706.03762', tag: 'P1 · p.2', title: 'Attention Is All You Need', meta: 'Vaswani et al. · 2017 · 15 pp' },
  { n: 2, tone: 'mint', id: '1409.3215', tag: 'P2 · p.1', title: 'Sequence to Sequence Learning with Neural Networks', meta: 'Sutskever et al. · 2014 · 9 pp' },
  { n: 3, tone: 'peach', id: '1409.0473', tag: 'P3 · p.3', title: 'Neural Machine Translation by Jointly Learning to Align and Translate', meta: '' },
] as const

const IDLE = [
  { n: 1, id: '1810.04805', title: 'BERT: Pre-training of Deep Bidirectional Transformers' },
  { n: 2, id: '2005.14165', title: 'Language Models are Few-Shot Learners' },
  { n: 3, id: '1910.10683', title: 'Exploring the Limits of Transfer Learning (T5)' },
] as const

const CLAIMS = [
  { n: 1, tone: 'lav', text: 'The Transformer drops recurrence entirely and relies on attention alone to relate input and output positions.' },
  { n: 2, tone: 'mint', text: 'Recurrent seq2seq models encode the source with stacked LSTMs into a fixed-length vector before decoding.' },
  { n: 3, tone: 'peach', text: 'Attention was first added to such models to let the decoder align with relevant source words.' },
] as const

export function HeroStage() {
  return (
    <div className="hero-clip" aria-hidden="true">
      <div className="hero-stage">
        <div className="hero-grid" />
        <span className="hero-blob hero-blob-1" />
        <span className="hero-blob hero-blob-2" />
        <span className="hero-blob hero-blob-3" />
        <svg className="hero-lines" width="1120" height="600" viewBox="0 0 1120 600" fill="none">
          <path className="hero-line hero-line-1" d="M244 92 C 290 92, 280 220, 312 220" />
          <path className="hero-line hero-line-2" d="M260 476 C 300 476, 280 300, 312 300" />
          <path className="hero-line hero-line-3" d="M900 282 C 860 282, 850 260, 808 260" />
        </svg>
        {CITED.map((c) => (
          <span key={c.n} className={`hero-traveler hero-traveler-${c.n} tone-${c.tone}`} />
        ))}
        {CITED.map((c) => (
          <div key={c.n} className={`hero-paper hero-cited hero-cited-${c.n}`}>
            <div className="hero-paper-top">
              <span>arXiv:{c.id}</span>
              <span className={`hero-tag tone-${c.tone}`}>{c.tag}</span>
            </div>
            <div className="hero-paper-title">{c.title}</div>
            {c.meta && <div className="hero-paper-meta">{c.meta}</div>}
          </div>
        ))}
        {IDLE.map((p) => (
          <div key={p.n} className={`hero-idle hero-idle-${p.n}`}>
            <div className="hero-paper hero-paper-dim">
              <div className="hero-paper-top">
                <span>arXiv:{p.id}</span>
              </div>
              <div className="hero-paper-title">{p.title}</div>
            </div>
          </div>
        ))}
        <div className="hero-card">
          <div className="hero-search">
            <span className="search-glyph hero-glyph" />
            <span className="hero-query">
              <span className="hero-typed">How do Transformers differ from recurrent seq2seq models?</span>
              <span className="hero-caret" />
            </span>
            <span className="hero-enter">⏎</span>
          </div>
          <div className="hero-body">
            <div className="hero-searching">
              <span className="dot tone-lav" />
              Searching your papers · hybrid + rerank
            </div>
            <div className="hero-claims">
              {CLAIMS.map((c) => (
                <div key={c.n} className={`hero-claim hero-claim-${c.n}`}>
                  {c.text} <span className={`hero-chip hero-chip-${c.n} tone-${c.tone}`}>P{c.n}</span>
                </div>
              ))}
              <div className="hero-claim hero-claim-4 hero-meta">
                <span className="text-ok">✓ 3/3 citations verified</span>
                <span>qwen2.5:3b · local</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
