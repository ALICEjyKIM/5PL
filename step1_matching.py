import gurobipy as gp
from gurobipy import GRB


class Step1MatchingSolver:
    def __init__(self, buyers, sellers, gamma=0.9, v_hat_next=150.0, big_m=100000):
        self.buyers = buyers
        self.sellers = sellers
        self.gamma = gamma
        self.v_hat_next = v_hat_next
        self.big_m = big_m

        # Gurobi 모델 객체 생성
        self.model = gp.Model("Step1_MultiProduct_Matching")
        self.model.setParam('OutputFlag', 0)  # 로그 출력 숨김

        # 변수 저장용 딕셔너리 초기화
        self.y = {}      # 구매자 수락 여부 (Binary)
        self.z = {}      # 공급자 선택 여부 (Binary)
        self.x = {}      # 거래 수량 (Continuous)
        self.u_bs = {}   # 구매자 배분 잉여
        self.v_bs = {}   # 공급자 배분 잉여
        self.pi_bs = {}  # 플랫폼 거래쌍별 gross 잉여
        self.u_b = {}    # 구매자 총 잉여
        self.v_s = {}    # 공급자 총 잉여
        self.pi_t = None # 플랫폼 당기 순이윤

    def create_variables(self):
        """1. 결정 변수(Decision Variables) 정의"""
        # (1) 구매자 수락 여부 (y_b) 및 공급자 선택 여부 (z_s)
        for b_id in self.buyers:
            self.y[b_id] = self.model.addVar(vtype=GRB.BINARY, name=f"y_{b_id}")

        for s_id in self.sellers:
            self.z[s_id] = self.model.addVar(vtype=GRB.BINARY, name=f"z_{s_id}")

        # (2) 거래 수량 변수 (x_bsk): 공통 취급 품목만 생성 (Sparsity 반영)
        for b_id, b_data in self.buyers.items():
            for s_id, s_data in self.sellers.items():
                common_items = set(b_data['orders'].keys()) & set(s_data.keys())
                for k in common_items:
                    self.x[(b_id, s_id, k)] = self.model.addVar(
                        lb=0.0, vtype=GRB.CONTINUOUS, name=f"x_{b_id}_{s_id}_{k}"
                    )

        # (3) 거래쌍별 잉여 배분 변수 (u_bs, v_bs, pi_bs)
        for b_id in self.buyers:
            for s_id in self.sellers:
                pair = (b_id, s_id)
                self.u_bs[pair] = self.model.addVar(lb=0.0, name=f"u_{b_id}_{s_id}")
                self.v_bs[pair] = self.model.addVar(lb=0.0, name=f"v_{b_id}_{s_id}")
                self.pi_bs[pair] = self.model.addVar(lb=0.0, name=f"pi_{b_id}_{s_id}")

        # (4) 참여자별 합산 잉여 및 플랫폼 순이윤
        for b_id in self.buyers:
            self.u_b[b_id] = self.model.addVar(lb=0.0, name=f"u_{b_id}")
        for s_id in self.sellers:
            self.v_s[s_id] = self.model.addVar(lb=0.0, name=f"v_{s_id}")

        self.pi_t = self.model.addVar(lb=0.0, name="pi_t")

    def set_objective_and_constraints(self):
        """2. 목적함수 설정 및 핵심 제약식(Constraints) 추가"""
        # (1) 목적함수: max pi_t + gamma * V_hat_{t+1}
        obj_expr = self.pi_t + self.gamma * self.v_hat_next
        self.model.setObjective(obj_expr, GRB.MAXIMIZE)

        # (2) 제약식 1: 다품종 주문 일괄 수락 제약
        for b_id, b_data in self.buyers.items():
            for k, item_data in b_data['orders'].items():
                matched_x = [self.x[(b_id, s_id, k)] for s_id in self.sellers if (b_id, s_id, k) in self.x]
                self.model.addConstr(
                    gp.quicksum(matched_x) >= item_data['min_demand'] * self.y[b_id],
                    name=f"MinDemand_{b_id}_{k}"
                )
                self.model.addConstr(
                    gp.quicksum(matched_x) <= item_data['max_demand'] * self.y[b_id],
                    name=f"MaxDemand_{b_id}_{k}"
                )

        # (3) 제약식 2: 공급 용량 제약 및 공급자 선택(z_s) 연동
        for s_id, s_data in self.sellers.items():
            for k, item_data in s_data.items():
                matched_x = [self.x[(b_id, s_id, k)] for b_id in self.buyers if (b_id, s_id, k) in self.x]
                self.model.addConstr(
                    gp.quicksum(matched_x) <= item_data['capacity'],
                    name=f"SupplyCap_{s_id}_{k}"
                )

            all_s_x = [self.x[(b_id, s_id, k)] for (b_id, s, k) in self.x.keys() if s == s_id]
            self.model.addConstr(
                gp.quicksum(all_s_x) <= self.big_m * self.z[s_id],
                name=f"SupplierSelect_{s_id}"
            )

        # (4) 제약식 3: 거래 쌍별 총잉여 배분 제약
        for b_id, b_data in self.buyers.items():
            for s_id, s_data in self.sellers.items():
                pair = (b_id, s_id)
                common_items = set(b_data['orders'].keys()) & set(s_data.keys())

                surplus_expr = gp.quicksum(
                    (b_data['orders'][k]['bid_price'] - s_data[k]['ask_price']) * self.x[(b_id, s_id, k)]
                    for k in common_items
                )
                self.model.addConstr(
                    self.pi_bs[pair] + self.u_bs[pair] + self.v_bs[pair] == surplus_expr,
                    name=f"SurplusSplit_{b_id}_{s_id}"
                )

        # (5) 제약식 4: 참여자별 총 잉여 합산
        for b_id in self.buyers:
            self.model.addConstr(
                self.u_b[b_id] == gp.quicksum(self.u_bs[(b_id, s_id)] for s_id in self.sellers),
                name=f"TotalBuyerSurplus_{b_id}"
            )
        for s_id in self.sellers:
            self.model.addConstr(
                self.v_s[s_id] == gp.quicksum(self.v_bs[(b_id, s_id)] for b_id in self.buyers),
                name=f"TotalSellerSurplus_{s_id}"
            )

        # (6) 제약식 5: 플랫폼 순이윤 및 약한 예산 균형 (Weak Budget Balance)
        gross_pi_sum = gp.quicksum(self.pi_bs[(b, s)] for b in self.buyers for s in self.sellers)
        delivery_cost_sum = gp.quicksum(b_data['delivery_cost'] * self.y[b_id] for b_id, b_data in self.buyers.items())

        self.model.addConstr(
            self.pi_t == gross_pi_sum - delivery_cost_sum,
            name="PlatformNetProfitDef"
        )

    def solve(self):
        """3. Gurobi 최적화 실행"""
        self.model.optimize()

        if self.model.status == GRB.OPTIMAL:
            print("=== 최적화 성공 (Optimal Solution Found) ===")
            print(f"목적식 값 (당기이윤 + 할인된 미래가치): {self.model.objVal:.2f}")
            print(f"플랫폼 당기 순이윤 (pi_t): {self.pi_t.X:.2f}\n")
        else:
            print(f"최적해를 찾지 못했습니다. Status Code: {self.model.status}")

    def extract_results(self):
        """4. 매칭 결과 및 잉여 배분 수치 추출"""
        if self.model.status != GRB.OPTIMAL:
            return None

        results = {
            'pi_t': self.pi_t.X,
            'buyer_acceptance': {b: self.y[b].X for b in self.buyers},
            'seller_selection': {s: self.z[s].X for s in self.sellers},
            'buyer_surplus': {b: self.u_b[b].X for b in self.buyers},
            'seller_surplus': {s: self.v_s[s].X for s in self.sellers},
            'matches': []
        }

        for (b_id, s_id, k), var in self.x.items():
            if var.X > 1e-5:
                results['matches'].append({
                    'buyer': b_id,
                    'seller': s_id,
                    'item': k,
                    'quantity': var.X
                })

        return results


# =====================================================================
# 메인 실행 파이프라인
# =====================================================================
if __name__ == "__main__":
    # 1. 시장 기준 가격 (Step 2 제안가 편차 계산용)
    market_ref_price = {'k1': 50, 'k2': 65, 'k3': 80}

    # 2. 공급자 데이터 (공급 용량 C_skt 및 희망가격 P_skt)
    sellers = {
        's1': {'k1': {'capacity': 50, 'ask_price': 35}, 'k2': {'capacity': 40, 'ask_price': 48}},
        's2': {'k2': {'capacity': 60, 'ask_price': 45}, 'k3': {'capacity': 50, 'ask_price': 70}},
        's3': {'k1': {'capacity': 40, 'ask_price': 38}, 'k3': {'capacity': 60, 'ask_price': 68}}
    }

    # 3. 구매자 데이터 (배송비 c_bt, 품목별 최소/최대 요구량 D_bkt, \bar{D}_bkt, 지불의사가 P_bkt)
    buyers = {
        'b1': {
            'delivery_cost': 5,
            'orders': {
                'k1': {'min_demand': 20, 'max_demand': 30, 'bid_price': 60},
                'k2': {'min_demand': 15, 'max_demand': 25, 'bid_price': 70}
            }
        },
        'b2': {
            'delivery_cost': 4,
            'orders': {
                'k2': {'min_demand': 25, 'max_demand': 40, 'bid_price': 68},
                'k3': {'min_demand': 10, 'max_demand': 20, 'bid_price': 85}
            }
        }
    }

    # 4. Sol가 객체 생성 및 최적화 실행
    solver = Step1MatchingSolver(buyers, sellers, gamma=0.9, v_hat_next=150.0)
    solver.create_variables()
    solver.set_objective_and_constraints()
    solver.solve()

    # 5. 결과 추출 및 출력
    res = solver.extract_results()
    if res:
        print("--- 구매자 수락 상태 및 잉여 ---")
        for b, accepted in res['buyer_acceptance'].items():
            status = "수락" if accepted > 0.5 else "탈락"
            print(f"  구매자 {b}: {status} | 총잉여 u_b = {res['buyer_surplus'][b]:.1f}")

        print("\n--- 공급자 선택 상태 및 잉여 ---")
        for s, selected in res['seller_selection'].items():
            status = "선택됨" if selected > 0.5 else "미선택"
            print(f"  공급자 {s}: {status} | 총잉여 v_s = {res['seller_surplus'][s]:.1f}")

        print("\n--- 상세 매칭 결과 (x_bsk) ---")
        for m in res['matches']:
            print(f"  [매칭] {m['buyer']} <-> {m['seller']} | 품목: {m['item']} | 수량: {m['quantity']:.1f}")
