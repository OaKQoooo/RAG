"""Pure helpers for standard-aware indexing and retrieval ranking."""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any, Iterable


STANDARD_LEVEL_LABELS = {
    "national_mandatory": "国家标准（强制性）",
    "national_recommended": "国家标准（推荐性）",
    "industry": "行业标准",
    "local": "地方标准",
    "group": "团体标准",
    "enterprise": "企业或公司标准",
    "project": "项目文件",
    "unknown": "未识别层级",
}

# This is a retrieval tie-breaker, not a legal conclusion. Applicability and
# explicit wording in the retrieved standards still control the final answer.
STANDARD_LEVEL_PRIORITIES = {
    "national_mandatory": float(os.getenv("RAG_PRIORITY_NATIONAL_MANDATORY", "1.00")),
    "national_recommended": float(os.getenv("RAG_PRIORITY_NATIONAL_RECOMMENDED", "0.90")),
    "industry": float(os.getenv("RAG_PRIORITY_INDUSTRY", "0.75")),
    "local": float(os.getenv("RAG_PRIORITY_LOCAL", "0.65")),
    "group": float(os.getenv("RAG_PRIORITY_GROUP", "0.50")),
    "enterprise": float(os.getenv("RAG_PRIORITY_ENTERPRISE", "0.40")),
    "project": float(os.getenv("RAG_PRIORITY_PROJECT", "0.30")),
    "unknown": float(os.getenv("RAG_PRIORITY_UNKNOWN", "0.20")),
}

_UPLOAD_PREFIX = re.compile(r"^(?:admin|user)_\d+_\d{14}_", re.IGNORECASE)
_INDUSTRY_PREFIXES = (
    "DL",
    "SL",
    "NB",
    "JGJ",
    "JT",
    "JTG",
    "HJ",
    "SY",
    "YD",
    "TB",
    "CB",
    "HG",
    "SH",
    "JC",
    "CECS",
)
_INTENT_KEYWORDS = {
    "national_mandatory": ("强制性国家标准", "强制国标"),
    "national_recommended": ("推荐性国家标准", "推荐国标"),
    "industry": ("行业标准", "行标"),
    "local": ("地方标准", "地标"),
    "group": ("团体标准", "团标"),
    "enterprise": ("企业标准", "公司标准", "企标"),
    "project": ("项目标准", "项目文件", "合同约定"),
}
_QUERY_STOP_TERMS = {
    "哪些",
    "什么",
    "如何",
    "是否",
    "基本",
    "规定",
    "要求",
    "有关",
    "相关",
    "问题",
    "内容",
    "标准",
    "规范",
    "条款",
    "以及",
    "怎么",
}
_QUERY_STOP_PHRASES = (
    "有哪些",
    "有什么",
    "是什么",
    "基本规定",
    "相关规定",
    "有关规定",
    "相关要求",
    "具体要求",
    "请问",
)


def normalize_standard_name(source: str) -> str:
    """Remove storage prefixes and normalize common compact standard codes."""
    value = str(source or "").strip()
    value = re.sub(r"\.(?:pdf|json)$", "", value, flags=re.IGNORECASE)
    value = _UPLOAD_PREFIX.sub("", value)
    value = value.replace("+", " ").replace("—", "-")
    value = re.sub(r"\bGBT(?=\s*\d)", "GB/T ", value, flags=re.IGNORECASE)
    value = re.sub(
        rf"\b({'|'.join(_INDUSTRY_PREFIXES)})T(?=\s*\d)",
        r"\1/T ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(GB/T|DL/T|SL/T|NB/T|DB\d*/T)(?=\d)", r"\1 ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "未知规范"


def extract_standard_code(source: str) -> str:
    """Extract a normalized standard code when the filename contains one."""
    value = normalize_standard_name(source).upper()
    patterns = [
        r"GB(?:/T)?\s*\d+(?:[.\-]\d+)*(?:\s*-\s*\d{4})?",
        rf"(?:{'|'.join(_INDUSTRY_PREFIXES)})(?:/T)?\s*\d+(?:[.\-]\d+)*(?:\s*-\s*\d{{4}})?",
        r"DB\d*(?:/T)?\s*\d+(?:[.\-]\d+)*(?:\s*-\s*\d{4})?",
        r"(?:T|Q)/[A-Z0-9._-]+\s*\d+(?:[.\-]\d+)*(?:\s*-\s*\d{4})?",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)).replace("--", "-")
    return ""


def classify_standard_level(source: str) -> str:
    """Classify a standard from its code or descriptive filename."""
    value = normalize_standard_name(source).upper().replace(" ", "")
    if re.search(r"(?:^|[^A-Z])GB/T\d", value):
        return "national_recommended"
    if re.search(r"(?:^|[^A-Z])GB\d", value):
        return "national_mandatory"
    if re.search(r"(?:^|[^A-Z])Q/", value) or any(item in value for item in ("企业标准", "公司标准")):
        return "enterprise"
    if re.search(r"(?:^|[^A-Z])T/", value) or "团体标准" in value:
        return "group"
    if re.search(r"(?:^|[^A-Z])DB\d", value) or "地方标准" in value:
        return "local"
    if re.search(rf"(?:^|[^A-Z])(?:{'|'.join(_INDUSTRY_PREFIXES)})(?:/T)?\d", value):
        return "industry"
    if any(item in value for item in ("项目标准", "项目文件", "合同", "技术要求")):
        return "project"
    return "unknown"


def describe_standard_level(level: str) -> str:
    return STANDARD_LEVEL_LABELS.get(level, STANDARD_LEVEL_LABELS["unknown"])


def raw_content(document: Any) -> str:
    metadata = getattr(document, "metadata", {}) or {}
    return str(metadata.get("raw_content") or getattr(document, "page_content", "") or "")


def enrich_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    source_original = str(metadata.get("source_original") or metadata.get("source_file") or "")
    source_file = normalize_standard_name(source_original)
    standard_level = str(metadata.get("standard_level") or classify_standard_level(source_file))
    metadata["source_original"] = source_original
    metadata["source_file"] = source_file
    metadata["standard_code"] = str(metadata.get("standard_code") or extract_standard_code(source_file))
    metadata["standard_level"] = standard_level
    metadata["standard_level_label"] = describe_standard_level(standard_level)
    metadata["standard_level_priority"] = STANDARD_LEVEL_PRIORITIES.get(
        standard_level,
        STANDARD_LEVEL_PRIORITIES["unknown"],
    )
    return metadata


def build_index_text(source: str, chapter: str, clause_id: str, content: str) -> str:
    """Include citation metadata in embeddings without leaking it into answers."""
    display_source = normalize_standard_name(source)
    level = describe_standard_level(classify_standard_level(display_source))
    return (
        f"规范名称：{display_source}\n"
        f"标准层级：{level}\n"
        f"章节：{chapter}\n"
        f"条款号：{clause_id}\n"
        f"正文：{content}"
    )


def rerank_text(document: Any) -> str:
    metadata = enrich_metadata(getattr(document, "metadata", {}) or {})
    return build_index_text(
        str(metadata.get("source_file") or ""),
        str(metadata.get("chapter") or ""),
        str(metadata.get("clause_id") or ""),
        raw_content(document),
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower()).replace("—", "-")


def _terms(value: str) -> set[str]:
    normalized = _normalized_text(value)
    terms = set(re.findall(r"[a-z]+(?:/[a-z]+)?[a-z0-9._/-]*|\d+(?:\.\d+)+", normalized))
    for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        terms.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return terms


def _overlap_score(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    return len(query_terms & _terms(text)) / len(query_terms)


def lexical_relevance_score(document: Any, query: str) -> float:
    metadata = enrich_metadata(getattr(document, "metadata", {}) or {})
    cleaned_query = str(query or "")
    for phrase in _QUERY_STOP_PHRASES:
        cleaned_query = cleaned_query.replace(phrase, "")
    all_query_terms = _terms(cleaned_query)
    query_terms = all_query_terms - _QUERY_STOP_TERMS or all_query_terms
    content_score = _overlap_score(query_terms, raw_content(document))
    chapter_score = _overlap_score(query_terms, str(metadata.get("chapter") or ""))
    source_score = _overlap_score(query_terms, str(metadata.get("source_file") or ""))
    clause_score = _overlap_score(query_terms, str(metadata.get("clause_id") or ""))
    return min(1.0, 0.52 * content_score + 0.28 * chapter_score + 0.14 * source_score + 0.06 * clause_score)


def _query_level_intent(query: str) -> set[str]:
    normalized = _normalized_text(query)
    levels = {
        level
        for level, keywords in _INTENT_KEYWORDS.items()
        if any(_normalized_text(keyword) in normalized for keyword in keywords)
    }
    if "国标" in normalized or "国家标准" in normalized:
        levels.update({"national_mandatory", "national_recommended"})
    return levels


def _float_metadata(metadata: dict[str, Any], name: str, default: float = 0.0) -> float:
    try:
        return float(metadata.get(name, default))
    except (TypeError, ValueError):
        return default


def _document_key(document: Any) -> tuple[str, str, str]:
    metadata = getattr(document, "metadata", {}) or {}
    return (
        str(metadata.get("document_id") or ""),
        str(metadata.get("clause_key") or metadata.get("clause_id") or ""),
        str(metadata.get("chunk_index") or "0"),
    )


def merge_candidates(*candidate_groups: Iterable[Any]) -> list[Any]:
    """Merge vector and lexical candidates while retaining their best scores."""
    merged: dict[tuple[str, str, str], Any] = {}
    for document in (item for group in candidate_groups for item in group):
        metadata = enrich_metadata(getattr(document, "metadata", {}) or {})
        key = _document_key(document)
        existing = merged.get(key)
        if existing is None:
            merged[key] = document
            continue
        existing_metadata = getattr(existing, "metadata", {}) or {}
        for score_name in ("_vector_score", "_lexical_candidate_score"):
            existing_metadata[score_name] = max(
                _float_metadata(existing_metadata, score_name),
                _float_metadata(metadata, score_name),
            )
    return list(merged.values())


def rank_documents(documents: Iterable[Any], query: str, max_chunks_per_clause: int = 1) -> list[Any]:
    """Fuse semantic, lexical and standard-level signals, then diversify clauses."""
    query_levels = _query_level_intent(query)
    query_code = extract_standard_code(query)
    ranked = []

    for document in documents:
        metadata = enrich_metadata(getattr(document, "metadata", {}) or {})
        lexical = lexical_relevance_score(document, query)
        vector = _float_metadata(metadata, "_vector_score")
        rerank_present = "_rerank_score" in metadata
        rerank = _float_metadata(metadata, "_rerank_score")
        authority = _float_metadata(metadata, "standard_level_priority", STANDARD_LEVEL_PRIORITIES["unknown"])

        if rerank_present:
            fused = 0.72 * rerank + 0.18 * vector + 0.10 * lexical
        else:
            fused = 0.65 * vector + 0.35 * lexical

        authority_bonus = 0.06 * authority
        intent_bonus = 0.14 if query_levels and metadata.get("standard_level") in query_levels else 0.0
        code_bonus = 0.22 if query_code and query_code == metadata.get("standard_code") else 0.0
        fused += authority_bonus + intent_bonus + code_bonus

        metadata["_lexical_score"] = round(lexical, 6)
        metadata["_authority_bonus"] = round(authority_bonus, 6)
        metadata["_standard_intent_bonus"] = round(intent_bonus, 6)
        metadata["_standard_code_bonus"] = round(code_bonus, 6)
        metadata["_fused_score"] = round(fused, 6)
        ranked.append(document)

    ranked.sort(key=lambda item: _float_metadata(getattr(item, "metadata", {}) or {}, "_fused_score"), reverse=True)

    selected = []
    clause_counts: Counter[tuple[str, str]] = Counter()
    for document in ranked:
        metadata = getattr(document, "metadata", {}) or {}
        clause_key = (
            str(metadata.get("source_file") or metadata.get("source_original") or metadata.get("document_id") or ""),
            re.sub(
                r"_p\d+$",
                "",
                str(metadata.get("clause_key") or metadata.get("clause_id") or ""),
            ),
        )
        if clause_counts[clause_key] >= max_chunks_per_clause:
            continue
        clause_counts[clause_key] += 1
        selected.append(document)
    return selected
