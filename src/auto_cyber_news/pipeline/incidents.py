"""Deterministic incident grouping for related enriched articles."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from auto_cyber_news.models.article import EnrichedArticle, SeverityLevel
from auto_cyber_news.models.incident import SecurityIncident
from auto_cyber_news.utils.hashing import content_hash

CONTENT_HASH_PREFIX_LEN = 16
TITLE_SIMILARITY_THRESHOLD = 0.55
MIN_SHARED_INCIDENT_KEYWORDS = 2
MAX_RELATED_ARTICLES_IN_ALERT = 5

_INCIDENT_KEYWORDS = frozenset(
    {
        "supply",
        "chain",
        "cve",
        "worm",
        "exploit",
        "ransomware",
        "malware",
        "compromise",
        "jenkins",
        "npm",
        "pypi",
        "campaign",
        "breach",
        "zero",
        "day",
        "trojan",
        "backdoor",
        "apt",
    },
)
_TITLE_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "about",
        "after",
        "over",
        "news",
        "report",
        "reports",
    },
)
_SEVERITY_ORDER = {
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}


def group_into_incidents(articles: tuple[EnrichedArticle, ...]) -> tuple[SecurityIncident, ...]:
    """Group enriched articles into security incidents using deterministic rules."""
    if not articles:
        return ()

    union_find = _UnionFind(len(articles))
    for left in range(len(articles)):
        for right in range(left + 1, len(articles)):
            if _articles_related(articles[left], articles[right]):
                union_find.union(left, right)

    grouped: dict[int, list[EnrichedArticle]] = {}
    for index, article in enumerate(articles):
        root = union_find.find(index)
        grouped.setdefault(root, []).append(article)

    incidents: list[SecurityIncident] = []
    for group in grouped.values():
        incident_articles = tuple(
            sorted(group, key=lambda article: (-_SEVERITY_ORDER[article.severity], -article.risk_score)),
        )
        incidents.append(_build_incident(incident_articles))

    return tuple(sorted(incidents, key=lambda incident: (-_SEVERITY_ORDER[incident.max_severity], -incident.max_risk_score)))


def generate_incident_id(articles: tuple[EnrichedArticle, ...]) -> str:
    """Build a stable incident identifier for a related article group."""
    canonical_urls = sorted({article.article.canonical_url for article in articles})
    if len(canonical_urls) == 1:
        return content_hash(f"incident|canonical|{canonical_urls[0]}")

    lead = _lead_article(articles)
    domains = sorted({_article_domain(article.article.canonical_url) for article in articles})
    keywords = sorted(_incident_keywords_for_article(lead))
    title_signature = _title_signature(lead.article.title)
    payload = "|".join(
        [
            "incident",
            *domains,
            title_signature,
            *keywords,
        ],
    )
    return content_hash(payload)


def _build_incident(articles: tuple[EnrichedArticle, ...]) -> SecurityIncident:
    lead = _lead_article(articles)
    categories: list[str] = []
    cves: list[str] = []
    for article in articles:
        for category in article.categories:
            if category not in categories:
                categories.append(category)
        for cve in article.detected_cves:
            if cve not in cves:
                cves.append(cve)

    return SecurityIncident(
        incident_id=generate_incident_id(articles),
        title=lead.article.title,
        articles=articles,
        max_severity=lead.severity,
        max_risk_score=max(article.risk_score for article in articles),
        sources=tuple(sorted({article.article.source for article in articles})),
        categories=tuple(categories),
        detected_cves=tuple(cves),
    )


def _articles_related(left: EnrichedArticle, right: EnrichedArticle) -> bool:
    if left.article.canonical_url == right.article.canonical_url:
        return True
    if left.article.content_hash == right.article.content_hash:
        return True
    if _content_hash_prefix_match(left.article.content_hash, right.article.content_hash):
        return True
    if _cves_overlap(left, right):
        return True
    if _shared_incident_keywords(left, right):
        return True
    if _same_domain_and_similar_title(left, right):
        return True
    return False


def _content_hash_prefix_match(left_hash: str, right_hash: str) -> bool:
    if left_hash == right_hash:
        return False
    prefix_length = min(CONTENT_HASH_PREFIX_LEN, len(left_hash), len(right_hash))
    if prefix_length == 0:
        return False
    return left_hash[:prefix_length] == right_hash[:prefix_length]


def _cves_overlap(left: EnrichedArticle, right: EnrichedArticle) -> bool:
    if not left.detected_cves or not right.detected_cves:
        return False
    return bool(set(left.detected_cves) & set(right.detected_cves))


def _shared_incident_keywords(left: EnrichedArticle, right: EnrichedArticle) -> bool:
    shared = _incident_keywords_for_article(left) & _incident_keywords_for_article(right)
    return len(shared) >= MIN_SHARED_INCIDENT_KEYWORDS


def _same_domain_and_similar_title(left: EnrichedArticle, right: EnrichedArticle) -> bool:
    left_domain = _article_domain(left.article.canonical_url)
    right_domain = _article_domain(right.article.canonical_url)
    if left_domain != right_domain:
        return False
    return _titles_similar(left.article.title, right.article.title)


def _incident_keywords_for_article(article: EnrichedArticle) -> set[str]:
    haystack = f"{article.article.title} {article.article.raw_content or ''}".casefold()
    return {keyword for keyword in _INCIDENT_KEYWORDS if keyword in haystack}


def _titles_similar(left_title: str, right_title: str) -> bool:
    left_tokens = _title_tokens(left_title)
    right_tokens = _title_tokens(right_title)
    if not left_tokens or not right_tokens:
        return False

    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    if len(union) == 0:
        return False
    if len(intersection) / len(union) >= TITLE_SIMILARITY_THRESHOLD:
        return True

    left_normalized = " ".join(sorted(left_tokens))
    right_normalized = " ".join(sorted(right_tokens))
    return left_normalized in right_normalized or right_normalized in left_normalized


def _title_tokens(title: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", title.casefold())
    return {token for token in tokens if len(token) > 2 and token not in _TITLE_STOPWORDS}


def _title_signature(title: str) -> str:
    return "|".join(sorted(_title_tokens(title))[:12])


def _article_domain(url: str) -> str:
    netloc = urlsplit(url).netloc.casefold()
    if netloc.startswith("www."):
        return netloc[4:]
    return netloc


def _lead_article(articles: tuple[EnrichedArticle, ...]) -> EnrichedArticle:
    return max(articles, key=lambda article: (_SEVERITY_ORDER[article.severity], article.risk_score))


class _UnionFind:
    """Disjoint-set union for incident clustering."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, index: int) -> int:
        parent = self._parent[index]
        if parent != index:
            self._parent[index] = self.find(parent)
        return self._parent[index]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root
