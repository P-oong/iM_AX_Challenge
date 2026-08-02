"""
결정론적 연산 엔진 — 보고서의 설계 원칙 "판단은 AI가, 계산은 엔진이"를 구현하는 핵심 모듈.

LLM은 이 모듈이 계산한 숫자를 '해석/브리핑'만 할 뿐, 점수 자체는 절대 재계산하지 않는다.
(app 어디에서도 LLM에게 최종 점수를 산출하게 시키지 않는다.)

각 지표에 대해 계산하는 값:
  - current_score   : 계단식 구간표에서 현재 실적으로 도달한 누적 점수
  - max_score        : 지표 만점
  - is_maxed         : 상한(만점) 도달 여부 → "영업중단 권고" 대상
  - next_hurdle       : 다음 구간까지 남은 목표
  - gap              : 다음 구간까지 필요한 잔여 실적
  - score_gain       : 다음 구간 통과 시 추가로 얻는 점수
  - roi              : 1건(1백만원)당 점수 상승분 — '가성비' 판단 기준
  - is_feasible      : 잔여기간 × 일평균 처리량으로 물리적 달성 가능 여부 (SOP 규칙 R2)
  - attainment_pct   : 만점 대비 현재 달성률(%)
  - category         : 상한도달 / 가성비 / 사각지대 / 진행 (히트맵 색상 분류)
"""

TOP_ROI_COUNT = 3  # '가성비 지표'로 분류할 상위 ROI 지표 개수


def _compute_single(ind: dict) -> dict:
    hurdles = sorted(ind["hurdles"], key=lambda h: h["threshold"])
    current_value = ind["current_value"]

    current_score = 0
    for h in hurdles:
        if current_value >= h["threshold"]:
            current_score = h["score"]

    max_score = hurdles[-1]["score"]
    is_maxed = current_value >= hurdles[-1]["threshold"]

    next_hurdle = None
    for h in hurdles:
        if current_value < h["threshold"]:
            next_hurdle = h
            break

    if next_hurdle:
        gap = round(next_hurdle["threshold"] - current_value, 1)
        score_gain = next_hurdle["score"] - current_score
        roi = round(score_gain / gap, 4) if gap > 0 else 0.0
    else:
        gap, score_gain, roi = 0.0, 0, 0.0

    daily_rate = ind.get("daily_rate", 0) or 0.001
    remaining_days = ind.get("remaining_days", 0)
    is_feasible = is_maxed or (gap <= daily_rate * remaining_days)

    attainment_pct = round(min(current_value / hurdles[-1]["threshold"], 1.5) * 100, 1)

    out = dict(ind)
    out.update({
        "current_score": current_score,
        "max_score": max_score,
        "is_maxed": is_maxed,
        "next_hurdle": next_hurdle,
        "gap": gap,
        "score_gain": score_gain,
        "roi": roi,
        "is_feasible": is_feasible,
        "attainment_pct": attainment_pct,
    })
    return out


def compute_all(indicators: list[dict]) -> list[dict]:
    """지표 리스트 전체에 대해 점수/ROI/카테고리를 계산한다."""
    computed = [_compute_single(ind) for ind in indicators]

    # ROI 상위 N개(상한 미도달 + 물리적으로 달성 가능한 지표 중에서) → '가성비'로 분류
    candidates = [c for c in computed if not c["is_maxed"] and c["is_feasible"] and c["roi"] > 0]
    top_roi_ids = {c["id"] for c in sorted(candidates, key=lambda c: c["roi"], reverse=True)[:TOP_ROI_COUNT]}

    for c in computed:
        if c["is_maxed"]:
            c["category"] = "상한도달"
        elif c["id"] in top_roi_ids:
            c["category"] = "가성비"
        elif c.get("is_micro") and 35 <= c["attainment_pct"] <= 80:
            c["category"] = "사각지대"
        else:
            c["category"] = "진행"

    return computed


def total_score(computed_indicators: list[dict]) -> dict:
    cur = sum(c["current_score"] for c in computed_indicators)
    mx = sum(c["max_score"] for c in computed_indicators)
    return {"current": cur, "max": mx, "pct": round(cur / mx * 100, 1) if mx else 0.0}


def simulate_addition(computed_indicators: list[dict], indicator_id: str, added_amount: float) -> list[dict]:
    """시뮬레이터: 특정 지표에 실적을 added_amount만큼 추가했을 때 재계산한 결과를 반환."""
    updated_raw = []
    for c in computed_indicators:
        raw = {k: v for k, v in c.items()
               if k not in ("current_score", "max_score", "is_maxed", "next_hurdle",
                            "gap", "score_gain", "roi", "is_feasible", "attainment_pct", "category")}
        if raw["id"] == indicator_id:
            raw["current_value"] = raw["current_value"] + added_amount
        updated_raw.append(raw)
    return compute_all(updated_raw)
