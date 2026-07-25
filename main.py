from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum

app = FastAPI(
    title="F&B 소상공인 정부정책 지원금 및 적격성 API",
    description="LLM 에이전트 및 결정형 시스템이 호출하여 정책 데이터를 조회하고, 선언적 규칙 기반 적격성 판정 및 지원 효과를 시뮬레이션하는 API",
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

# --- 2. 데이터 스키마 정의 (명세서 18.2 & 18.4) ---

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

# [명세서 18.4] 지원 효과 시뮬레이션 요청/응답 스키마
class SimulationRequest(BaseModel):
    policy_id: str = Field(..., description="적용하고자 하는 정책 ID", example="POL-2026-001")
    current_loan_amount_krw: int = Field(..., description="기존 대출 잔액(원)", example=30000000)
    current_interest_rate_pct: float = Field(..., description="기존 대출 금리(%)", example=7.5)
    policy_interest_rate_pct: float = Field(default=2.0, description="정책 지원 적용 우대 금리(%)", example=2.0)

class SimulationResult(BaseModel):
    policy_id: str
    current_annual_interest_krw: int = Field(..., description="기존 연간 이자 비용(원)")
    new_annual_interest_krw: int = Field(..., description="정책 적용 후 연간 이자 비용(원)")
    annual_savings_krw: int = Field(..., description="연간 절감액(원)")
    monthly_savings_krw: int = Field(..., description="월 절감액(원)")
    summary_message: str = Field(..., description="결과 요약 설명 문구")

# --- 3. Mock 정책 데이터 ---

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
        "region_codes": ["11"],
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
    results = MOCK_POLICIES
    if industry:
        results = [p for p in results if industry.upper() in p["industry_inclusions"]]
    if region:
        results = [p for p in results if "ALL" in p["region_codes"] or region in p["region_codes"]]
    return results

@app.post("/api/v1/policies/evaluate", response_model=List[EligibilityResult])
def evaluate_policy_eligibility(store: StoreProfileRequest):
    today = date.today()
    evaluations = []

    for policy in MOCK_POLICIES:
        reasons = []
        is_eligible = True

        end_date = date.fromisoformat(policy["application_end"])
        if today > end_date:
            evaluations.append(EligibilityResult(
                policy_id=policy["policy_id"],
                policy_name=policy["name"],
                status=EligibilityStatus.CLOSED,
                reasons=["신청 마감일이 지났습니다."]
            ))
            continue

        if "ALL" not in policy["region_codes"] and store.region_code not in policy["region_codes"]:
            is_eligible = False
            reasons.append(f"지역 불일치 (점포: {store.region_code}, 지원지역: {policy['region_codes']})")

        if store.industry_code in policy["industry_exclusions"]:
            is_eligible = False
            reasons.append(f"지원 제외 업종 해당 ({store.industry_code})")

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

@app.post("/api/v1/policies/simulate-benefit", response_model=SimulationResult)
def simulate_policy_benefit(req: SimulationRequest):
    """
    [명세서 18.4] 정책 적용 시 기존 대출 대비 금융비용 절감액을 수치적으로 시뮬레이션합니다.
    """
    current_annual_interest = int(req.current_loan_amount_krw * (req.current_interest_rate_pct / 100))
    new_annual_interest = int(req.current_loan_amount_krw * (req.policy_interest_rate_pct / 100))
    annual_savings = current_annual_interest - new_annual_interest
    monthly_savings = int(annual_savings / 12)

    return SimulationResult(
        policy_id=req.policy_id,
        current_annual_interest_krw=current_annual_interest,
        new_annual_interest_krw=new_annual_interest,
        annual_savings_krw=annual_savings,
        monthly_savings_krw=monthly_savings,
        summary_message=f"정책 적용 시 연간 약 {annual_savings:,}원(월 약 {monthly_savings:,}원)의 이자 비용이 절감됩니다."
    )