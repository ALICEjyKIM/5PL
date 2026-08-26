"""5PL 합성 인스턴스의 구조 및 값 검증."""

from __future__ import annotations

from typing import Any

from src.types import Instance


def validate_instance(instance: Instance, raise_on_error: bool = False) -> dict[str, Any]:
    """검증 항목별 결과와 구체적인 실패 메시지를 반환한다."""
    checks: dict[str, bool] = {}
    failures: list[str] = []
    def record(name: str, passed: bool, message: str) -> None:
        checks[name] = bool(passed)
        if not passed:
            failures.append(message)
    record("positive_counts", instance.num_buyers > 0 and instance.num_sellers > 0 and instance.num_skus > 0, "구매자·공급자·품목 수 중 1 미만인 값이 있습니다.")
    record("seller_has_item", all(s.items for s in instance.sellers.values()), "취급 품목이 없는 공급자가 있습니다.")
    covered = {sku for seller in instance.sellers.values() for sku in seller.items}
    record("every_item_has_seller", set(instance.sku_ids) <= covered, "공급자가 한 명도 없는 품목이 있습니다.")
    record("buyer_has_item", all(b.items for b in instance.buyers.values()), "주문 품목이 없는 구매자가 있습니다.")
    record("min_le_max", all(i.min_qty <= i.max_qty for b in instance.buyers.values() for i in b.items.values()), "최소주문량이 최대주문량보다 큰 주문이 있습니다.")
    record("nonnegative_demand", all(i.min_qty >= 0 and i.max_qty >= 0 for b in instance.buyers.values() for i in b.items.values()), "음수 주문량이 있습니다.")
    record("nonnegative_supply", all(i.capacity >= 0 for s in instance.sellers.values() for i in s.items.values()), "음수 공급량이 있습니다.")
    record("nonnegative_prices", all(i.wtp >= 0 for b in instance.buyers.values() for i in b.items.values()) and all(i.wta >= 0 for s in instance.sellers.values() for i in s.items.values()), "음수 WTP 또는 WTA가 있습니다.")
    record("nonnegative_delivery", all(b.delivery_cost >= 0 for b in instance.buyers.values()), "음수 배송비가 있습니다.")
    triples = [(b.buyer_id, s.seller_id, sku) for b in instance.buyers.values() for s in instance.sellers.values() for sku in set(b.items).intersection(s.items)]
    record("tradable_triples", len(triples) > 0, "거래 가능한 구매자–공급자–품목 조합이 없습니다.")
    result = {"valid": not failures, "checks": checks, "failures": failures, "tradable_triple_count": len(triples)}
    if raise_on_error and failures:
        raise ValueError("인스턴스 검증 실패:\n- " + "\n- ".join(failures))
    return result
