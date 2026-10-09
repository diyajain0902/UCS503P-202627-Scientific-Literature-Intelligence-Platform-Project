"""arXiv API client (FR-01, FR-02).

Outbound requests are restricted to an allow-list of HTTPS hosts (SSRF guard, AC-01.2), rate limited
per the arXiv API terms of use, and responses are size-bounded. Atom XML is parsed with defusedxml.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit
from xml.etree.ElementTree import Element

import httpx
from defusedxml import ElementTree as SafeET

from app.core.errors import DocumentRejectedError, InvalidInputError, NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

_NEW_STYLE = r"\d{4}\.\d{4,5}"
_OLD_STYLE = r"[a-z]+(?:-[a-z]+)*(?:\.[A-Z]{2})?/\d{7}"
_ID_RE = re.compile(rf"^(?P<base>{_NEW_STYLE}|{_OLD_STYLE})(?:v(?P<version>[1-9]\d{{0,3}}))?$")
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_MAX_METADATA_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 3


@dataclass(frozen=True)
class ArxivId:
    base: str
    version: int | None = None

    @classmethod
    def parse(cls, raw: str) -> "ArxivId":
        candidate = raw.strip()
        if candidate.lower().startswith("arxiv:"):
            candidate = candidate[len("arxiv:") :]
        match = _ID_RE.fullmatch(candidate)
        if match is None:
            raise InvalidInputError(
                f"'{raw[:64]}' is not a valid arXiv identifier (e.g. 1706.03762)"
            )
        version = match.group("version")
        return cls(base=match.group("base"), version=int(version) if version else None)

    def __str__(self) -> str:
        return f"{self.base}v{self.version}" if self.version else self.base


@dataclass(frozen=True)
class ArxivMetadata:
    arxiv_id: str
    version: int
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_at: datetime | None
    updated_at: datetime | None


class ArxivSource(Protocol):
    def fetch_metadata(self, arxiv_id: ArxivId) -> ArxivMetadata: ...

    def download_pdf(self, arxiv_id: str, version: int, max_bytes: int) -> bytes: ...

    def search(self, text: str, max_results: int) -> list[ArxivMetadata]: ...


def _text(element: Element | None) -> str:
    return " ".join((element.text or "").split()) if element is not None else ""


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _parse_root(xml: bytes) -> Element:
    try:
        root: Element = SafeET.fromstring(xml)
    except SafeET.ParseError as exc:
        raise UpstreamError("arXiv returned malformed XML") from exc
    return root


def _entry_metadata(entry: Element) -> ArxivMetadata | None:
    """Metadata for one Atom entry, or None for arXiv's error pseudo-entries."""
    entry_id = _text(entry.find(f"{_ATOM}id"))
    if "/api/errors" in entry_id:
        return None
    match = re.search(r"/abs/(?P<id>.+?)v(?P<version>\d+)$", entry_id)
    if match is None:
        raise UpstreamError("arXiv response is missing a versioned identifier")
    title = _text(entry.find(f"{_ATOM}title"))
    if not title:
        raise UpstreamError("arXiv response is missing the paper title")
    categories = [
        term for category in entry.findall(f"{_ATOM}category") if (term := category.get("term"))
    ]
    primary = entry.find(f"{_ARXIV}primary_category")
    primary_term = primary.get("term") if primary is not None else None
    if primary_term and primary_term in categories:
        categories.remove(primary_term)
        categories.insert(0, primary_term)
    return ArxivMetadata(
        arxiv_id=match.group("id"),
        version=int(match.group("version")),
        title=title,
        authors=[_text(a.find(f"{_ATOM}name")) for a in entry.findall(f"{_ATOM}author")],
        abstract=_text(entry.find(f"{_ATOM}summary")),
        categories=categories,
        published_at=_parse_datetime(_text(entry.find(f"{_ATOM}published"))),
        updated_at=_parse_datetime(_text(entry.find(f"{_ATOM}updated"))),
    )


def parse_atom_entry(xml: bytes, requested: ArxivId) -> ArxivMetadata:
    """Parse an arXiv API Atom response for a single ``id_list`` lookup."""
    entries = _parse_root(xml).findall(f"{_ATOM}entry")
    if not entries:
        raise NotFoundError(f"arXiv has no paper with identifier {requested}")
    meta = _entry_metadata(entries[0])
    if meta is None:
        summary = _text(entries[0].find(f"{_ATOM}summary"))
        raise NotFoundError(f"arXiv rejected identifier {requested}: {summary}")
    if meta.arxiv_id != requested.base:
        raise UpstreamError("arXiv returned a different paper than requested")
    return meta


def parse_atom_feed(xml: bytes) -> list[ArxivMetadata]:
    """Parse an arXiv search response (FR-01)."""
    results = []
    for entry in _parse_root(xml).findall(f"{_ATOM}entry"):
        meta = _entry_metadata(entry)
        if meta is not None:
            results.append(meta)
    return results


_QUERY_TERM = re.compile(r"[\w.-]+", re.UNICODE)
# arXiv's index drops these words, so an ``all:<stop word>`` clause matches nothing and, because
# every clause is AND-ed, a title such as "Attention Is All You Need" found no papers (MVP
# acceptance check). They are removed unless the query consists of nothing else.
_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "all",
        "you",
        "your",
        "we",
        "our",
        "can",
        "do",
        "does",
        "not",
        "no",
    ]
)
MAX_SEARCH_RESULTS = 25


def build_search_query(text: str) -> str:
    """Turn free text into an arXiv ``search_query``: every content word must match (all fields).

    Only word characters, dots, and hyphens are kept, so user input cannot inject arXiv query
    operators or parameters.
    """
    terms = _QUERY_TERM.findall(text)
    if not terms:
        raise InvalidInputError("search text must contain at least one word")
    terms = ([t for t in terms if t.lower() not in _STOP_WORDS] or terms)[:12]
    return " AND ".join(f"all:{term}" for term in terms)


class ArxivClient:
    """HTTP client for the arXiv export API and PDF host."""

    def __init__(
        self,
        api_url: str,
        pdf_base_url: str,
        allowed_hosts: list[str],
        timeout_seconds: float,
        min_interval_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_url = api_url
        self._pdf_base_url = pdf_base_url if pdf_base_url.endswith("/") else pdf_base_url + "/"
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._min_interval = min_interval_seconds
        self._last_request = 0.0
        self._lock = threading.Lock()
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "slip-research-platform/0.1 (university project)"},
        )
        self._check_url(api_url)
        self._check_url(self._pdf_base_url)

    def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or (parts.hostname or "").lower() not in self._allowed_hosts:
            raise UpstreamError(f"Refusing to contact non-allow-listed URL host '{parts.hostname}'")

    def _throttle(self) -> None:
        with self._lock:
            wait = self._last_request + self._min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _get(
        self, url: str, max_bytes: int, params: dict[str, str] | None = None
    ) -> httpx.Response:
        for _ in range(_MAX_REDIRECTS + 1):
            self._check_url(url)
            self._throttle()
            try:
                with self._client.stream("GET", url, params=params) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get("location", ""))
                        params = None
                        continue
                    if response.status_code == 404:
                        raise NotFoundError("arXiv returned 404 for the requested resource")
                    if response.status_code >= 400:
                        raise UpstreamError(f"arXiv returned HTTP {response.status_code}")
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise DocumentRejectedError(
                            f"Response is larger than the {max_bytes // (1024 * 1024)} MB limit"
                        )
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > max_bytes:
                            raise DocumentRejectedError(
                                f"Response is larger than the {max_bytes // (1024 * 1024)} MB limit"
                            )
                    return httpx.Response(
                        response.status_code, headers=response.headers, content=bytes(body)
                    )
            except httpx.TimeoutException as exc:
                raise UpstreamError("arXiv request timed out") from exc
            except httpx.TransportError as exc:
                raise UpstreamError(f"Could not reach arXiv: {type(exc).__name__}") from exc
        raise UpstreamError("arXiv redirected too many times")

    def fetch_metadata(self, arxiv_id: ArxivId) -> ArxivMetadata:
        response = self._get(
            self._api_url,
            _MAX_METADATA_BYTES,
            params={"id_list": str(arxiv_id), "max_results": "1"},
        )
        return parse_atom_entry(response.content, arxiv_id)

    def search(self, text: str, max_results: int) -> list[ArxivMetadata]:
        response = self._get(
            self._api_url,
            _MAX_METADATA_BYTES,
            params={
                "search_query": build_search_query(text),
                "max_results": str(min(max(max_results, 1), MAX_SEARCH_RESULTS)),
                "sortBy": "relevance",
            },
        )
        return parse_atom_feed(response.content)

    def download_pdf(self, arxiv_id: str, version: int, max_bytes: int) -> bytes:
        url = urljoin(self._pdf_base_url, f"{arxiv_id}v{version}")
        response = self._get(url, max_bytes)
        logger.info(
            "arxiv_pdf_downloaded", extra={"arxiv_id": arxiv_id, "bytes": len(response.content)}
        )
        return response.content

    def close(self) -> None:
        self._client.close()
