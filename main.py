from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum

app = FastAPI(
    title="F&B 소상공인 정부정책 지원금 및 적격성 API",
    description="LLM 에이전트 및 결정형 시스템이 호출하여 정책 데이터를 조회하고, 선언적 규칙 기반 적격성을 판정하는 API",
    version="2.0.0"
)

# --- 1. ENUM 정의 (명세서 18.2 & 18.3) ---

class PolicyPurpose(str, Enum):
    WORKING_CAPITAL = "WORKING_CAPITAL"  # 운전자금
    REFINANCING = "REFINANCING"          # 대환대출
    RENT_SUPPORT = "RENT_SUPPORT"        # 임대료 지원

class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE_ON_DECLARED_RULES"  # 규칙 충족
    NEEDS_INFO = "NEEDS_INFORMATION"          # 정보 부족
    INELIGIBLE = "INELIGIBLE"                # 부적격
    CLOSED = "CLOSED"                        # 신청 마감

# --- 2. 데이터 스키마 정의 (명세서 18.2) ---

class PolicySupport(BaseModel):
    policy_id: str = Field(..., description="정책 고유 번호", example="POL-2026-001")
    name: str = Field(..., description="정책명", example="2026 소상공인 이자환급 지원")
    provider: str = Field(..., description="주관 기관", example="소상공인시장진흥공단")
    purpose: List[PolicyPurpose] = Field(..., description="지원 목적 목록")
    region_codes: List[str] = Field(..., description="지원 지역 코드 목록 (11: 서울, ALL: 전국)", example=["11", "ALL"])
    industry_inclusions: List[str] = Field(..., description="지원 대상 업종 코드", example=["FNB", "FNB_CAFE"])
    industry_exclusions: List[str] = Field(default=[], description="지원 제외 업종 코드")
    max_amount_krw: int = Field(..., description="최대 지원 한도(원)", example=50000000)
    application_start: date = Field(..., description="신청 시작일", example="2026-01-01")
    application_end: date = Field(..., description="신청 마감일", example="2026-12-31")
    source_id: str = Field(..., description="원문 출처 식별자", example="SRC-POLICY-2026-01")
    validation_status: str = Field(default="ACCEPTED", description="검증 상태 (ACCEPTED, EXTRACTED 등)")

class StoreProfileRequest(BaseModel):
    store_id: str = Field(..., description="점포 고유 ID", example="STORE-001")
    region_code: str = Field(..., description="점포 소재지 지역코드 (예: 11=서울, 41=경기)", example="11")
    industry_code: str = Field(..., description="점포 업종 코드", example="FNB")
    monthly_revenue_krw: int = Field(..., description="월 매출(원)", example=30000000)

class EligibilityResult(BaseModel):
    policy_id: str
    policy_name: str
    status: EligibilityStatus
    reasons: List[str] = Field(..., description="판정 사유 상세 목록")

# --- 3. Mock 정책 데이터 (명세서 규격 적용) ---

MOCK_POLICIES: List[dict] = [
    {
        "policy_id": "POL-2026-001",
        "name": "FNB 음식업 소상공인 초저금리 대환대출",
        "provider": "소상공인시장진흥공단",
        "purpose": [PolicyPurpose.REFINANCING, PolicyPurpose.WORKING_CAPITAL],
        "region_codes": ["ALL"],
        "industry_inclusions": ["FNB", "FNB_CAFE"],
        "industry_exclusions": [],
        "max_amount_krw": 50000000,
        "application_start": "2026-01-01",
        "application_end": "2026-12-31",
        "source_id": "SRC-SEMAS-2026-01",
        "validation_status": "ACCEPTED"
    },
    {
        "policy_id": "POL-2026-002",
        "name": "서울특별시 영세 소상공인 임대료 특별지원",
        "provider": "서울특별시",
        "purpose": [PolicyPurpose.RENT_SUPPORT],
        "region_codes": ["11"],  # 서울 전용
        "industry_inclusions": ["FNB", "RETAIL"],
        "industry_exclusions": ["GAMBLING"],
        "max_amount_krw": 2000000,
        "application_start": "2026-02-01",
        "application_end": "2026-09-30",
        "source_id": "SRC-SEOUL-2026-05",
        "validation_status": "ACCEPTED"
    }
]

# --- 4. 엔드포인트 구현 ---

@app.get("/")
def home():
    return {"status": "ok", "message": "정부정책 및 적격성 평가 API 서버가 정상 동작 중입니다!"}

@app.get("/api/v1/policies", response_model=List[PolicySupport])
def get_policies(
    industry: Optional[str] = Query(None, description="업종 코드 (예: FNB)"),
    region: Optional[str] = Query(None, description="지역 코드 (예: 11=서울)")
):
    """
    AI 및 결정형 시스템이 정책 지원금 전체 목록을 검색/조회합니다.
    """
    results = MOCK_POLICIES
    if industry:
        results = [p for p in results if industry.upper() in p["industry_inclusions"]]
    if region:
        results = [p for p in results if "ALL" in p["region_codes"] or region in p["region_codes"]]
    return results

@app.post("/api/v1/policies/evaluate", response_model=List[EligibilityResult])
def evaluate_policy_eligibility(store: StoreProfileRequest):
    """
    [명세서 18.3] 점포 프로파일을 입력받아 정책별 적격성을 선언적 규칙 기반으로 결정론적으로 판정합니다.
    """
    today = date.today()
    evaluations = []

    for policy in MOCK_POLICIES:
        reasons = []
        is_eligible = True

        # 규칙 1. 마감 여부 점검
        end_date = date.fromisoformat(policy["application_end"])
        if today > end_date:
            evaluations.append(EligibilityResult(
                policy_id=policy["policy_id"],
                policy_name=policy["name"],
                status=EligibilityStatus.CLOSED,
                reasons=["신청 마감일이 지났습니다."]
            ))
            continue

        # 규칙 2. 지역 일치 여부 점검
        if "ALL" not in policy["region_codes"] and store.region_code not in policy["region_codes"]:
            is_eligible = False
            reasons.append(f"지역 불일치 (점포: {store.region_code}, 지원지역: {policy['region_codes']})")

        # 규칙 3. 제외 업종 점검
        if store.industry_code in policy["industry_exclusions"]:
            is_eligible = False
            reasons.append(f"지원 제외 업종 해당 ({store.industry_code})")

        # 규칙 4. 포함 업종 점검
        if "ALL" not in policy["industry_inclusions"] and store.industry_code not in policy["industry_inclusions"]:
            is_eligible = False
            reasons.append(f"지원 대상 업종 미포함 (점포: {store.industry_code})")

        status = EligibilityStatus.ELIGIBLE if is_eligible else EligibilityStatus.INELIGIBLE
        if is_eligible:
            reasons.append("선언적 명시 조건(지역, 업종, 신청기간)을 모두 충족합니다.")

        evaluations.append(EligibilityResult(
            policy_id=policy["policy_id"],
            policy_name=policy["name"],
            status=status,
            reasons=reasons
        ))

    return evaluations