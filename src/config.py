"""API 키 등 설정값 관리 — 키 조회 로직을 이 파일 한 곳으로 집중한다.

우선순위: 이미 설정된 환경변수(배포 환경) > 프로젝트 루트의 .env 파일(로컬 개발).
Streamlit Community Cloud는 대시보드 Secrets에 등록한 값을 환경변수로도 주입하므로,
로컬(.env)과 배포(Secrets) 모두 동일하게 os.environ 경로로 읽힌다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# override=False: 배포 환경에서 이미 주입된 환경변수를 .env가 덮어쓰지 않도록 한다.
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def get_openai_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return key or None


def has_openai_api_key() -> bool:
    return get_openai_api_key() is not None
