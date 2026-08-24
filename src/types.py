# 연구에서 사용하는 데이터 type 정의

# ============================================================
# 타입 힌트 오류 줄이기 위한 안전장치
from __future__ import annotations
# 데이터 묶음을 클래스 형태로 만들 때 사용
from dataclasses import dataclass, field, asdict
# 변수에 어떤 자료형이 들어가는지 표시하는 타입 힌트
from typing import Dict, List, Any
# ============================================================


# ============================================================
# 1. Buyer가 SKU 하나에 대해 제출하는 주문 정보
# ============================================================
@dataclass
class BuyerItem: 
    # 구매자 b가 특정 SKU k에 대해 제출하는 주문 정보
    sku_id: str
    # 주문이 성립하기 위해 필요한 최소 수량
    min_qty: float
    # 구매자가 받을 수 있는 최대 수량
    max_qty: float
    # 해당 SKU 1단위에 대한 최대 지불의사금액(Willingness To Pay)
    wtp: float

# ============================================================
# 2. Buyer 정보
# ============================================================
@dataclass
class Buyer: 
    buyer_id: str
    # 구매자가 주문한 SKU별 정보. key는 sku_id, value는 BuyerItem
    items: Dict[str, BuyerItem]
    # 단일 허브 > 구매자 플랫폼 예상 배송비 c_b
    delivery_cost: float=0.0
    # 과거 매칭이력 h_b
    match_history: float=0.0

    # buyer.items.keys() 대신 buyer.sku_ids로 변수처럼 쓸 수 있음
    @property
    def sku_ids(self) -> List[str]:
        # 구매자가 주문한 SKU 목록
        return list(self.items.keys())

    
# ============================================================
# 3. Seller가 SKU 하나에 대해 제출하는 공급 정보
# ============================================================
@dataclass
class SellerItem:
    sku_id: str
    # 해당 SKU의 최대 공급 가능 수량 C_sk
    capacity: float
    # 해당 SKU 1단위에 대해 공급자가 요구하는 최소 가격(Willingness To Accept). 본 연구에서는 허브 도착가격으로 해석. 
    wta: float

# ============================================================
# 4. Seller
# ============================================================
@dataclass
class Seller:
    seller_id: str
    items: Dict[str, SellerItem]
    # 과거 매칭이력 h_s
    match_history: float = 0.0

    @property
    def sku_ids(self) -> List[str]:
        # 공급자가 공급 가능한 SKU 목록
        return list(self.items.keys())


# ============================================================
# 5. MILP에 입력되는 하나의 시장 인스턴스
# ============================================================
@dataclass
class Instance: 
    instance_id: str
    # 전체 SKU 집합 K
    sku_ids: List[str]
    buyers: Dict[str, Buyer]
    sellers: Dict[str, Seller]

    # 임의 데이터 생성 시 사용한 random seed
    seed: int = 0
    # 현재 기간. 단일기간 실험에서는 기본값 1
    period: int = 1

    @property
    def buyer_ids(self) -> List[str]:
        return list(self.buyers.keys())

    @property
    def seller_ids(self) -> List[str]:
        return list(self.sellers.keys())

    @property
    def num_buyers(self) -> int:
        return len(self.buyers)

    @property
    def num_sellers(self) -> int:
        return len(self.sellers)

    @property
    def num_skus(self) -> int:
        return len(self.sku_ids)

    # JSON 저장에 사용할 수 있도록 dataclass를 일반 dictionary로 변환
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# 6. MILP Solution (단일기간 MILP 결과를 저장)
# ============================================================

@dataclass
class MILPSolution:
    # status: OPTIMAL, INFEASIBLE, TIME_LIMIT 등
    status: str

    # 플랫폼 당기 순이윤 pi_t
    objective_value: float = 0.0
    platform_profit: float = 0.0

    # y_b 결과.buyer_id -> 0 또는 1 
    accepted_buyers: Dict[str, int] = field(default_factory=dict)
    # z_s 결과. seller_id -> 0 또는 1
    selected_sellers: Dict[str, int] = field(default_factory=dict)


    # x_bsk 결과. key:(buyer_id, seller_id, sku_id), value: 해당 거래의 배정 수량
    allocation: Dict[tuple[str, str, str], float] = field(
        default_factory=dict
    )

    buyer_surplus: Dict[str, float] = field(default_factory=dict)
    seller_surplus: Dict[str, float] = field(default_factory=dict)

    solve_time: float = 0.0