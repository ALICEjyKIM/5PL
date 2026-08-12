# Simulation Distribution Design

## Buyer

### 1. Number of Buyers

* Variable: (|B_1|)
* Meaning: 초기 Buyer 수
* Candidate: Fixed / Scenario-based
* Initial assumption: 30 
* Experimental levels: 30 / 50 / 100
* Olist calibration: No
* Status: Temporarily fixed

> (t >= 2)의 (B_t)는 새로 생성하지 않고 재참여확률 (r_{b,t})에 따라 결정

### 2. Number of SKUs per Order

* Variable: (|K_{bt}|)
* Meaning: Buyer b의 한 주문에 포함되는 서로 다른 SKU의 수
* Candidate distribution: Categorical / Empirical
* Olist calibration: Possible
* Initial assumption: Categorical (근거 마련 필요)
  * 1 SKU: 20%
  * 2 SKU: 30%
  * 3 SKU: 30%
  * 4 SKU: 15%
  * 5 SKU: 5%
* Future: Olist empirical distribution으로 calibration
* Status: Temporarily fixed

### 3. SKU Selection

* Variable: (K_{bt})
* Meaning: Buyer b의 주문에 포함되는 SKU 집합
* Candidate distribution: Categorical / Weighted sampling without replacement (중복X)
* Olist calibration: Possible
* Initial assumption: Uniform (모든 SKU가 똑같이 선택될 가능성이 있다고 가정)
* Future: 모든 SKU가 똑같이 선택될 가능성이 있다고 가정
* Status: Temporarily fixed

### 4. Order Quantity

* Variable: (\underline{D}_{bkt}, \overline{D}_{bkt})
* Meaning:
  * (\overline{D}_{bkt}): Buyer의 SKU별 최대 주문수량
  * (\underline{D}_{bkt}): 주문 성립을 위한 최소 요구수량
* Candidate distribution:
  * (\overline{D}_{bkt}): Lognormal / Empirical
  * \(underline{D}_{bkt} = \alpha \overline{D}_{bkt})
* Olist calibration: Partial
* Initial assumption: TBD
* Future: Olist 주문량 분포를 참고하여 (\overline{D}_{bkt}) calibration
* Status: Not fixed

### 5. WTP

* Variable: (P_{bkt})
* Meaning: Buyer b의 SKU k에 대한 단위당 최대 지불의사금액
* Candidate: Reference price ± deviation
* Olist calibration: Partial
* Olist use: SKU별 가격 수준 및 가격 변동성 calibration
* Initial assumption: TBD
* Status: Not fixed

> Reference Price 항목을 먼저 정한 뒤 WTP와 WTA를 그 주변에서 같이 설계

### 6. Delivery Cost

* Variable: (c_{bt})
* Meaning: Hub → Buyer 예상 배송비
* Candidate: Region / Quantity-based
* Olist calibration: Partial
* Olist use: 지역별 freight 차이 및 비용 규모 참고
* Initial assumption: Region-based fixed cost
* Future: Quantity effect 추가 검토
* Status: Temporarily fixed

> 개발 단계에서는 단순히 Near: 10, Medium: 20, Far: 30 처럼 시작

---

## Seller

### 1. Number of Sellers

* Variable: (|S_1|)
* Meaning: 초기 Seller 수
* Candidate: Fixed / Scenario-based
* Initial assumption: 30 
* Experimental levels: 20 / 30 / 50
* Olist calibration: No
* Status: Temporarily fixed

> (t >= 2)의 (S_t)는 재참여확률 (r_{s,t})에 따라 결정

### 2. SKU Availability

* Variable: (S_{kt})
* Meaning: 기간 t에 SKU k를 공급할 수 있는 Seller 집합
* Generation: 초기 (t=1)에서 Seller–SKU 조합별 Bernoulli sampling으로 공급 가능 여부 생성
* Candidate distribution: Bernoulli / Scenario-based
* Olist calibration: Partial / Proxy(직접 측정 어려우니 과거 판매이력을 공급가능성의 대리값proxy로 사용)
* Initial assumption: (p=0.5), 각 Seller가 평균적으로 전체 SKU의 약 50% 공급
  * Seller별 최소 1개 이상의 SKU를 공급하도록 보정
  * 각 SKU별 최소 1명 이상의 Seller가 존재하도록 보정
* Experimental factor: SKU coverage level (Low 0.3 / Medium 0.5 / High 0.7)
* Transition: 이후 공급 SKU는 고정하고, Seller 재참여 여부에 따라 S_{kt}만 갱신
* Status: Temporarily fixed

### 3. Supply Quantity

* Variable: (C_{skt})
* Meaning: 기간 t에 Seller의 SKU별 최대 공급량
* Generation: 공급 가능한 Seller–SKU 조합에 대해서만 공급량 생성하며, 공급 불가능한 경우 (C_{skt}=0)
* Candidate distribution: Gamma (Seller별 공급량 차이가 있는 시장을 만들어서 재참여 효과를 보기위함)
* Olist calibration: Olist calibration: Difficult / Proxy (실제 판매량은 관측 가능하지만 Seller의 최대 공급능력은 직접 알 수 없음)
* Initial assumption: Gamma distribution 기반으로 생성하고, 전체 공급량은 목표 Demand–Supply balance에 맞게 조정
* Experimental factor: Supply level (Scarce 0.7 / Balanced 1.0 / Abundant 1.3)
* Status: Temporarily fixed

### 4. WTA

* Variable: (P_{skt})
* Meaning: Seller s가 SKU k를 공급하기 위해 요구하는 단위당 최소 허용가격
* Generation: 공급 가능한 Seller–SKU 조합에 대해 (P^{ref}_{kt}) 기준으로 Seller별 가격편차(\epsilon^S{skt})를 생성하여 WTA 결정
* Candidate: Reference price ± deviation
* Olist calibration: Limited / Proxy (실제 거래가격의 수준·분산은 참고 가능하지만 Seller의 실제 WTA는 관측 불가)
* Initial assumption: SKU 기준가격 (P^{ref}{kt})를 중심으로, 각 Seller는 최대 ±10% 범위 내에서 개별적인 가격 민감도 (\epsilon^S{skt})를 가진다고 가정하며, 
                      이를 반영해 (P^S_{skt}=P^{ref}_{kt} * (1+\epsilon^S{skt}))로 WTA를 설정
* Experimental factor: Seller price dispersion (Low ±5% / Medium ±10% / High ±20%)
* Status: Temporarily fixed (Baseline: ±10%)

---

## Market

### 1. Number of SKUs

* Variable: (|K|)
* Candidate: Fixed
* Initial assumption: (|K|=5)
* Olist calibration: Not required
* Status: Fixed

### 2. Reference Price

* Variable: (P^{ref}_{kt})
* Meaning: SKU k의 WTP와 WTA를 생성하기 위한 시장 기준가격
* Generation: 초기 (t=1)에 SKU별 기준가격을 설정하고 전체 기간 동안 고정
* Candidate: Normalized fixed value / Olist-based calibration
* Olist calibration: Possible (SKU/카테고리별 거래가격을 이용해 기준가격 수준 설정 가능)
* Initial assumption: TBD (Olist 가격분포 분석 후 결정)
* Status: Not fixed

### 3. Demand–Supply Balance

* Variable:
  [
  \frac{\sum_s C_{skt}}
  {\sum_b \overline{D}_{bkt}}
  ]
* Meaning: SKU (k)의 총 최대수요 대비 총 공급가능량 비율
* Generation: 수요와 Seller별 공급량 생성 후, 목표 비율에 맞도록 (C_{skt})의 전체 규모 조정
* Candidate: Scenario-based
* Experimental factor: Supply–Demand condition
* Olist calibration: Difficult (실제 판매량은 관측 가능하지만 잠재 수요와 최대 공급능력은 직접 관측 불가)
* Initial assumption:
  * Scarce: 0.7
  * Balanced: 1.0
  * Abundant: 1.3
* Status: Temporarily fixed (scenario levels are provisional)

### 4. Expected Demand

* Variable: (\hat{D}_{k,t+1})
* Meaning: 다음 기간 SKU별 예상 총수요
* Generation: 이전 기간들의 SKU별 실제 주문량을 이용하여 다음 기간 수요 추정
* Candidate: Moving average / Historical average
* Initial assumption: 최근 (L)개 기간의 SKU별 평균수요를 사용하는 Moving average
* Olist calibration: Possible (상품/카테고리별 주문빈도와 기간별 수요 변동 참고 가능)
* Initial value: 시뮬레이션 초기에는 초기 생성수요 또는 사전 설정된 평균수요 사용
* Status: Not fixed

---

## Participant State

### 1. Matching History

* Variable: (h_{bt}, h_{st})
* Meaning: Buyer와 Seller의 과거 매칭 경험을 반영하는 누적 상태값
* Initial value: (h_{b1}=h_{s1}=0)
* Distribution: None
* Update rule: (h_{b,t+1}=\rho_B h_{bt}+(1-\rho_B)y_{bt}), Seller도 동일한 방식으로 갱신
* Role: 재참여확률 계산에 사용
* Status: Fixed structure

### 2. Retention Probability

* Variable: (r_{b,t+1}, r_{s,t+1})
* Meaning: Buyer와 Seller가 다음 기간에 다시 참여할 확률
* Distribution: None
* Generated directly: No
* Determined by:
  * normalized surplus (\eta)
  * matching history (h)
  * surplus gap (\Delta)
  * price deviation (Dev)
* Calculation: 각 요인을 결합한 retention function을 통해 (0\sim1)의 확률로 산출
* Transition: 산출된 확률을 이용해 다음 기간 실제 참여 여부 결정
* Status: Model-derived

---

## Olist Calibration Candidates

Olist를 직접적인 B2B 데이터로 사용하지 않고 다음 입력분포의 calibration에 활용한다.

* [ ] 주문당 SKU 수 (|K_{bt}|)
* [ ] SKU별 선택확률
* [ ] 주문량 (D_{bkt})
* [ ] 품목별 가격 수준
* [ ] 가격 변동성
* [ ] (P^{ref}_{kt})
* [ ] 주문 발생 패턴
* [ ] 품목별 상대적 수요빈도

---

## To Do

* [ ] (|B_1|), (|S_1|), (|K|) 결정
* [ ] (|K_{bt}|) 분포 확인
* [ ] SKU 선택확률 확인
* [ ] (D_{bkt}) 분포 확인
* [ ] (C_{skt}) 분포 설정
* [ ] (P_{bkt}), (P_{skt}) 생성 방식 설정
* [ ] (P^{ref}_{kt}) 생성 방식 설정
* [ ] (c_{bt}) 생성 방식 설정
* [ ] Olist에서 실제 사용할 항목 결정
