from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

# 1. FastAPI 앱 생성
app = FastAPI(
    title="소상공인 정부정책 지원금 API",
    description="AI가 직접 읽고 활용할 수 있는 정부정책 데이터 API",
    version="1.0.0"
)

# 2. 데이터 구조 정의 (AI가 인식하기 쉬운 표준 규격)
class PolicySupport(BaseModel):
    policy_id: str = Field(..., description="정책 고유 번호", example="POL-2026-001")
    name: str = Field(..., description="정책명", example="2026 소상공인 이자환급 지원")
    provider: str = Field(..., description="주관 기관", example="중소벤처기업부")
    target_industry: List[str] = Field(..., description="지원 대상 업종", example=["FNB"])
    max_amount_krw: int = Field(..., description="최대 지원 한도(원)", example=50000000)
    application_end_date: date = Field(..., description="신청 마감일", example="2026-12-31")
    is_active: bool = Field(..., description="현재 신청 가능 여부", example=True)

# 3. 테스트용 정부정책 데이터
MOCK_POLICIES = [
    {
        "policy_id": "POL-2026-001",
        "name": "FNB 음식업 소상공인 초저금리 대환대출",
        "provider": "소상공인시장진흥공단",
        "target_industry": ["FNB"],
        "max_amount_krw": 50000000,
        "application_end_date": "2026-12-31",
        "is_active": True,
    },
    {
        "policy_id": "POL-2026-002",
        "name": "영세 소상공인 임대료 특별지원",
        "provider": "서울특별시",
        "target_industry": ["FNB", "RETAIL"],
        "max_amount_krw": 2000000,
        "application_end_date": "2026-09-30",
        "is_active": True,
    }
]

# 4. API 화면 접속 테스트용
@app.get("/")
def home():
    return {"status": "ok", "message": "정부정책 API 서버가 작동 중입니다!"}

# 5. 정책 데이터 조회 API (JSON 반환)
@app.get("/api/v1/policies", response_model=List[PolicySupport])
def get_policies(industry: Optional[str] = Query(None, description="업종 코드 (예: FNB)")):
    """
    AI 및 사용자가 호출해서 사용할 수 있는 정책 목록 API
    """
    if industry:
        return [p for p in MOCK_POLICIES if industry.upper() in p["target_industry"]]
    return MOCK_POLICIES
    