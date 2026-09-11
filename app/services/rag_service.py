import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.agent import AgentKnowledgeQueryArguments


RAG_TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_erp_manual",
        "description": (
            "检索 ShoeFlow ERP 操作手册。用户询问系统如何使用、"
            "业务规则、操作步骤、字段含义、错误处理或 Agent 安全规则时"
            "必须使用。该工具只读取知识文档，不查询实时库存，也不修改数据。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户关于 ERP 使用方法或规则的问题",
                },
                "limit": {
                    "type": "integer",
                    "description": "最多返回知识片段数，默认 3，最大 5",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True)
class KnowledgeChunk:
    source_id: str
    document_title: str
    section_title: str
    content: str
    term_counts: Counter[str]
    token_count: int


@dataclass(frozen=True)
class KnowledgeIndex:
    chunks: tuple[KnowledgeChunk, ...]
    document_frequency: dict[str, int]
    average_length: float


def _resolve_knowledge_dir() -> Path:
    configured_path = Path(settings.rag_knowledge_dir)

    if configured_path.is_absolute():
        return configured_path

    project_root = Path(__file__).resolve().parents[2]
    return project_root / configured_path


def _knowledge_files() -> list[Path]:
    knowledge_dir = _resolve_knowledge_dir()

    if not knowledge_dir.is_dir():
        return []

    return sorted(
        path
        for path in knowledge_dir.rglob("*.md")
        if path.is_file()
    )


def _knowledge_fingerprint(
    files: list[Path],
) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (
            str(path.resolve()),
            path.stat().st_mtime_ns,
            path.stat().st_size,
        )
        for path in files
    )


def _tokenize(text: str) -> list[str]:
    normalized = text.upper()
    tokens = re.findall(
        r"[A-Z0-9]+(?:[._/-][A-Z0-9]+)*",
        normalized,
    )

    for chinese_group in re.findall(
        r"[\u4e00-\u9fff]+",
        normalized,
    ):
        if len(chinese_group) == 1:
            tokens.append(chinese_group)
            continue

        tokens.extend(
            chinese_group[index:index + 2]
            for index in range(len(chinese_group) - 1)
        )

        if len(chinese_group) >= 3:
            tokens.extend(
                chinese_group[index:index + 3]
                for index in range(len(chinese_group) - 2)
            )

    return tokens


def _split_long_section(content: str) -> list[str]:
    maximum = settings.rag_max_chunk_chars

    if len(content) <= maximum:
        return [content]

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", content)
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        added_length = len(paragraph) + (2 if current else 0)

        if current and current_length + added_length > maximum:
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0

        if len(paragraph) > maximum:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_length = 0

            chunks.extend(
                paragraph[start:start + maximum]
                for start in range(0, len(paragraph), maximum)
            )
            continue

        current.append(paragraph)
        current_length += added_length

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _parse_markdown(path: Path) -> list[KnowledgeChunk]:
    text = path.read_text(encoding="utf-8")
    document_title = path.stem
    current_section = "概述"
    current_lines: list[str] = []
    raw_sections: list[tuple[str, str]] = []

    def flush_section() -> None:
        content = "\n".join(current_lines).strip()

        if content:
            raw_sections.append(
                (current_section, content)
            )

        current_lines.clear()

    for line in text.splitlines():
        if line.startswith("# "):
            document_title = line[2:].strip() or document_title
            continue

        if line.startswith("## "):
            flush_section()
            current_section = line[3:].strip() or "未命名章节"
            continue

        current_lines.append(line)

    flush_section()

    chunks: list[KnowledgeChunk] = []
    sequence = 0

    for section_title, section_content in raw_sections:
        for part in _split_long_section(section_content):
            sequence += 1
            searchable_text = (
                f"{document_title} {section_title} {part}"
            )
            term_counts = Counter(
                _tokenize(searchable_text)
            )
            chunks.append(
                KnowledgeChunk(
                    source_id=(
                        f"{path.name}#section-{sequence}"
                    ),
                    document_title=document_title,
                    section_title=section_title,
                    content=part,
                    term_counts=term_counts,
                    token_count=sum(term_counts.values()),
                )
            )

    return chunks


@lru_cache(maxsize=8)
def _build_index(
    fingerprint: tuple[tuple[str, int, int], ...],
) -> KnowledgeIndex:
    chunks: list[KnowledgeChunk] = []

    for path_string, _, _ in fingerprint:
        chunks.extend(
            _parse_markdown(Path(path_string))
        )

    document_frequency: Counter[str] = Counter()

    for chunk in chunks:
        document_frequency.update(
            chunk.term_counts.keys()
        )

    average_length = (
        sum(chunk.token_count for chunk in chunks)
        / len(chunks)
        if chunks
        else 0.0
    )

    return KnowledgeIndex(
        chunks=tuple(chunks),
        document_frequency=dict(document_frequency),
        average_length=average_length,
    )


def _tf_idf_cosine(
    query_counts: Counter[str],
    chunk: KnowledgeChunk,
    *,
    document_frequency: dict[str, int],
    document_count: int,
) -> float:
    query_vector: dict[str, float] = {}
    chunk_vector: dict[str, float] = {}

    for term in query_counts.keys() | chunk.term_counts.keys():
        frequency = document_frequency.get(term, 0)
        inverse_frequency = (
            math.log((document_count + 1) / (frequency + 1))
            + 1
        )

        if term in query_counts:
            query_vector[term] = (
                (1 + math.log(query_counts[term]))
                * inverse_frequency
            )

        if term in chunk.term_counts:
            chunk_vector[term] = (
                (1 + math.log(chunk.term_counts[term]))
                * inverse_frequency
            )

    dot_product = sum(
        query_vector.get(term, 0.0) * value
        for term, value in chunk_vector.items()
    )
    query_norm = math.sqrt(
        sum(value * value for value in query_vector.values())
    )
    chunk_norm = math.sqrt(
        sum(value * value for value in chunk_vector.values())
    )

    if query_norm == 0 or chunk_norm == 0:
        return 0.0

    return dot_product / (query_norm * chunk_norm)


def _bm25_score(
    query_counts: Counter[str],
    chunk: KnowledgeChunk,
    *,
    index: KnowledgeIndex,
) -> float:
    if not index.chunks or index.average_length <= 0:
        return 0.0

    document_count = len(index.chunks)
    score = 0.0
    k1 = 1.5
    b = 0.75

    for term in query_counts:
        term_frequency = chunk.term_counts.get(term, 0)

        if term_frequency == 0:
            continue

        frequency = index.document_frequency.get(term, 0)
        inverse_frequency = math.log(
            1
            + (
                document_count
                - frequency
                + 0.5
            )
            / (frequency + 0.5)
        )
        denominator = (
            term_frequency
            + k1
            * (
                1
                - b
                + b
                * chunk.token_count
                / index.average_length
            )
        )
        score += inverse_frequency * (
            term_frequency * (k1 + 1)
            / denominator
        )

    return score


def _title_overlap(
    query_counts: Counter[str],
    chunk: KnowledgeChunk,
) -> float:
    title_tokens = set(
        _tokenize(
            f"{chunk.document_title} {chunk.section_title}"
        )
    )
    query_tokens = set(query_counts)

    if not query_tokens:
        return 0.0

    return len(query_tokens & title_tokens) / len(query_tokens)


def search_knowledge(
    query: str,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    files = _knowledge_files()
    fingerprint = _knowledge_fingerprint(files)
    index = _build_index(fingerprint)
    query_counts = Counter(_tokenize(query))
    result_limit = limit or settings.rag_default_top_k

    if not index.chunks or not query_counts:
        return {
            "query": query,
            "count": 0,
            "items": [],
        }

    scored_items: list[tuple[float, KnowledgeChunk]] = []

    for chunk in index.chunks:
        cosine_score = _tf_idf_cosine(
            query_counts,
            chunk,
            document_frequency=index.document_frequency,
            document_count=len(index.chunks),
        )
        bm25_score = _bm25_score(
            query_counts,
            chunk,
            index=index,
        )
        normalized_bm25 = 1 - math.exp(-bm25_score / 4)
        heading_score = _title_overlap(
            query_counts,
            chunk,
        )
        combined_score = min(
            1.0,
            0.52 * cosine_score
            + 0.28 * normalized_bm25
            + 0.2 * heading_score,
        )

        if combined_score >= settings.rag_min_score:
            scored_items.append(
                (combined_score, chunk)
            )

    scored_items.sort(
        key=lambda item: item[0],
        reverse=True,
    )
    selected_items = scored_items[:result_limit]

    return {
        "query": query,
        "count": len(selected_items),
        "items": [
            {
                "source_id": chunk.source_id,
                "document_title": chunk.document_title,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "excerpt": (
                    chunk.content
                    if len(chunk.content) <= 220
                    else f"{chunk.content[:217].rstrip()}..."
                ),
                "score": round(score, 4),
            }
            for score, chunk in selected_items
        ],
    }


def execute_knowledge_tool(
    raw_arguments: Any,
) -> dict[str, Any]:
    try:
        arguments = (
            AgentKnowledgeQueryArguments.model_validate(
                raw_arguments
            )
        )
    except ValidationError:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_KNOWLEDGE_QUERY",
                "message": "知识库检索参数无效，请重新描述问题",
            },
        }

    data = search_knowledge(
        arguments.query,
        limit=arguments.limit,
    )

    if data["count"] == 0:
        return {
            "ok": False,
            "error": {
                "code": "KNOWLEDGE_NOT_FOUND",
                "message": (
                    "操作手册中没有找到足够相关的内容，"
                    "请说明具体功能或操作场景"
                ),
            },
            "data": data,
        }

    return {
        "ok": True,
        "data": data,
    }
