"""
간이 규정 검색기 (Hybrid RAG의 축소판).

실제 설계(보고서 4-2절)는 BM25 + 임베딩 + Reranker를 결합한 Hybrid RAG이지만,
데모에서는 '필수 로직만' 구현한다는 원칙에 따라 키워드 매칭 기반 검색으로 대체했다.
문서를 "### 소제목" 단위 청크로 분할하고, 질문 토큰과의 중복도로 점수를 매겨
상위 청크만 LLM 컨텍스트로 전달한다. 매칭되는 청크가 하나도 없으면 근거 없음으로
처리하여 "규정 확인 필요" 가드레일이 작동하도록 한다(보고서의 GUARD 규칙).
"""
import re
from pathlib import Path

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "kpi_guideline.md"

_STOPWORDS = {"무엇", "어떻게", "그리고", "합니다", "인가요", "인지", "대해", "알려줘", "설명해줘", "관련"}


def load_chunks(doc_path: Path = DOC_PATH) -> list[dict]:
    text = doc_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    chunks = []
    current_section = "공통"
    current_title = None
    buf: list[str] = []

    def flush():
        if current_title and buf:
            chunks.append({
                "section": current_section,
                "title": current_title,
                "text": "\n".join(buf).strip(),
            })

    for line in lines:
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            current_title = None
            buf = []
        elif line.startswith("### "):
            flush()
            current_title = line[4:].strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return chunks


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text)
    return {t for t in tokens if len(t) >= 2 and t not in _STOPWORDS}


def search(query: str, chunks: list[dict] | None = None, top_k: int = 3) -> list[dict]:
    chunks = chunks if chunks is not None else load_chunks()
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scored = []
    for c in chunks:
        c_tokens = _tokenize(c["title"] + " " + c["text"])
        overlap = sum(1 for qt in q_tokens if any(qt in ct or ct in qt for ct in c_tokens))
        if overlap > 0:
            scored.append({**c, "score": overlap})

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
