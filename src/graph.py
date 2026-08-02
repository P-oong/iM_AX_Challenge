"""
LangGraph 멀티에이전트 오케스트레이션 (보고서 4-2-(4) 구현).

그래프 구조:

    START
      │
      ▼
    dispatch ──────────┐  (Send fan-out: 부문 수만큼 동시 실행)
      │                │
      ▼                │
    dept_agent ×N (병렬)
      │
      ▼
    validate_depts ────┐
      │                │ 문제 발견 + 재시도 여력 → 해당 부문만 재실행
      │◄───────────────┘
      ▼ (통과 or 재시도 소진)
    supervisor
      │
      ▼
    validate_briefing ─┐
      │                │ 문제 발견 + 재시도 여력 → supervisor 재실행
      │◄───────────────┘
      ▼ (통과 or 재시도 소진)
     END

설계 원칙 유지:
  - scoring_engine / benchmarking / rag 는 LLM이 호출하는 tool이 아니라 그래프 바깥에서
    이미 계산을 끝낸 상태로 들어온다. LLM에게 계산을 맡기지 않는다는 원칙 그대로다.
  - Validator 노드도 LLM이 아닌 결정론적 Python(validator.py)이다.
  - 재시도는 문제가 있는 부문만 다시 돌린다 (정상 부문은 결과를 그대로 유지).
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src import llm_agent, validator
from src.kpi_master import DEPARTMENTS

MAX_DEPT_RETRIES = 1        # 부문 에이전트 재시도 횟수
MAX_BRIEFING_RETRIES = 1    # Supervisor 재시도 횟수


class BranchKPIState(TypedDict, total=False):
    """모든 노드가 공유하는 단일 상태(보고서의 BranchKPIState)."""
    # ── 입력 (그래프 실행 전 연산엔진이 채워 넣는다) ──
    all_dept_facts: dict          # 부문별 에이전트 입력
    learned_rules: list           # 피드백에서 학습된 지점 규칙
    branch_profile: dict          # 지점 프로파일
    engine_index: dict            # 검증용 정답표 (지표명 → 엔진 계산값)

    # ── 부문 에이전트 결과 (병렬 쓰기 → dict 병합 리듀서 필요) ──
    dept_results: Annotated[dict, operator.or_]

    # ── 재실행 대상 및 재시도 카운터 ──
    pending_depts: list           # 이번 라운드에 실행할 부문 목록 (비면 전 부문 통과)
    briefing_issues: list         # 최종 브리핑 검증 결과 (비면 통과)
    dept_retries: int
    briefing_retries: int

    # ── 검증 로그 (라운드마다 누적) ──
    validation_log: Annotated[list, operator.add]

    # ── 최종 산출물 ──
    briefing: dict


# ──────────────────────────────────────────────────────────────────────
# 노드
# ──────────────────────────────────────────────────────────────────────

def node_dispatch(state: BranchKPIState) -> dict:
    """Supervisor의 과제 분배 단계. 첫 라운드에는 전 부문을 대상으로 한다."""
    if not state.get("pending_depts"):
        return {"pending_depts": list(DEPARTMENTS)}
    return {}


def fan_out_depts(state: BranchKPIState):
    """pending_depts에 있는 부문만 병렬로 띄운다(Send API).
    재시도 라운드에서는 문제가 있던 부문만 다시 실행된다."""
    return [
        Send("dept_agent", {
            "dept": dept,
            "facts": state["all_dept_facts"][dept],
        })
        for dept in state["pending_depts"]
        if dept in state["all_dept_facts"]
    ]


def node_dept_agent(payload: dict) -> dict:
    """부문 전문 에이전트 1개. Send로 전달된 payload만 받는다(전체 상태가 아님)."""
    dept = payload["dept"]
    result = llm_agent.run_dept_agent(dept, payload["facts"])
    return {"dept_results": {dept: result}}


def node_validate_depts(state: BranchKPIState) -> dict:
    """부문 결과를 결정론적으로 검증하고, 문제가 있는 부문을 다음 라운드 대상으로 지정한다."""
    issues_by_dept = validator.validate_all_dept_results(
        state.get("dept_results", {}), state["engine_index"]
    )
    round_no = state.get("dept_retries", 0) + 1

    if not issues_by_dept:
        return {
            "pending_depts": [],
            "validation_log": [f"[부문 검증 {round_no}회차] 전 부문 통과"],
        }

    flat = [msg for msgs in issues_by_dept.values() for msg in msgs]
    return {
        "pending_depts": list(issues_by_dept.keys()),
        "validation_log": [f"[부문 검증 {round_no}회차] {len(flat)}건 발견"] + flat,
    }


def route_after_dept_validation(state: BranchKPIState) -> str:
    """문제가 있고 재시도 여력이 남았으면 해당 부문만 재실행, 아니면 Supervisor로 진행."""
    if state.get("pending_depts") and state.get("dept_retries", 0) < MAX_DEPT_RETRIES:
        return "retry_depts"
    return "to_supervisor"


def node_retry_depts(state: BranchKPIState) -> dict:
    """재시도 카운터만 올리는 통과 노드 (다음 dispatch에서 pending_depts가 쓰인다)."""
    return {"dept_retries": state.get("dept_retries", 0) + 1}


def node_supervisor(state: BranchKPIState) -> dict:
    """부문별 안건을 종합해 최종 3대 과제를 확정한다."""
    briefing = llm_agent.synthesize_briefing(
        state.get("dept_results", {}),
        state.get("learned_rules", []),
        state["branch_profile"],
    )
    return {"briefing": briefing}


def node_validate_briefing(state: BranchKPIState) -> dict:
    issues = validator.validate_briefing(
        state.get("briefing", {}), state.get("dept_results", {}), state["engine_index"]
    )
    round_no = state.get("briefing_retries", 0) + 1
    if not issues:
        return {"briefing_issues": [], "validation_log": [f"[최종 검증 {round_no}회차] 통과"]}
    return {
        "briefing_issues": issues,
        "validation_log": [f"[최종 검증 {round_no}회차] {len(issues)}건 발견"] + issues,
    }


def route_after_briefing_validation(state: BranchKPIState) -> str:
    """검증 결과(briefing_issues)만 보고 판단한다. 로그 문자열을 파싱하지 않는다 —
    이전 라운드의 낡은 로그에 반응하는 것을 막기 위함이다."""
    if state.get("briefing_issues") and state.get("briefing_retries", 0) < MAX_BRIEFING_RETRIES:
        return "retry_briefing"
    return "done"


def node_retry_briefing(state: BranchKPIState) -> dict:
    return {"briefing_retries": state.get("briefing_retries", 0) + 1}


# ──────────────────────────────────────────────────────────────────────
# 그래프 조립
# ──────────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(BranchKPIState)

    g.add_node("dispatch", node_dispatch)
    g.add_node("dept_agent", node_dept_agent)
    g.add_node("validate_depts", node_validate_depts)
    g.add_node("retry_depts", node_retry_depts)
    g.add_node("supervisor", node_supervisor)
    g.add_node("validate_briefing", node_validate_briefing)
    g.add_node("retry_briefing", node_retry_briefing)

    g.add_edge(START, "dispatch")
    # fan-out: dispatch → dept_agent 를 부문 수만큼 동시에
    g.add_conditional_edges("dispatch", fan_out_depts, ["dept_agent"])
    # fan-in: 모든 dept_agent 가 끝나야 validate_depts 가 실행된다
    g.add_edge("dept_agent", "validate_depts")

    g.add_conditional_edges(
        "validate_depts", route_after_dept_validation,
        {"retry_depts": "retry_depts", "to_supervisor": "supervisor"},
    )
    g.add_edge("retry_depts", "dispatch")  # 자기교정 루프

    g.add_edge("supervisor", "validate_briefing")
    g.add_conditional_edges(
        "validate_briefing", route_after_briefing_validation,
        {"retry_briefing": "retry_briefing", "done": END},
    )
    g.add_edge("retry_briefing", "supervisor")  # 자기교정 루프

    return g.compile()


_COMPILED = None


def get_graph():
    """컴파일된 그래프를 재사용한다(매 호출마다 다시 컴파일하지 않도록)."""
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def run_briefing_graph(all_dept_facts: dict, learned_rules: list,
                       branch_profile: dict, engine_index: dict) -> dict:
    """그래프를 실행하고 최종 브리핑 + 부문별 결과 + 검증 로그를 반환한다.

    반환 형태는 Phase 2의 generate_weekly_briefing()과 호환되도록 맞춘다
    (briefing dict에 dept_results / validation_log 를 얹어서 돌려준다).
    """
    final_state = get_graph().invoke({
        "all_dept_facts": all_dept_facts,
        "learned_rules": learned_rules,
        "branch_profile": branch_profile,
        "engine_index": engine_index,
        "dept_results": {},
        "pending_depts": [],
        "briefing_issues": [],
        "dept_retries": 0,
        "briefing_retries": 0,
        "validation_log": [],
    })

    briefing = dict(final_state.get("briefing") or {})
    briefing["dept_results"] = final_state.get("dept_results", {})
    briefing["validation_log"] = final_state.get("validation_log", [])
    return briefing
