"""
피드백 로그 저장소 + 지점 특화 진화 메커니즘 (보고서 기능3).

동작 방식:
  1) 지점장이 AI 제안을 [수용/보류] 하고 사유 태그를 남기면 로그에 누적된다.
  2) 동일 (부문, 사유) 조합이 임계치(RULE_THRESHOLD) 이상 누적되면
     '지점 고유 규칙'으로 승격되어 해당 부문 지표의 추천 가중치를 낮춘다(R3: ×0.3).
  3) 다음 주간 브리핑 생성 시 이 규칙이 LLM 프롬프트에 주입되어,
     실현 가능성이 낮은 지표 대신 우회 전략을 제안하도록 유도한다.

Streamlit 세션 상태에 저장하며, 앱 재시작 시 data_generator의 시드 데이터로 복원된다.
"""

RULE_THRESHOLD = 3
DEPRIORITIZE_WEIGHT = 0.3


def add_feedback(log: list[dict], entry: dict) -> list[dict]:
    return log + [entry]


def derive_rules(log: list[dict]) -> list[dict]:
    """(부문, 사유) 조합별 보류 횟수를 집계하고, 임계치 이상인 것만 '학습된 규칙'으로 반환."""
    tally: dict[tuple, int] = {}
    for entry in log:
        if entry.get("decision") != "보류":
            continue
        key = (entry["dept"], entry["reason"])
        tally[key] = tally.get(key, 0) + 1

    rules = []
    for (dept, reason), count in tally.items():
        if count >= RULE_THRESHOLD:
            rules.append({
                "dept": dept,
                "reason": reason,
                "count": count,
                "weight_multiplier": DEPRIORITIZE_WEIGHT,
                "rule_text": f"'{dept}' 지표 중 '{reason}' 사유로 {count}회 이상 보류됨 → "
                             f"해당 부문 지표의 추천 가중치를 {DEPRIORITIZE_WEIGHT}배로 하향 조정",
            })
    return rules


def apply_rules(computed_indicators: list[dict], rules: list[dict]) -> list[dict]:
    """규칙을 반영해 지표별 adjusted_roi(추천 우선순위용 조정 ROI)를 계산한다.
    원본 roi(연산엔진 산출값)는 그대로 두고, 별도 필드에만 가중치를 적용해
    '숫자는 엔진이, 우선순위 판단은 규칙+AI가' 원칙을 지킨다."""
    dept_multiplier = {r["dept"]: r["weight_multiplier"] for r in rules}
    out = []
    for ind in computed_indicators:
        mult = dept_multiplier.get(ind["dept"], 1.0)
        adjusted = dict(ind)
        adjusted["adjusted_roi"] = round(ind["roi"] * mult, 4)
        adjusted["deprioritized"] = mult < 1.0
        out.append(adjusted)
    return out
