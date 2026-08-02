"""
Validator — 보고서 4-2-(4) '자기교정(Self-correction) 루프'의 검증 로직.

에이전트 출력이 SOP 규칙을 지켰는지 검사한다. 여기서 중요한 설계 결정:
**검증은 100% 결정론적 Python으로 수행한다. LLM을 쓰지 않는다.**
수치가 맞는지를 다시 LLM에게 묻는 것은 '계산은 엔진이' 원칙을 스스로 무너뜨리는
일이기 때문이다. 엔진이 계산한 원본 값과 에이전트가 인용한 값을 직접 대조한다.

검사 항목 (부문 에이전트):
  V1. 존재하지 않는 지표를 추천했는가 (환각)
  V2. 다른 부문 지표를 추천했는가 (부문 월경)
  V3. 이미 상한 도달한 지표를 추천했는가 (SOP R1 위반)
  V4. 잔여기간 내 달성 불가능한 지표를 추천했는가 (SOP R2 위반)
  V5. 인용한 수치가 엔진 계산값과 다른가 (SOP R4/R5 위반 — 수치 환각)
  V6. 영업중단 권고가 실제 상한도달 지표가 아닌가 (허위 권고)
  V7. 규정 근거(caution)가 비어 있는가

검사 항목 (Supervisor 최종 브리핑):
  B1. 존재하지 않는 지표를 카드로 냈는가
  B2. 부문 에이전트가 올리지 않은 지표를 임의로 골랐는가 (SOP R1 위반)
  B3. 카드가 한 부문에만 편중되었는가 (SOP R2 위반)
"""

# 수치 대조 시 허용 오차 — 엔진이 소수 1자리로 반올림하므로 그보다 작게 잡는다.
NUMERIC_TOLERANCE = 0.051


def build_engine_index(computed_indicators: list[dict]) -> dict[str, dict]:
    """지표명 → 엔진 계산값 인덱스. Validator가 대조할 '정답' 역할을 한다."""
    return {
        ind["name"]: {
            "dept": ind["dept"],
            "current_value": ind["current_value"],
            "gap": ind["gap"],
            "score_gain": ind["score_gain"],
            "is_maxed": ind["is_maxed"],
            "is_feasible": ind["is_feasible"],
        }
        for ind in computed_indicators
    }


def _mismatch(cited, actual) -> bool:
    try:
        return abs(float(cited) - float(actual)) > NUMERIC_TOLERANCE
    except (TypeError, ValueError):
        return True


def validate_dept_result(dept: str, result: dict, engine_index: dict[str, dict]) -> list[str]:
    """한 부문 에이전트의 결과를 검증한다. 문제가 없으면 빈 리스트를 반환."""
    issues: list[str] = []

    for rec in result.get("recommendations", []):
        name = rec.get("indicator_name", "")
        engine = engine_index.get(name)

        if engine is None:
            issues.append(f"[{dept}] V1 존재하지 않는 지표를 추천: '{name}'")
            continue

        if engine["dept"] != dept:
            issues.append(f"[{dept}] V2 다른 부문({engine['dept']}) 지표를 추천: '{name}'")

        if engine["is_maxed"]:
            issues.append(f"[{dept}] V3 이미 상한 도달한 지표를 추천: '{name}'")

        if not engine["is_feasible"]:
            issues.append(f"[{dept}] V4 잔여기간 내 달성 불가능한 지표를 추천: '{name}'")

        for field, engine_key, label in (
            ("cited_current_value", "current_value", "현재실적"),
            ("cited_gap", "gap", "필요실적"),
            ("cited_score_gain", "score_gain", "추가점수"),
        ):
            if field not in rec:
                continue
            if _mismatch(rec[field], engine[engine_key]):
                issues.append(
                    f"[{dept}] V5 수치 불일치 '{name}' {label}: "
                    f"에이전트={rec[field]} / 엔진={engine[engine_key]}"
                )

        if not (rec.get("caution") or "").strip():
            issues.append(f"[{dept}] V7 규정 근거(caution) 누락: '{name}'")

    for name in result.get("stop_recommendations", []):
        engine = engine_index.get(name)
        if engine is None:
            issues.append(f"[{dept}] V6 존재하지 않는 지표에 영업중단 권고: '{name}'")
        elif not engine["is_maxed"]:
            issues.append(f"[{dept}] V6 상한 미도달 지표에 영업중단 권고: '{name}'")

    return issues


def validate_all_dept_results(dept_results: dict[str, dict],
                              engine_index: dict[str, dict]) -> dict[str, list[str]]:
    """부문별 검증 결과를 {부문: [문제, ...]} 형태로 반환. 문제 없는 부문은 제외한다."""
    out = {}
    for dept, result in dept_results.items():
        issues = validate_dept_result(dept, result, engine_index)
        if issues:
            out[dept] = issues
    return out


def validate_briefing(briefing: dict, dept_results: dict[str, dict],
                      engine_index: dict[str, dict]) -> list[str]:
    """Supervisor가 낸 최종 브리핑을 검증한다."""
    issues: list[str] = []

    # 부문 에이전트가 올린 안건 목록 (Supervisor는 이 안에서만 골라야 한다)
    proposed = {
        rec["indicator_name"]
        for result in dept_results.values()
        for rec in result.get("recommendations", [])
    }

    card_depts = []
    for card in briefing.get("cards", []):
        name = card.get("indicator_name", "")
        engine = engine_index.get(name)

        if engine is None:
            issues.append(f"[Supervisor] B1 존재하지 않는 지표를 과제로 선정: '{name}'")
            continue

        card_depts.append(engine["dept"])
        if name not in proposed:
            issues.append(f"[Supervisor] B2 부문 에이전트가 올리지 않은 지표를 임의 선정: '{name}'")

    if len(card_depts) >= 3 and len(set(card_depts)) == 1:
        issues.append(f"[Supervisor] B3 3대 과제가 '{card_depts[0]}' 부문에만 편중됨")

    return issues
