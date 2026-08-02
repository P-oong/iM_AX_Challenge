"""
LLM(Claude) 연동 계층 — 보고서의 설계 원칙 "판단은 AI가, 계산은 엔진이"의 AI 쪽 절반.

이 파일이 하는 일은 딱 두 가지뿐이다:
  1) generate_weekly_briefing : scoring_engine/benchmarking/feedback_store가 이미
     계산해 둔 '숫자'를 자연어 브리핑 문장으로 번역한다. 점수·구간·ROI를 LLM이
     다시 계산하지 않도록 프롬프트에 명시하고, 출력은 JSON 스키마로 강제한다.
  2) answer_regulation_question : rag.py가 찾아준 규정 청크만 근거로 답변한다.
     근거 청크가 없으면 LLM을 호출하지 않고 "규정 확인 필요"를 반환한다(GUARD 규칙).

ANTHROPIC_API_KEY가 설정되어 있지 않으면 두 함수 모두 결정론적 폴백 텍스트로
동작한다 — 데모를 먼저 배포하고 새벽에 키만 추가해도 되도록 하기 위함이다.
"""
import json
import os

MODEL = "claude-opus-5"

BRIEFING_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "이번 주 한 줄 요약"},
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "구간 연산 | 벤치마킹 | 사각지대 중 하나"},
                    "indicator_name": {"type": "string"},
                    "message": {"type": "string", "description": "지점장에게 보여줄 브리핑 문장"},
                },
                "required": ["label", "indicator_name", "message"],
                "additionalProperties": False,
            },
        },
        "regulation_summary": {"type": "string", "description": "배포용 규정 요약 (창구 교육 자료)"},
    },
    "required": ["headline", "cards", "regulation_summary"],
    "additionalProperties": False,
}

SUPERVISOR_SYSTEM_PROMPT = """\
[ROLE] 당신은 은행 영업점의 KPI 전담 책임자(Supervisor Agent)다.
[RULE]
R1. 이미 상한(만점)에 도달한 지표는 "영업중단 권고"로 안내할 것.
R2. 잔여기간 내 물리적으로 달성 불가능한 지표는 추천하지 말 것.
R3. 지점 학습 규칙(가중치 하향)이 주어지면 해당 부문 지표의 우선순위를 낮추고,
    상권 특성에 맞는 대체 지표를 제안할 것.
R4. 모든 수치(점수, 필요건수, 달성률 등)는 입력으로 주어진 값만 그대로 인용할 것.
    스스로 숫자를 계산하거나 추정하지 말 것.
[GUARD] 입력에 없는 근거는 만들어내지 말 것.
[OUTPUT] 반드시 주어진 JSON 스키마 형식으로만 답할 것. 3개의 card는 각각
'구간 연산'(상한도달/가성비 지표), '벤치마킹'(peer 대비 뒤처진 지표),
'사각지대'(놓치기 쉬운 지표) 관점을 하나씩 담을 것. 어조는 지점장에게 보고하는
간결하고 실무적인 한국어로 작성할 것."""

QA_SYSTEM_PROMPT = """\
[ROLE] 당신은 은행 KPI 세부 평가기준 규정 안내 챗봇이다.
[RULE] 아래에 주어진 '근거 문서 발췌'만을 근거로 답하라. 발췌에 없는 내용은
추측하지 말고 "해당 내용은 제공된 규정에서 확인되지 않습니다. 규정 확인 필요"라고 답하라.
답변 끝에는 반드시 참고한 소제목을 "(출처: OOO)" 형식으로 표기하라."""


def get_client():
    """Anthropic 클라이언트를 생성한다. 키가 없거나 SDK 초기화에 실패하면 None을 반환하여
    호출부가 폴백 로직으로 넘어가도록 한다."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            api_key = None
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


def _fallback_briefing(facts: dict) -> dict:
    cards = []
    for item in facts["top_roi"][:1]:
        cards.append({
            "label": "구간 연산",
            "indicator_name": item["name"],
            "message": (
                f"'{item['name']}'은(는) 현재 {item['current_value']}{item['unit']} 실적으로 "
                f"{item['gap']}{item['unit']}만 더 확보하면 +{item['score_gain']}점 구간을 통과합니다. "
                f"잔여 {item['remaining_days']}영업일 내 달성 가능한 최우선 과제입니다."
            ),
        })
    for item in facts["maxed"][:1]:
        cards.append({
            "label": "구간 연산",
            "indicator_name": item["name"],
            "message": f"'{item['name']}'은(는) 이미 만점 구간에 도달했습니다. 추가 영업을 멈추고 인력을 다른 지표로 전환하십시오.",
        })
    for item in facts["underperforming"][:1]:
        cards.append({
            "label": "벤치마킹",
            "indicator_name": item["name"],
            "message": (
                f"유사 상권 1등 지점({item['peer_top_name']})은 '{item['name']}' 달성률 {item['peer_top_pct']}%이나, "
                f"당점은 {item['my_pct']}%로 {item['gap_to_top']}%p 뒤처져 있습니다. 집중 공략이 필요합니다."
            ),
        })
    for item in facts["micro"][:1]:
        cards.append({
            "label": "사각지대",
            "indicator_name": item["name"],
            "message": (
                f"'{item['name']}'은(는) 달성률 {item['attainment_pct']}%로 놓치기 쉬운 조건부 지표입니다. "
                f"창구 필수 안내 멘트로 추가해 주십시오."
            ),
        })

    rule_note = ""
    if facts["learned_rules"]:
        r = facts["learned_rules"][0]
        rule_note = f" (참고: {r['rule_text']})"

    headline = f"이번 주 3대 과제 — 가성비 지표 확보, 벤치마킹 격차 해소, 사각지대 점검.{rule_note}"
    regulation_summary = facts.get("regulation_note", "관련 규정 요약을 확인해 주세요.")
    return {"headline": headline, "cards": cards, "regulation_summary": regulation_summary}


def generate_weekly_briefing(facts: dict) -> dict:
    """facts: dict(top_roi, maxed, underperforming, micro, learned_rules, regulation_note 등
    scoring_engine/benchmarking/feedback_store가 계산한 결과만 담긴 순수 데이터)."""
    client = get_client()
    if client is None:
        return _fallback_briefing(facts)

    user_prompt = (
        "다음은 결정론적 연산엔진이 계산한 사실 데이터다. 이 숫자만 인용해서 브리핑을 작성하라.\n\n"
        f"[가성비 지표 후보]\n{json.dumps(facts['top_roi'], ensure_ascii=False)}\n\n"
        f"[상한도달 지표]\n{json.dumps(facts['maxed'], ensure_ascii=False)}\n\n"
        f"[벤치마킹 뒤처진 지표]\n{json.dumps(facts['underperforming'], ensure_ascii=False)}\n\n"
        f"[사각지대 후보 지표]\n{json.dumps(facts['micro'], ensure_ascii=False)}\n\n"
        f"[학습된 지점 규칙]\n{json.dumps(facts['learned_rules'], ensure_ascii=False)}\n\n"
        f"[규정 근거 발췌]\n{facts.get('regulation_note', '')}\n"
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SUPERVISOR_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": BRIEFING_SCHEMA}},
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception:
        return _fallback_briefing(facts)


def answer_regulation_question(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return "해당 내용은 제공된 규정에서 확인되지 않습니다. 규정 확인 필요."

    client = get_client()
    context = "\n\n".join(f"### {c['title']}\n{c['text']}" for c in chunks)

    if client is None:
        # 폴백: 검색된 발췌를 그대로 요약 없이 보여준다 (환각 없음이 보장됨)
        titles = ", ".join(c["title"] for c in chunks)
        return f"{context}\n\n(출처: {titles})"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=QA_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"[근거 문서 발췌]\n{context}\n\n[질문]\n{question}",
            }],
        )
        return next(b.text for b in response.content if b.type == "text")
    except Exception:
        titles = ", ".join(c["title"] for c in chunks)
        return f"{context}\n\n(출처: {titles})"
