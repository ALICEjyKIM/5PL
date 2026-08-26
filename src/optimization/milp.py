"""공급자 중심 5PL 매칭 연구의 단일기간 MILP.

이 모듈은 향후 다기간 시뮬레이터에서 반복 호출할 당기 의사결정 모형이다.
주문 수락, 물량 배정, 거래 공급자 선택, 공급자 잉여배분 및 플랫폼
순이윤을 동시에 결정한다.

현재 기본 목적함수는 당기 플랫폼 순이윤을 최대화하는 Myopic 정책이다.
따라서 ADP 미래가치가 연결되기 전에는 공급자 잉여배분 v가 일반적으로
0이 된다. 이는 오류가 아니라 미래를 고려하지 않는 비교 기준의 결과다.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import gurobipy as gp
from gurobipy import GRB

from src.types import Instance, MILPSolution


AllocationKey = Tuple[str, str, str]


def solve_milp(
    instance: Instance,
    output_flag: bool = True,
    *,
    allocation_epsilon: float = 1e-6,
    time_limit: Optional[float] = None,
    mip_gap: Optional[float] = None,
) -> MILPSolution:
    """공급자 중심 5PL 매칭 문제의 한 기간을 최적화한다.

    결정변수
    --------
    x[b,s,k] : 공급자 s가 구매자 b에게 공급하는 품목 k의 수량
    y[b]     : 구매자 b의 다품종 주문 수락 여부
    z[s]     : 공급자 s의 당기 실제 거래 여부
    v[s]     : 당기 거래잉여 중 공급자 s에게 배분하는 금액
    pi       : 플랫폼의 당기 순이윤

    주요 가정
    ---------
    * 구매자 WTP가 공급자 WTA 이상인 조합만 거래 후보로 만든다.
    * 구매자가 요구한 모든 품목의 최소·최대 수량 조건을 만족해야
      해당 다품종 주문을 수락할 수 있다.
    * 거래잉여는 플랫폼 전체의 공동 재원으로 사용하므로 실제 거래한
      공급자 사이의 교차보조를 허용한다.
    * 공급자 참여확률과 ADP 미래가치는 이후 상태전이·가치함수 모듈에서
      연결하며, 이 함수는 당기 의사결정만 담당한다.
    """

    if allocation_epsilon <= 0:
        raise ValueError("allocation_epsilon은 0보다 커야 합니다.")

    buyers = instance.buyer_ids
    sellers = instance.seller_ids
    skus = instance.sku_ids

    # ------------------------------------------------------------
    # 1. 거래 가능한 (구매자, 공급자, 품목) 조합 생성
    # ------------------------------------------------------------
    # 현재 거래에서 단위당 잉여가 음수인 WTP < WTA 조합은 처음부터
    # 제외한다. 이 필터는 손실 거래를 미래가치로 보전하는 해를 막는다.
    valid_triples: list[AllocationKey] = []
    unit_surplus: Dict[AllocationKey, float] = {}

    for b in buyers:
        buyer = instance.buyers[b]
        for s in sellers:
            seller = instance.sellers[s]
            for k in skus:
                if k not in buyer.items or k not in seller.items:
                    continue

                surplus = float(buyer.items[k].wtp - seller.items[k].wta)
                if surplus >= 0.0:
                    key = (b, s, k)
                    valid_triples.append(key)
                    unit_surplus[key] = surplus

    valid_triple_set = set(valid_triples)

    model = gp.Model(f"5PL_single_period_{instance.instance_id}")
    model.Params.OutputFlag = 1 if output_flag else 0
    if time_limit is not None:
        model.Params.TimeLimit = float(time_limit)
    if mip_gap is not None:
        model.Params.MIPGap = float(mip_gap)

    # ------------------------------------------------------------
    # 2. 결정변수
    # ------------------------------------------------------------
    # 동일 품목을 여러 공급자에게 분할 조달할 수 있으므로 x는 연속변수다.
    x = model.addVars(
        valid_triples,
        lb=0.0,
        vtype=GRB.CONTINUOUS,
        name="x",
    )
    y = model.addVars(buyers, vtype=GRB.BINARY, name="y")
    z = model.addVars(sellers, vtype=GRB.BINARY, name="z")

    # ------------------------------------------------------------
    # 3. 잉여배분 변수의 Big-M 계산
    # ------------------------------------------------------------
    # 가능한 거래잉여를 다소 크게 추정한 안전한 상한이다. 실제 목적값을
    # 계산하는 값이 아니라 거래 여부 z와 잉여배분 v를 연결하는 M으로만 쓴다.
    surplus_big_m = sum(
        unit_surplus[b, s, k]
        * min(
            float(instance.buyers[b].items[k].max_qty),
            float(instance.sellers[s].items[k].capacity),
        )
        for b, s, k in valid_triples
    )
    surplus_big_m = max(0.0, float(surplus_big_m))

    # v[s]는 공급자의 기본 WTA 지급액과 별도로 당기 거래잉여에서
    # 공급자에게 추가 배분하는 금액이다.
    v = model.addVars(
        sellers,
        lb=0.0,
        ub=surplus_big_m,
        vtype=GRB.CONTINUOUS,
        name="v",
    )

    # pi의 하한을 0으로 두어 플랫폼의 당기 적자를 허용하지 않는다.
    pi = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="pi")

    gross_trade_surplus = gp.quicksum(
        unit_surplus[b, s, k] * x[b, s, k]
        for b, s, k in valid_triples
    )
    delivery_cost = gp.quicksum(
        float(instance.buyers[b].delivery_cost) * y[b]
        for b in buyers
    )

    # ------------------------------------------------------------
    # 4. 구매자 다품종 주문의 All-or-Nothing 제약
    # ------------------------------------------------------------
    # y[b]=1이면 주문에 포함된 모든 품목이 각각 최소수량 이상,
    # 최대수량 이하로 배정되어야 한다. y[b]=0이면 모든 배정량이 0이다.
    for b in buyers:
        buyer = instance.buyers[b]
        for k, buyer_item in buyer.items.items():
            allocated = gp.quicksum(
                x[b, s, k]
                for s in sellers
                if (b, s, k) in valid_triple_set
            )
            model.addConstr(
                allocated >= float(buyer_item.min_qty) * y[b],
                name=f"buyer_min_{b}_{k}",
            )
            model.addConstr(
                allocated <= float(buyer_item.max_qty) * y[b],
                name=f"buyer_max_{b}_{k}",
            )

    # ------------------------------------------------------------
    # 5. 공급자별·품목별 공급용량 제약
    # ------------------------------------------------------------
    # 한 공급자가 여러 구매자에게 나누어 공급할 수는 있지만 총량은
    # 해당 공급자의 품목별 용량을 초과할 수 없다.
    for s in sellers:
        seller = instance.sellers[s]
        for k, seller_item in seller.items.items():
            supplied = gp.quicksum(
                x[b, s, k]
                for b in buyers
                if (b, s, k) in valid_triple_set
            )
            model.addConstr(
                supplied <= float(seller_item.capacity),
                name=f"seller_capacity_{s}_{k}",
            )

    # ------------------------------------------------------------
    # 6. 공급자 거래 여부와 물량·잉여배분 연결
    # ------------------------------------------------------------
    # 공급자가 양의 수량을 공급할 때만 z[s]=1이 되며, 실제 거래한
    # 공급자만 v[s]를 받을 수 있다.
    for s in sellers:
        seller_total = gp.quicksum(
            x[b, seller_id, k]
            for b, seller_id, k in valid_triples
            if seller_id == s
        )
        seller_capacity_total = sum(
            float(item.capacity) for item in instance.sellers[s].items.values()
        )
        model.addConstr(
            seller_total <= seller_capacity_total * z[s],
            name=f"seller_use_upper_{s}",
        )
        model.addConstr(
            seller_total >= allocation_epsilon * z[s],
            name=f"seller_use_lower_{s}",
        )

        # z[s]=0이면 v[s]=0이므로 미거래 공급자에게는 지급할 수 없다.
        model.addConstr(
            v[s] <= surplus_big_m * z[s],
            name=f"surplus_trade_link_{s}",
        )

    # ------------------------------------------------------------
    # 7. 당기 거래잉여 배분 한도
    # ------------------------------------------------------------
    # 전체 공급자에게 배분하는 금액은 당기에 발생한 총 거래잉여를
    # 초과할 수 없다. 외부 보조금을 사용하는 구조가 아니다.
    model.addConstr(
        gp.quicksum(v[s] for s in sellers) <= gross_trade_surplus,
        name="surplus_budget",
    )

    # ------------------------------------------------------------
    # 8. 플랫폼 당기 순이윤 정의
    # ------------------------------------------------------------
    # 플랫폼 순이윤 = 총 거래잉여 - 공급자 잉여배분 - 배송비
    model.addConstr(
        pi
        == gross_trade_surplus
        - gp.quicksum(v[s] for s in sellers)
        - delivery_cost,
        name="platform_profit_balance",
    )

    # ------------------------------------------------------------
    # 9. 목적함수
    # ------------------------------------------------------------
    # 현재는 당기 순이윤만 최대화하는 Myopic 기준 정책이다.
    # 이후 ADP 단계에서 gamma * V_hat(의사결정 직후 상태)를 더한다.
    model.setObjective(pi, GRB.MAXIMIZE)
    model.optimize()

    status_map = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED",
    }
    status = status_map.get(model.Status, f"STATUS_{model.Status}")

    if model.SolCount == 0:
        return MILPSolution(
            status=status,
            objective_value=0.0,
            platform_profit=0.0,
            accepted_buyers={},
            selected_sellers={},
            allocation={},
            buyer_surplus={},
            seller_surplus={},
            solve_time=float(model.Runtime),
        )

    tolerance = 1e-6
    accepted_buyers = {b: int(round(y[b].X)) for b in buyers}
    selected_sellers = {s: int(round(z[s].X)) for s in sellers}
    allocation = {
        (b, s, k): float(x[b, s, k].X)
        for b, s, k in valid_triples
        if x[b, s, k].X > tolerance
    }
    supplier_surplus_allocation = {
        s: float(v[s].X) for s in sellers
    }

    return MILPSolution(
        status=status,
        objective_value=float(model.ObjVal),
        platform_profit=float(pi.X),
        accepted_buyers=accepted_buyers,
        selected_sellers=selected_sellers,
        allocation=allocation,
        # 최신 공급자 중심 모형에서는 구매자 잉여배분을 결정하지 않는다.
        buyer_surplus={},
        # 기존 반환구조와의 호환을 위해 seller_surplus 필드에 v[s]를 저장한다.
        seller_surplus=supplier_surplus_allocation,
        solve_time=float(model.Runtime),
    )
