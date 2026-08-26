# src/optimization/milp.py

from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from src.types import Instance, MILPSolution


# ============================================================
# 단일 기간 MILP
# ============================================================
# 단일 기간 5PL 매칭 MILP를 푼다.
# 현재 버전은 MILP 검산을 위한 1차 단순 모형
"""주요 결정:
        x[b, s, k]: 공급자 s의 SKU k를 구매자 b에게 배정하는 수량

        y[b]: 구매자 b의 다품종 주문 수락 여부

    목적함수:
        총 거래잉여 - 구매자 배송비 최대화

        거래잉여 =
            (Buyer WTP - Seller WTA) * 거래량

    주요 제약:
        1. 다품종 주문 All-or-Nothing
        2. 구매자 SKU별 최소 주문량
        3. 구매자 SKU별 최대 주문량
        4. 공급자 SKU별 공급용량"""
"""주의:
        현재 목적함수는 최종 연구모형의 플랫폼 순이윤(pi_t)과
        완전히 동일하지 않다.

        지금은 MILP 구조 및 데이터 연결 검산을 위해
        '총 거래잉여 - 배송비'를 사용한다.

        이후 u, v, pi 잉여배분 변수를 추가하여
        실제 플랫폼 순이윤 목적함수로 확장한다."""


def solve_milp(
    instance: Instance,
    output_flag: bool = True,
) -> MILPSolution:
    # ========================================================
    # 1. Sets
    # ========================================================

    # 구매자 집합 B
    B = instance.buyer_ids

    # 공급자 집합 S
    S = instance.seller_ids

    # 전체 SKU 집합 K
    K = instance.sku_ids

    # ========================================================
    # 2. 가능한 거래 조합 생성
    # ========================================================
    valid_triples = []

    for b in B:
        buyer = instance.buyers[b]

        for s in S:
            seller = instance.sellers[s]

            for k in K:
                buyer_has_sku = k in buyer.items
                seller_has_sku = k in seller.items

                if buyer_has_sku and seller_has_sku:
                    valid_triples.append((b, s, k))

    # 빠른 membership 검사를 위해 set 만들어 두기
    valid_triple_set = set(valid_triples)

    # ========================================================
    # 3. Gurobi Model 생성
    # ========================================================

    model = gp.Model(f"5PL_single_period_{instance.instance_id}")

    # output_flag = True이면 Gurobi 로그 출력
    # output_flag = False이면 로그 숨김
    model.Params.OutputFlag = 1 if output_flag else 0

    # ========================================================
    # 4. Decision Variables
    # ========================================================

    # --------------------------------------------------------
    # x[b, s, k]
    #
    # 공급자 s의 SKU k를 구매자 b에게 배정하는 수량
    #
    # 연속변수로 설정.
    #
    # 예:
    # x["B1", "S1", "K1"] = 5
    # → S1의 K1을 B1에게 5단위 공급
    # --------------------------------------------------------

    x = model.addVars(
        valid_triples,
        lb=0.0,
        vtype=GRB.CONTINUOUS,
        name="x",
    )

    # --------------------------------------------------------
    # y[b]
    #
    # 구매자 b의 주문 수락 여부
    #
    # y[b] = 1
    # → 구매자 주문 수락
    #
    # y[b] = 0
    # → 구매자 주문 거절
    # --------------------------------------------------------

    y = model.addVars(
        B,
        vtype=GRB.BINARY,
        name="y",
    )

    # ========================================================
    # 5. Objective Function
    # ========================================================

    # --------------------------------------------------------
    # 5-1. 거래에서 발생하는 총잉여
    #
    # 단위당 거래잉여:
    #
    # Buyer WTP - Seller WTA
    #
    # 예:
    # WTP = 12
    # WTA = 7
    #
    # → 단위당 잉여 = 5
    #
    # 5단위를 거래하면:
    #
    # 5 * 5 = 25
    # --------------------------------------------------------

    trade_surplus = gp.quicksum(
        (instance.buyers[b].items[k].wtp - instance.sellers[s].items[k].wta)
        * x[b, s, k]
        for b, s, k in valid_triples
    )

    # --------------------------------------------------------
    # 5-2. 배송비
    #
    # 구매자 주문이 수락될 경우(y[b] = 1)
    # 플랫폼이 해당 구매자의 배송비를 부담한다고 가정.
    #
    # y[b] = 0이면 배송비도 0.
    # --------------------------------------------------------

    delivery_cost = gp.quicksum(instance.buyers[b].delivery_cost * y[b] for b in B)

    # --------------------------------------------------------
    # 5-3. 목적함수
    #
    # 현재 검산용 모형:
    #
    # 총 거래잉여 - 총 배송비
    #
    # 최대화
    # --------------------------------------------------------

    model.setObjective(
        trade_surplus - delivery_cost,
        GRB.MAXIMIZE,
    )

    # ========================================================
    # 6. Constraints
    # ========================================================

    # ========================================================
    # 6-1. Buyer All-or-Nothing 주문 제약
    # ========================================================
    #
    # 구매자 b가 주문한 각각의 SKU k에 대해:
    #
    # min_qty[b,k] * y[b]
    #       <=
    # 실제 배정량
    #       <=
    # max_qty[b,k] * y[b]
    #
    #
    # 예:
    #
    # B1:
    #   K1 최소 5, 최대 10
    #   K2 최소 3, 최대 8
    #
    #
    # y[B1] = 1이면
    #
    # K1 >= 5
    # K2 >= 3
    #
    # 둘 다 만족해야 한다.
    #
    #
    # y[B1] = 0이면
    #
    # K1 = 0
    # K2 = 0
    #
    # 즉 주문 전체가 거절된다.
    #
    # 이것이 다품종 All-or-Nothing 구조이다.
    # ========================================================

    for b in B:
        buyer = instance.buyers[b]

        # 해당 buyer가 실제 주문한 SKU만 반복
        for k, buyer_item in buyer.items.items():
            # buyer b가 SKU k를 모든 seller로부터
            # 공급받는 총량
            total_allocated_to_buyer = gp.quicksum(
                x[b, s, k] for s in S if (b, s, k) in valid_triple_set
            )

            # ------------------------------------------------
            # 최소 요구수량
            # ------------------------------------------------

            model.addConstr(
                total_allocated_to_buyer >= buyer_item.min_qty * y[b],
                name=f"buyer_min_{b}_{k}",
            )

            # ------------------------------------------------
            # 최대 주문수량
            # ------------------------------------------------

            model.addConstr(
                total_allocated_to_buyer <= buyer_item.max_qty * y[b],
                name=f"buyer_max_{b}_{k}",
            )

    # ========================================================
    # 6-2. Seller 공급용량 제약
    # ========================================================
    #
    # 공급자 s가 SKU k를 여러 buyer에게 나눠서 공급할 수 있지만,
    # 전체 공급량은 capacity[s,k]를 초과할 수 없다.
    #
    # 예:
    #
    # S1 K1 capacity = 8
    #
    # B1에게 5
    # B2에게 3
    #
    # → 가능
    #
    # B1에게 5
    # B2에게 4
    #
    # → 총 9이므로 불가능
    # ========================================================

    for s in S:
        seller = instance.sellers[s]

        # seller가 실제 공급 가능한 SKU만 반복
        for k, seller_item in seller.items.items():
            total_allocated_from_seller = gp.quicksum(
                x[b, s, k] for b in B if (b, s, k) in valid_triple_set
            )

            model.addConstr(
                total_allocated_from_seller <= seller_item.capacity,
                name=f"seller_capacity_{s}_{k}",
            )

    # ========================================================
    # 7. Model update
    # ========================================================

    # 최근 Gurobi에서는 반드시 필요하지는 않지만,
    # 변수 및 제약 정의를 명시적으로 반영하기 위해 호출.
    model.update()

    # ========================================================
    # 8. Optimize
    # ========================================================

    model.optimize()

    # ========================================================
    # 9. Solver Status 확인
    # ========================================================

    status_map = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED",
    }

    status = status_map.get(
        model.Status,
        f"STATUS_{model.Status}",
    )

    # ========================================================
    # 10. 해가 없는 경우
    # ========================================================

    # 최적해도 없고 feasible solution도 없는 경우
    # 빈 MILPSolution을 반환한다.

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
            solve_time=model.Runtime,
        )

    # ========================================================
    # 11. Solution 추출
    # ========================================================

    # --------------------------------------------------------
    # 11-1. 구매자 주문 수락 여부
    # --------------------------------------------------------

    accepted_buyers = {}

    for b in B:
        accepted_buyers[b] = int(round(y[b].X))

    # --------------------------------------------------------
    # 11-2. 실제 거래량
    # --------------------------------------------------------

    allocation = {}

    # numerical tolerance
    tolerance = 1e-6

    for b, s, k in valid_triples:
        quantity = x[b, s, k].X

        # 0인 거래는 저장하지 않는다.
        if quantity > tolerance:
            allocation[(b, s, k)] = float(quantity)

    # --------------------------------------------------------
    # 11-3. 선택된 Seller
    # --------------------------------------------------------
    #
    # 현재 1차 모형에는 z[s] 변수를 아직 넣지 않았다.
    #
    # 따라서 실제 allocation이 하나라도 존재하는 seller를
    # 선택된 seller로 간주한다.
    #
    # 이후 연구모형에서 z[s] 변수를 직접 추가할 예정이다.
    # --------------------------------------------------------

    selected_sellers = {}

    for s in S:
        seller_is_used = any(
            seller_id == s and qty > tolerance
            for (b, seller_id, k), qty in allocation.items()
        )

        selected_sellers[s] = 1 if seller_is_used else 0

    # ========================================================
    # 12. 목적함수 값
    # ========================================================

    objective_value = float(model.ObjVal)

    # ========================================================
    # 13. platform_profit에 대한 주의
    # ========================================================
    #
    # 현재 목적함수는
    #
    #   총 거래잉여 - 배송비
    #
    # 이다.
    #
    # 따라서 엄밀하게 말하면 이것은 최종 연구모형의
    # 플랫폼 순이윤 pi_t가 아니다.
    #
    # 하지만 현재 MILP 검산 단계에서는 임시로
    # platform_profit 필드에도 동일한 값을 넣는다.
    #
    # 이후 u, v, pi 잉여배분 변수를 추가할 때
    # 이 부분을 실제 pi_t로 교체한다.
    # ========================================================

    platform_profit = objective_value

    # ========================================================
    # 14. 결과 반환
    # ========================================================

    return MILPSolution(
        status=status,
        objective_value=objective_value,
        platform_profit=platform_profit,
        accepted_buyers=accepted_buyers,
        selected_sellers=selected_sellers,
        allocation=allocation,
        # 잉여배분 변수 u, v는 아직 구현하지 않았기 때문에
        # 현재는 빈 dictionary로 반환.
        buyer_surplus={},
        seller_surplus={},
        solve_time=float(model.Runtime),
    )
