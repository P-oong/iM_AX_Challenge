"""
이미지 자산 로딩 헬퍼 — assets/ 폴더에 정해진 파일명으로 이미지를 넣기만 하면
해당 위치에 자동으로 표시된다. 파일이 없으면 아무것도 표시하지 않으므로(오류 없음),
이미지 없이도 앱은 그대로 동작한다.

지원하는 슬롯 (파일명 → 표시 위치):
  assets/logo.png             → 사이드바 최상단 (모든 페이지 공통)
  assets/hero.png             → 홈(app.py) 상단 배너
  assets/briefing_banner.png  → ① 주간 전략 브리핑 페이지 상단 배너
  assets/background.png       → 앱 전체 배경 (반투명 오버레이로 가독성 유지)

png 외에 jpg/jpeg/webp 도 같은 이름이면 인식한다. (예: hero.jpg)
"""
import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def _find(stem: str) -> Path | None:
    """assets/<stem>.<확장자> 중 존재하는 첫 파일을 찾는다."""
    for ext in _EXTENSIONS:
        p = ASSETS_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def show_banner(stem: str) -> bool:
    """배너 이미지를 전체 폭으로 표시한다. 파일이 없으면 False를 반환하고 아무것도 안 한다."""
    path = _find(stem)
    if path is None:
        return False
    st.image(str(path), width="stretch")
    return True


def sidebar_logo() -> bool:
    """사이드바 상단에 로고를 표시한다."""
    path = _find("logo")
    if path is None:
        return False
    st.sidebar.image(str(path), width="stretch")
    return True


def apply_background() -> bool:
    """assets/background.* 가 있으면 앱 전체 배경으로 깐다.
    글자 가독성을 위해 흰색 반투명 오버레이를 함께 적용한다."""
    path = _find("background")
    if path is None:
        return False
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else path.suffix.lstrip(".").lower()
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background:
                linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.90)),
                url("data:image/{mime};base64,{b64}") center / cover fixed no-repeat;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return True
