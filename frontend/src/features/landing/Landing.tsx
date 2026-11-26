import { useEffect, useRef } from 'react'
import { Wordmark } from '../../ui/controls'
import { HeroStage } from './HeroStage'

const REPO = 'https://github.com/diyajain0902/UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project'

const STEPS = [
  ['01', 'lav', 'Import', 'Search arXiv, import by ID, or upload a PDF. Re-imports are idempotent.'],
  ['02', 'mint', 'Index', 'Page-aware extraction, 256-token chunks, 384-dim MiniLM embeddings.'],
  ['03', 'peach', 'Retrieve', 'Hybrid dense + BM25 search, reranked by a cross-encoder.'],
  ['04', 'sky', 'Answer & verify', 'Each claim cites a passage; citations are checked server-side.'],
] as const

/** Marketing page at "/". The evaluation figures are from docs/evaluation/rag-evaluation-report.md (2026-10-09). */
export function Landing({ onOpenApp }: { onOpenApp: (addPapers: boolean) => void }) {
  const how = useRef<HTMLElement>(null)
  const evaluation = useRef<HTMLElement>(null)
  useEffect(() => {
    document.title = 'slip · Ask your papers'
  }, [])
  const scrollTo = (target: HTMLElement | null) => target?.scrollIntoView?.({ behavior: 'smooth' })

  return (
    <div className="landing">
      <header className="landing-nav">
        <Wordmark large />
        <nav className="landing-links" aria-label="Page">
          <button type="button" onClick={() => scrollTo(how.current)}>
            How it works
          </button>
          <button type="button" onClick={() => scrollTo(evaluation.current)}>
            Evaluation
          </button>
          <a href={`${REPO}/tree/main/docs`} target="_blank" rel="noreferrer noopener">
            Docs
          </a>
          <a href={REPO} target="_blank" rel="noreferrer noopener">
            GitHub
          </a>
        </nav>
        <button type="button" className="btn btn-dark btn-pill landing-cta-sm" onClick={() => onOpenApp(false)}>
          Open dashboard
        </button>
      </header>

      <section className="landing-hero">
        <p className="landing-badge">
          <span className="dot dot-ok" aria-hidden="true" />
          Runs locally · No data leaves your machine
        </p>
        <h1 className="landing-title">
          Ask your papers.
          <br />
          Get answers you can <span className="serif">check.</span>
        </h1>
        <p className="landing-sub">
          Import from arXiv or drop in PDFs. slip indexes every page on your machine and answers with citations to the
          exact passage — or tells you when the papers don't say.
        </p>
        <div className="landing-ctas">
          <button type="button" className="btn btn-dark btn-pill landing-cta" onClick={() => onOpenApp(false)}>
            Open dashboard
          </button>
          <button type="button" className="btn btn-light btn-pill landing-cta" onClick={() => onOpenApp(true)}>
            Import from arXiv
          </button>
        </div>
      </section>

      <HeroStage />

      <section ref={how} className="landing-section" aria-labelledby="how-heading">
        <div className="landing-section-head">
          <h2 id="how-heading">From PDF to cited answer in four steps.</h2>
          <p>Every stage runs on your hardware — PostgreSQL with pgvector for storage, a local Ollama model for answers.</p>
        </div>
        <ol className="steps">
          {STEPS.map(([n, tone, title, body]) => (
            <li key={n} className="step">
              <span className={`step-num tone-${tone}`}>{n}</span>
              <div>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section ref={evaluation} className="landing-section" aria-labelledby="eval-heading">
        <h2 id="eval-heading" className="sr-only">
          Evaluation
        </h2>
        <div className="eval-band">
          <div>
            <div className="eval-num">0.875</div>
            <div className="eval-label">Recall@5 on 40 answerable eval questions</div>
          </div>
          <div>
            <div className="eval-num">1.00</div>
            <div className="eval-label">Citation validity (52 of 52 citations)</div>
          </div>
          <div>
            <div className="eval-num">
              9<span className="eval-dim">/10</span>
            </div>
            <div className="eval-label">Unanswerable questions correctly declined</div>
          </div>
          <div className="eval-note">
            <p>
              Measured, not promised. Labels were written by the assistant and are not yet human-reviewed; warm Q&amp;A
              p95 latency is 4.4 s, above the 3 s target.
            </p>
            <a href={`${REPO}/blob/main/docs/evaluation/rag-evaluation-report.md`} target="_blank" rel="noreferrer noopener">
              Read the report →
            </a>
          </div>
        </div>
        <footer className="landing-footer">
          <span>Scientific Literature Intelligence Platform · Thapar Institute of Engineering and Technology</span>
          <span>UCS503P · 2026–27</span>
        </footer>
      </section>
    </div>
  )
}
