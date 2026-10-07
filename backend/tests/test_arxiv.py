import time

import httpx
import pytest

from app.core.errors import DocumentRejectedError, InvalidInputError, NotFoundError, UpstreamError
from app.ingestion.arxiv import ArxivClient, ArxivId, parse_atom_entry

# Synthetic Atom documents shaped like arXiv API responses (not real paper metadata).
ENTRY = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001v3</id>
    <updated>2021-02-01T00:00:00Z</updated>
    <published>2021-01-01T00:00:00Z</published>
    <title>A Synthetic   Title
      Spanning Lines</title>
    <summary>  Synthetic abstract.  </summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <arxiv:primary_category term="cs.IR"/>
    <category term="cs.CL"/>
    <category term="cs.IR"/>
  </entry>
</feed>"""

ERROR_ENTRY = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_9999.99999</id>
    <title>Error</title>
    <summary>incorrect id format for 9999.99999</summary>
  </entry>
</feed>"""

EMPTY_FEED = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'


@pytest.mark.parametrize(
    ("raw", "base", "version"),
    [
        ("1706.03762", "1706.03762", None),
        ("1706.03762v5", "1706.03762", 5),
        ("arXiv:2101.00001", "2101.00001", None),
        ("  2101.00001v2 ", "2101.00001", 2),
        ("hep-th/9901001", "hep-th/9901001", None),
        ("math.GT/0309136v1", "math.GT/0309136", 1),
    ],
)
def test_parse_valid_ids(raw: str, base: str, version: int | None) -> None:
    parsed = ArxivId.parse(raw)
    assert (parsed.base, parsed.version) == (base, version)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abc",
        "1706.037",
        "1706.03762v0",
        "../../etc/passwd",
        "1706.03762?x=1",
        "https://evil/1706.03762",
    ],
)
def test_parse_invalid_ids(raw: str) -> None:
    with pytest.raises(InvalidInputError):
        ArxivId.parse(raw)


def test_parse_atom_entry_normalizes_metadata() -> None:
    meta = parse_atom_entry(ENTRY, ArxivId("2101.00001"))
    assert meta.arxiv_id == "2101.00001"
    assert meta.version == 3
    assert meta.title == "A Synthetic Title Spanning Lines"
    assert meta.abstract == "Synthetic abstract."
    assert meta.authors == ["Alice Example", "Bob Example"]
    assert meta.categories == ["cs.IR", "cs.CL"]  # primary category first
    assert meta.published_at is not None and meta.published_at.year == 2021


def test_parse_atom_entry_rejects_mismatched_paper() -> None:
    with pytest.raises(UpstreamError, match="different paper"):
        parse_atom_entry(ENTRY, ArxivId("2101.99999"))


@pytest.mark.parametrize("xml", [ERROR_ENTRY, EMPTY_FEED])
def test_parse_atom_entry_not_found(xml: bytes) -> None:
    with pytest.raises(NotFoundError):
        parse_atom_entry(xml, ArxivId("9999.99999"))


def test_parse_atom_entry_malformed_xml() -> None:
    with pytest.raises(UpstreamError, match="malformed"):
        parse_atom_entry(b"<feed><entry>", ArxivId("2101.00001"))


def test_parse_atom_entry_rejects_entity_expansion() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><feed>&a;</feed>'
    with pytest.raises(Exception):  # defusedxml refuses entity declarations  # noqa: B017
        parse_atom_entry(bomb, ArxivId("2101.00001"))


def _client(handler: httpx.MockTransport, interval: float = 0.0) -> ArxivClient:
    return ArxivClient(
        api_url="https://export.arxiv.org/api/query",
        pdf_base_url="https://arxiv.org/pdf/",
        allowed_hosts=["export.arxiv.org", "arxiv.org"],
        timeout_seconds=5,
        min_interval_seconds=interval,
        transport=handler,
    )


def test_client_fetches_metadata_with_id_list() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=ENTRY)

    meta = _client(httpx.MockTransport(handler)).fetch_metadata(ArxivId("2101.00001"))
    assert meta.version == 3
    assert seen[0].url.params["id_list"] == "2101.00001"


def test_client_refuses_non_https_or_unlisted_configuration() -> None:
    with pytest.raises(UpstreamError):
        ArxivClient(
            "http://export.arxiv.org/api/query",
            "https://arxiv.org/pdf/",
            ["export.arxiv.org", "arxiv.org"],
            5,
            0,
        )
    with pytest.raises(UpstreamError):
        ArxivClient(
            "https://169.254.169.254/api",
            "https://arxiv.org/pdf/",
            ["export.arxiv.org", "arxiv.org"],
            5,
            0,
        )


def test_client_follows_allowed_redirect_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pdf/2101.00001v1":
            return httpx.Response(
                301, headers={"location": "https://arxiv.org/pdf/2101.00001v1.pdf"}
            )
        if request.url.path == "/pdf/2101.00001v1.pdf":
            return httpx.Response(200, content=b"%PDF-1.7 ok")
        return httpx.Response(500)

    assert (
        _client(httpx.MockTransport(handler)).download_pdf("2101.00001", 1, 1000) == b"%PDF-1.7 ok"
    )

    def evil(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1:5432/"})

    with pytest.raises(UpstreamError, match="non-allow-listed"):
        _client(httpx.MockTransport(evil)).download_pdf("2101.00001", 1, 1000)


def test_client_enforces_size_limit_while_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-" + b"x" * 5000)

    with pytest.raises(DocumentRejectedError, match="larger than"):
        _client(httpx.MockTransport(handler)).download_pdf("2101.00001", 1, 1000)


def test_client_maps_errors() -> None:
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(NotFoundError):
        _client(httpx.MockTransport(not_found)).download_pdf("2101.00001", 1, 1000)
    with pytest.raises(UpstreamError, match="HTTP 503"):
        _client(httpx.MockTransport(server_error)).download_pdf("2101.00001", 1, 1000)
    with pytest.raises(UpstreamError, match="timed out"):
        _client(httpx.MockTransport(timeout)).download_pdf("2101.00001", 1, 1000)


def test_client_rate_limits_consecutive_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ENTRY)

    client = _client(httpx.MockTransport(handler), interval=0.2)
    start = time.monotonic()
    client.fetch_metadata(ArxivId("2101.00001"))
    client.fetch_metadata(ArxivId("2101.00001"))
    assert time.monotonic() - start >= 0.19
