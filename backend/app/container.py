"""Composition root: builds long-lived services from settings. Tests build their own."""

from dataclasses import dataclass, field

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import make_engine, make_session_factory
from app.generation.ollama import OllamaProvider
from app.ingestion.arxiv import ArxivClient
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.storage import FileStore
from app.retrieval.embedding import (
    ManagedEmbedder,
    SentenceTransformerEmbedder,
    required_input_tokens,
)
from app.services.corpus import CorpusService
from app.services.ingestion import IngestionService
from app.services.jobs import JobRunner
from app.services.qa import QALimits, QAService
from app.services.search import SearchService


@dataclass
class Container:
    settings: Settings
    session_factory: sessionmaker[Session]
    embedder: ManagedEmbedder
    ingestion: IngestionService
    search: SearchService
    corpus: CorpusService
    runner: JobRunner
    qa: QAService
    engine: Engine | None = None
    arxiv: ArxivClient | None = None
    ollama: OllamaProvider | None = None
    closed: bool = field(default=False)

    def close(self) -> None:
        if self.closed:
            return
        self.runner.shutdown(wait=False)
        if self.arxiv is not None:
            self.arxiv.close()
        if self.ollama is not None:
            self.ollama.close()
        if self.engine is not None:
            self.engine.dispose()
        self.closed = True


def build_container(settings: Settings) -> Container:
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    chunking = ChunkingConfig(settings.chunk_window_tokens, settings.chunk_overlap_tokens)
    embedder = SentenceTransformerEmbedder(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        min_input_tokens=required_input_tokens(settings.chunk_window_tokens),
    )
    arxiv = ArxivClient(
        api_url=str(settings.arxiv_api_url),
        pdf_base_url=str(settings.arxiv_pdf_base_url),
        allowed_hosts=settings.arxiv_allowed_hosts,
        timeout_seconds=settings.arxiv_timeout_seconds,
        min_interval_seconds=settings.arxiv_min_interval_seconds,
    )
    ingestion = IngestionService(
        session_factory=session_factory,
        arxiv=arxiv,
        embedder=embedder,
        tokenizer_provider=embedder.tokenizer,
        store=FileStore(settings.storage_dir),
        chunking=chunking,
        max_pdf_bytes=settings.max_pdf_bytes,
        max_pdf_pages=settings.max_pdf_pages,
    )
    search = SearchService(session_factory, embedder, settings.search_max_top_k)
    ollama = OllamaProvider(
        base_url=str(settings.ollama_base_url),
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        num_ctx=settings.ollama_num_ctx,
        max_tokens=settings.ollama_max_tokens,
        temperature=settings.ollama_temperature,
        seed=settings.ollama_seed,
        keep_alive=settings.ollama_keep_alive,
    )
    return Container(
        settings=settings,
        session_factory=session_factory,
        embedder=embedder,
        ingestion=ingestion,
        search=search,
        corpus=CorpusService(session_factory),
        runner=JobRunner(settings.ingestion_workers, ingestion.run_job),
        qa=QAService(session_factory, search, ollama, qa_limits(settings)),
        engine=engine,
        arxiv=arxiv,
        ollama=ollama,
    )


def qa_limits(settings: Settings) -> QALimits:
    return QALimits(
        default_top_k=settings.qa_default_top_k,
        max_top_k=settings.qa_max_top_k,
        max_question_chars=settings.qa_max_question_chars,
        min_score=settings.qa_min_score,
        max_context_chars=settings.qa_max_context_chars,
    )
