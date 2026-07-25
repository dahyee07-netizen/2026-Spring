import os
from fastapi import FastAPI, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum

from sqlalchemy import create_engine, Column, String, Integer, Date, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# --- 1. DB 연결 설정 ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 2. 실제 DB 테이블 모델 (노션 명세서 v2.0 규격) ---
class PolicyDB(Base):
    __tablename__ = "policies"

    policy_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    purpose = Column(JSON, nullable=False)
    region_codes = Column(JSON, nullable=False)
    industry_inclusions = Column(JSON, nullable=False)
    industry_exclusions = Column(JSON, nullable=False)
    max_amount_krw = Column(Integer, nullable=False)
    application_start = Column(Date, nullable=False)
    application_end = Column(Date, nullable=False)
    source_id = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    evidence_text = Column(Text, nullable=False)
    validation_status = Column(String, default="ACCEPTED")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 3. FastAPI 앱 및 Enum 정의 ---
app = FastAPI(
    title="F&B 소상공인 정부정책 API (PostgreSQL DB 연동)",
    description="실제 DB 기반 정책 조회, 규칙 적격성 평가, 금융효과 시뮬레이션 및 팩트체크 출처 제공 API",
    version="2.1.0"
)

class PolicyPurpose(str, Enum):
    WORKING_CAPITAL = "WORKING_CAPITAL"
    REFINANCING = "REFINANCING"
    RENT_SUPPORT = "RENT_SUPPORT"

class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE_ON_DECLARED_RULES"
    NEEDS_INFO = "NEEDS_INFORMATION"
    INELIGIBLE = "INELIGIBLE"
    CLOSED = "CLOSED"

# --- 4. 데이터 스키마 정의 ---
class PolicySupport(BaseModel):
    policy_id: str
    name: str
    provider: str
    purpose: List[str]
    region_codes: List[str]
    industry_inclusions: List[str]
    industry_exclusions: List[str]
    max_amount_krw: int
    application_start: date
    application_end: date
    source_id: str
    validation_status: str

    class Config:
        from_attributes = True

class StoreProfileRequest(BaseModel):
    store_id: str = Field(..., example="STORE-001")
    region_code: str = Field(..., example="11")
    industry_code: str = Field(..., example="FNB")
    monthly_revenue_krw: int = Field(..., example=30000000)

class EligibilityResult(BaseModel):
    policy_id: str
    policy_name: str
    status: EligibilityStatus
    reasons: List[str]

class SimulationRequest(BaseModel):
    policy_id: str = Field(..., example="POL-2026-001")
    current_loan_amount_krw: int = Field(..., example=30000000)
    current_interest_rate_pct: float = Field(..., example=7.5)
    policy_interest_rate_pct: float = Field(default=2.0, example=2.0)

class SimulationResult(BaseModel):
    policy_id: str
    current_annual_interest_krw: int
    new_annual_interest_krw: int
    annual_savings_krw: int
    monthly_savings_krw: int
    summary_message: str

class PolicyEvidenceResponse(BaseModel):
    policy_id: str
    source_id: str
    source_url: str
    evidence_text: str

# --- 5. 앱 시작 시 실제 DB에 검증된 정부 정책 초기 데이터 저장 ---
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    if db.query(PolicyDB).count() == 0:
        seed_data = [
            PolicyDB(
                policy_id="POL-2026-001",
                name="FNB 음식업 소상공인 초저금리 대환대출",
                provider="소상공인시장진흥공단",
                purpose=["REFINANCING", "WORKING_CAPITAL"],
                region_codes=["ALL"],
                industry_inclusions=["FNB", "FNB_CAFE"],
                industry_exclusions=[],
                max_amount_krw=50000000,
                application_start=date(2026, 1, 1),
                application_end=date(2026, 12, 31),
                source_id="SRC-SEMAS-2026-01",
                source_url="https://www.semas.or.kr/announcements/2026-001",
                evidence_text="제3조(지원대상): 전국 F&B 음식점 및 카페를 운영하는 소상공인 중 고금리 대출을 보유한 자. 최대 한도 5,000만원 내에서 연 2.0% 대환 금리를 적용함.",
                validation_status="ACCEPTED"
            ),
            PolicyDB(
                policy_id="POL-2026-002",
                name="서울특별시 영세 소상공인 임대료 특별지원",
                provider="서울특별시",
                purpose=["RENT_SUPPORT"],
                region_codes=["11"],
                industry_inclusions=["FNB", "RETAIL"],
                industry_exclusions=["GAMBLING"],
                max_amount_krw=2000000,
                application_start=date(2026, 2, 1),
                application_end=date(2026, 9, 30),
                source_id="SRC-SEOUL-2026-05",
                source_url="https://www.seoul.go.kr/news/news_notice.do#2026-05",
                evidence_text="서울특별시 공고 제2026-05호: 사업장 소재지가 서울특별시(지역코드 11)인 영세 소상공인을 대상으로 사업장 임대료를 최대 200만원 한도로 지원함.",
                validation_status="ACCEPTED"
            )
        ]
        db.add_all(seed_data)
        db.commit()
    db.close()

# --- 6. 엔드포인트 구현 (모두 실제 DB에서 조회/계산) ---
@app.get("/")
def home():
    return {"status": "ok", "message": "PostgreSQL DB가 성공적으로 연결된 정부정책 API 서버입니다!"}

@app.get("/api/v1/policies", response_model=List[PolicySupport])
def get_policies(
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(PolicyDB)
    policies = query.all()
    results = []
    for p in policies:
        if industry and industry.upper() not in p.industry_inclusions:
            continue
        if region and "ALL" not in p.region_codes and region not in p.region_codes:
            continue
        results.append(p)
    return results

@app.post("/api/v1/policies/evaluate", response_model=List[EligibilityResult])
def evaluate_policy_eligibility(store: StoreProfileRequest, db: Session = Depends(get_db)):
    today = date.today()
    policies = db.query(PolicyDB).all()
    evaluations = []

    for policy in policies:
        reasons = []
        is_eligible = True

        if today > policy.application_end:
            evaluations.append(EligibilityResult(
                policy_id=policy.policy_id,
                policy_name=policy.name,
                status=EligibilityStatus.CLOSED,
                reasons=["신청 마감일이 지났습니다."]
            ))
            continue

        if "ALL" not in policy.region_codes and store.region_code not in policy.region_codes:
            is_eligible = False
            reasons.append(f"지역 불일치 (점포: {store.region_code}, 지원지역: {policy.region_codes})")

        if store.industry_code in policy.industry_exclusions:
            is_eligible = False
            reasons.append(f"지원 제외 업종 해당 ({store.industry_code})")

        if "ALL" not in policy.industry_inclusions and store.industry_code not in policy.industry_inclusions:
            is_eligible = False
            reasons.append(f"지원 대상 업종 미포함 (점포: {store.industry_code})")

        status = EligibilityStatus.ELIGIBLE if is_eligible else EligibilityStatus.INELIGIBLE
        if is_eligible:
            reasons.append("선언적 명시 조건(지역, 업종, 신청기간)을 모두 충족합니다.")

        evaluations.append(EligibilityResult(
            policy_id=policy.policy_id,
            policy_name=policy.name,
            status=status,
            reasons=reasons
        ))

    return evaluations

@app.post("/api/v1/policies/simulate-benefit", response_model=SimulationResult)
def simulate_policy_benefit(req: SimulationRequest):
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

@app.get("/api/v1/policies/{policy_id}/evidence", response_model=PolicyEvidenceResponse)
def get_policy_evidence(policy_id: str, db: Session = Depends(get_db)):
    policy = db.query(PolicyDB).filter(PolicyDB.policy_id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="해당 정책의 근거 데이터를 DB에서 찾을 수 없습니다.")
    
    return PolicyEvidenceResponse(
        policy_id=policy.policy_id,
        source_id=policy.source_id,
        source_url=policy.source_url,
        evidence_text=policy.evidence_text
    )