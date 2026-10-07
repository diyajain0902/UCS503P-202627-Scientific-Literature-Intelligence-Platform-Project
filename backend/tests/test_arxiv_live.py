"""Live arXiv API checks (marker ``network``). Run manually; not part of CI."""

import pytest

from app.core.config import Settings
from app.ingestion.arxiv import ArxivClient, ArxivId
from app.ingestion.pdf import extract_pdf

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def client() -> ArxivClient:
    settings = Settings()
    return ArxivClient(
        api_url=str(settings.arxiv_api_url),
        pdf_base_url=str(settings.arxiv_pdf_base_url),
        allowed_hosts=settings.arxiv_allowed_hosts,
        timeout_seconds=60,
        min_interval_seconds=3,
    )


def test_fetch_metadata_and_pdf_for_known_paper(client: ArxivClient) -> None:
    meta = client.fetch_metadata(ArxivId.parse("1706.03762v1"))
    assert meta.arxiv_id == "1706.03762"
    assert meta.version == 1
    assert "Attention Is All You Need" in meta.title
    pdf = client.download_pdf(meta.arxiv_id, meta.version, 50 * 1024 * 1024)
    document = extract_pdf(pdf, 200)
    assert document.page_count > 5
    assert "attention" in document.text.lower()
