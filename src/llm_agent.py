"""
LLM(OpenAI GPT) 연동 계층 — 설계 원칙 "판단은 AI가, 계산은 엔진이"의 AI 쪽 절반.

브리핑 생성은 2단계로 나뉜다 (오케스트레이션은 graph.py의 LangGraph가 담당):
  1단계 (부문 에이전트) : 수신·여신·외환·기업연금 4개 부문 에이전트가 각자 자기
      부문 지표만 보고 추천 2건씩을 낸다. 프롬프트는 dept_prompts.py, 입력은
      dept_facts.py가 만든다. 하나의 프롬프트에 30개 지표를 몰아넣을 때 생기는
      '지시 희석 현상'을 막는 것이 목적이다.
  2단계 (Supervisor)    : 부문별 추천을 동일 척도로 비교해 최종 3대 과제를 확정하고
      지점장 브리핑 문구로 다듬는다.

이 파일이 제공하는 함수 (모두 graph.py의 노드 또는 페이지에서 호출):
  - run_dept_agent             : 부문 에이전트 1개 실행 (graph의 fan-out 노드가 호출)
  - synthesize_briefing        : Supervisor 종합 (graph의 supervisor 노드가 호출)
  - answer_regulation_question : rag.py가 찾아준 규정 청크만 근거로 답변 (규정 Q&A 챗)

OPENAI_API_KEY가 없으면 모든 함수가 결정론적 폴백 텍스트로 동작한다 — 데모를
먼저 배포하고 나중에 키만 추가해도 되도록 하기 위함이다.
키는 src/config.py 가 .env(로컬) 또는 환경변수(배포)에서 읽어온다.

모델은 GPT-5.6 계열 중 '균형형(Terra)' 등급을 사용한다 — 이 앱의 LLM 호출은
이미 계산된 사실을 근거로 짧은 한국어 문장을 만드는 제한적인 작업이라
최상위 프론티어 등급은 과하고, 균형형 등급이 비용 대비 적당하다.
"""
import json

from src.config import get_openai_api_key
from src.dept_prompts import DEPT_AGENT_SCHEMA, build_dept_prompt
from src.kpi_master import DEPARTMENTS

MODEL = "gpt-5.6-terra"

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
4개 부문(수신·여신·외환·기업연금) 전문 에이전트가 올린 추천 안건을 받아
지점 전체 관점에서 이번 주 3대 과제를 확정하는 것이 당신의 역할이다.

[RULE]
R1. 부문 에이전트가 올린 안건 중에서만 선택할 것. 새로운 지표를 임의로 만들지 말 것.
R2. 서로 다른 부문의 안건을 균형 있게 배분할 것. 한 부문에서만 3건을 뽑지 말 것.
R3. 부문 에이전트가 '영업중단 권고'로 올린 지표가 있으면 그 사실을 브리핑에 반영할 것.
R4. 모든 수치는 부문 에이전트가 인용한 값을 그대로 쓸 것. 스스로 계산하거나 추정하지 말 것.
R5. 지점 학습 규칙이 주어졌다면, 그 규칙이 왜 이번 추천에 반영되었는지 한 문장으로 언급할 것.

[GUARD] 입력에 없는 근거는 만들어내지 말 것.

[OUTPUT] 반드시 주어진 JSON 스키마 형식으로만 답할 것. 3개의 card는 가급적
'구간 연산'(구간 통과·상한 도달 관점), '벤치마킹'(peer 대비 격차 관점),
'사각지대'(놓치기 쉬운 조건부 지표 관점)를 하나씩 담되, 해당하는 안건이 없으면
있는 관점 안에서 3건을 구성할 것.
regulation_summary에는 선정된 과제들의 창구 안내 문구와 규정 유의사항을 묶어
그대로 전 직원에게 배포할 수 있는 형태로 작성할 것.
어조는 지점장에게 보고하는 간결하고 실무적인 한국어로 작성할 것."""

QA_SYSTEM_PROMPT = """\
[ROLE] 당신은 은행 KPI 세부 평가기준 규정 안내 챗봇이다.
[RULE] 아래에 주어진 '근거 문서 발췌'만을 근거로 답하라. 발췌에 없는 내용은
추측하지 말고 "해당 내용은 제공된 규정에서 확인되지 않습니다. 규정 확인 필요"라고 답하라.
답변 끝에는 반드시 참고한 소제목을 "(출처: OOO)" 형식으로 표기하라."""


def get_client():
    """OpenAI 클라이언트를 생성한다. 키가 없거나 SDK 초기화에 실패하면 None을 반환하여
    호출부가 폴백 로직으로 넘어가도록 한다."""
    api_key = get_openai_api_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# 1단계: 부문 전문 에이전트
# ──────────────────────────────────────────────────────────────────────

def _fallback_dept_result(dept_facts: dict) -> dict:
    """키가 없거나 호출이 실패했을 때 쓰는 결정론적 부문 결과.
    연산엔진이 이미 정렬해 둔 상위 지표를 그대로 추천으로 삼는다(환각 없음)."""
    indicators = dept_facts["indicators"]
    recommendations = []
    for ind in indicators[:2]:
        if ind["상한도달"] or not ind["잔여기간내_달성가능"]:
            continue
        recommendations.append({
            "indicator_name": ind["지표명"],
            "reason": (
                f"현재 {ind['현재실적']}{ind['단위']}({ind['달성률(%)']}%)로, "
                f"{ind['다음구간까지_필요실적']}{ind['단위']}를 더 확보하면 "
                f"+{ind['다음구간_통과시_추가점수']}점 구간을 통과합니다."
            ),
            "counter_guide": ind["규정요약"] or "규정 확인 후 안내 바랍니다.",
            "caution": ind["규정요약"] or "규정 확인 필요",
            # Validator가 대조할 수 있도록 엔진 값을 그대로 싣는다 (폴백은 정의상 항상 일치)
            "cited_current_value": ind["현재실적"],
            "cited_gap": ind["다음구간까지_필요실적"],
            "cited_score_gain": ind["다음구간_통과시_추가점수"],
        })

    return {
        "dept_summary": f"{dept_facts['dept']} 부문 지표 {len(indicators)}건을 검토했습니다.",
        "recommendations": recommendations,
        "stop_recommendations": dept_facts["maxed_indicators"][:2],
    }


def run_dept_agent(dept: str, dept_facts: dict, client=None) -> dict:
    """부문 전문 에이전트 1개를 실행한다.
    client를 넘기면 재사용하고, 없으면 새로 만든다(부문마다 재생성하지 않도록)."""
    client = client or get_client()
    if client is None:
        return _fallback_dept_result(dept_facts)

    user_prompt = (
        f"다음은 결정론적 연산엔진이 계산한 {dept} 부문 데이터다. "
        "이 숫자만 인용해서 추천을 작성하라.\n\n"
        f"[지점 프로파일]\n{json.dumps(dept_facts['branch_profile'], ensure_ascii=False)}\n\n"
        f"[담당 지표 현황]\n{json.dumps(dept_facts['indicators'], ensure_ascii=False)}\n\n"
        f"[상한 도달 지표]\n{json.dumps(dept_facts['maxed_indicators'], ensure_ascii=False)}\n\n"
        f"[유사지점 대비 격차]\n{json.dumps(dept_facts['benchmark_gaps'], ensure_ascii=False)}\n\n"
        f"[이 지점의 학습된 규칙]\n{json.dumps(dept_facts['learned_rules'], ensure_ascii=False)}\n\n"
        f"[규정 근거 발췌]\n{json.dumps(dept_facts['regulation_excerpts'], ensure_ascii=False)}\n"
    )
    try:
        response = client.responses.create(
            model=MODEL,
            instructions=build_dept_prompt(dept),
            input=user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "dept_agent_result",
                    "schema": DEPT_AGENT_SCHEMA,
                    "strict": True,
                },
            },
        )
        return json.loads(response.output_text)
    except Exception:
        return _fallback_dept_result(dept_facts)


# ──────────────────────────────────────────────────────────────────────
# 2단계: Supervisor 종합
# ──────────────────────────────────────────────────────────────────────

def _fallback_briefing(dept_results: dict[str, dict], learned_rules: list[dict]) -> dict:
    """부문 에이전트 결과를 규칙 기반으로 묶어 최종 브리핑을 만든다.
    부문을 돌아가며 하나씩 뽑아 한 부문 편중을 막는다(Supervisor R2와 같은 규칙)."""
    cards = []
    selected = []  # 카드로 채택된 (부문, 추천) 쌍 — 규정 요약도 이 목록만 다룬다.
    for dept in DEPARTMENTS:
        result = dept_results.get(dept)
        if not result or not result.get("recommendations"):
            continue
        rec = result["recommendations"][0]
        cards.append({
            "label": "구간 연산",
            "indicator_name": rec["indicator_name"],
            "message": f"[{dept}] {rec['reason']}",
        })
        selected.append((dept, rec))
        if len(cards) >= 3:
            break

    stop_notes = []
    for dept, result in dept_results.items():
        for name in (result.get("stop_recommendations") or [])[:1]:
            stop_notes.append(f"[{dept}] '{name}'은(는) 이미 만점 구간이므로 영업력을 다른 지표로 전환하십시오.")

    rule_note = f" (참고: {learned_rules[0]['rule_text']})" if learned_rules else ""
    headline = f"이번 주 3대 과제 — 부문별 전문 에이전트가 선별한 우선 과제입니다.{rule_note}"

    # 배포용 규정 요약은 '이번 주 과제로 채택된 지표'만 다뤄야 한다. 채택되지 않은
    # 지표까지 넣으면 지점장이 전 직원에게 배포했을 때 과제가 아닌 지표를 안내하게 된다.
    guide_lines = [f"· [{dept}] {rec['indicator_name']}: {rec['counter_guide']}" for dept, rec in selected]
    regulation_summary = "\n".join(guide_lines + stop_notes) or "관련 규정 요약을 확인해 주세요."

    return {"headline": headline, "cards": cards, "regulation_summary": regulation_summary}


def synthesize_briefing(dept_results: dict[str, dict], learned_rules: list[dict],
                        branch_profile: dict, client=None) -> dict:
    """Supervisor 단계: 부문별 결과를 종합해 최종 3대 과제를 확정한다."""
    client = client or get_client()
    if client is None:
        return _fallback_briefing(dept_results, learned_rules)

    user_prompt = (
        "다음은 4개 부문 전문 에이전트가 올린 추천 안건이다. "
        "이 안건들 중에서만 골라 이번 주 3대 과제를 확정하라.\n\n"
        f"[지점 프로파일]\n{json.dumps({'상권유형': branch_profile['type'], '규모': branch_profile['scale']}, ensure_ascii=False)}\n\n"
        f"[부문별 안건]\n{json.dumps(dept_results, ensure_ascii=False)}\n\n"
        f"[지점 학습 규칙]\n{json.dumps([r['rule_text'] for r in learned_rules], ensure_ascii=False)}\n"
    )
    try:
        response = client.responses.create(
            model=MODEL,
            instructions=SUPERVISOR_SYSTEM_PROMPT,
            input=user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "weekly_briefing",
                    "schema": BRIEFING_SCHEMA,
                    "strict": True,
                },
            },
        )
        return json.loads(response.output_text)
    except Exception:
        return _fallback_briefing(dept_results, learned_rules)


# ──────────────────────────────────────────────────────────────────────
# 규정 Q&A
# ──────────────────────────────────────────────────────────────────────

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
        response = client.responses.create(
            model=MODEL,
            instructions=QA_SYSTEM_PROMPT,
            input=f"[근거 문서 발췌]\n{context}\n\n[질문]\n{question}",
        )
        return response.output_text
    except Exception:
        titles = ", ".join(c["title"] for c in chunks)
        return f"{context}\n\n(출처: {titles})"
