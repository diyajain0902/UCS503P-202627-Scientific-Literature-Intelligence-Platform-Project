"""Environment-based application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings read from ``SLIP_``-prefixed environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="SLIP_", env_file=".env", extra="ignore")

    environment: str = Field(default="development", pattern="^(development|test|production)$")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

    database_url: str = "postgresql+psycopg://slip:slip@127.0.0.1:5432/slip"
    storage_dir: Path = Path("../data/storage")

    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen2.5:3b", min_length=1)
    ollama_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    # Bounded generation (AC-09.2). num_ctx must hold the prompt, the evidence, and the answer.
    ollama_num_ctx: int = Field(default=4096, ge=1024, le=32768)
    ollama_max_tokens: int = Field(default=512, ge=32, le=4096)
    ollama_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    ollama_seed: int = 0
    ollama_keep_alive: str = Field(default="30m", pattern=r"^-?\d+[smh]?$")
    ollama_warm_up: bool = True

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, gt=0)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    embedding_device: str = "cpu"

    # ADR-0003: window counts the model's special tokens; overlap is in content tokens.
    chunk_window_tokens: int = Field(default=256, ge=16, le=512)
    chunk_overlap_tokens: int = Field(default=38, ge=0)

    arxiv_api_url: AnyHttpUrl = AnyHttpUrl("https://export.arxiv.org/api/query")
    arxiv_pdf_base_url: AnyHttpUrl = AnyHttpUrl("https://arxiv.org/pdf/")
    arxiv_allowed_hosts: list[str] = Field(
        default_factory=lambda: ["export.arxiv.org", "arxiv.org"]
    )
    arxiv_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    arxiv_min_interval_seconds: float = Field(default=3.0, ge=0)

    max_pdf_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    ingestion_workers: int = Field(default=1, ge=1, le=4)

    search_max_top_k: int = Field(default=50, ge=1, le=200)
    search_default_top_k: int = Field(default=10, ge=1)
    search_max_query_chars: int = Field(default=1000, ge=10)

    # Hybrid Search & Reranking (FR-24, FR-25)
    search_mode: str = Field(default="hybrid_rerank", pattern="^(dense|bm25|hybrid|hybrid_rerank)$")
    hybrid_rrf_k: int = Field(default=60, ge=1)
    hybrid_dense_weight: float = Field(default=1.0, ge=0.0)
    hybrid_sparse_weight: float = Field(default=1.0, ge=0.0)
    hybrid_candidate_multiplier: int = Field(default=4, ge=1, le=10)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = True

    qa_default_top_k: int = Field(default=6, ge=1)
    qa_max_top_k: int = Field(default=10, ge=1, le=20)
    qa_max_question_chars: int = Field(default=1000, ge=10)
    # Passages scoring below this cosine similarity are not shown to the model. Provisional value
    # for MiniLM; to be calibrated against the M3 evaluation set.
    qa_min_score: float = Field(default=0.30, ge=-1.0, le=1.0)
    qa_max_context_chars: int = Field(default=12000, ge=1000)

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        content_tokens = self.chunk_window_tokens - 2
        if self.chunk_overlap_tokens >= content_tokens:
            raise ValueError("chunk_overlap_tokens must be smaller than the chunk content window")
        if self.search_default_top_k > self.search_max_top_k:
            raise ValueError("search_default_top_k must not exceed search_max_top_k")
        if self.qa_default_top_k > self.qa_max_top_k:
            raise ValueError("qa_default_top_k must not exceed qa_max_top_k")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
