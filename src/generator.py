"""재현 가능한 단일기간 5PL 합성 인스턴스 생성기."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from src.config import PROJECT_ROOT, load_config
from src.types import Buyer, BuyerItem, Instance, Seller, SellerItem


def _config_dict(config: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """설정 매핑 또는 프로젝트 상대 JSON 경로를 일반 dict로 바꾼다."""
    return dict(load_config(config)) if isinstance(config, (str, Path)) else dict(config)


def generate_instance(config: Mapping[str, Any] | str | Path = "configs/smoke.json") -> Instance:
    """설정에 따라 구조적 보정 조건을 만족하는 시장 인스턴스를 생성한다."""
    cfg = _config_dict(config)
    seed = int(cfg["seed"])
    rng = np.random.default_rng(seed)
    num_buyers = int(cfg["num_buyers"])
    num_sellers = int(cfg["num_sellers"])
    num_skus = int(cfg["num_skus"])
    if min(num_buyers, num_sellers, num_skus) < 1:
        raise ValueError("구매자·공급자·품목 수는 모두 1 이상이어야 합니다.")
    sku_ids = [f"K{i + 1}" for i in range(num_skus)]
    price_cfg = cfg["reference_price"]
    reference_prices = {sku: float(rng.uniform(price_cfg["min"], price_cfg["max"])) for sku in sku_ids}
    qty_cfg = cfg["order_quantity"]
    count_values = np.asarray(cfg["buyer_sku_count_values"], dtype=int)
    count_probs = np.asarray(cfg["buyer_sku_count_probs"], dtype=float)
    count_probs = count_probs / count_probs.sum()
    premium_cfg = cfg["buyer_price_premium"]
    regions = list(cfg["regions"].items())
    history_cfg = cfg["initial_history"]
    buyers: dict[str, Buyer] = {}
    total_demand = {sku: 0.0 for sku in sku_ids}
    for index in range(num_buyers):
        buyer_id = f"B{index + 1}"
        requested_count = max(1, min(int(rng.choice(count_values, p=count_probs)), num_skus))
        selected = rng.choice(sku_ids, size=requested_count, replace=False)
        buyer_items: dict[str, BuyerItem] = {}
        for sku_value in selected:
            sku = str(sku_value)
            max_qty = float(rng.integers(int(qty_cfg["min"]), int(qty_cfg["max"]) + 1))
            min_qty = float(max(1, round(max_qty * float(qty_cfg["minimum_fraction"]))))
            premium = float(rng.uniform(premium_cfg["min"], premium_cfg["max"]))
            buyer_items[sku] = BuyerItem(sku, min_qty, max_qty, reference_prices[sku] * (1 + premium))
            total_demand[sku] += max_qty
        _, delivery_cost = regions[int(rng.integers(0, len(regions)))]
        buyers[buyer_id] = Buyer(buyer_id, buyer_items, float(delivery_cost), float(rng.beta(history_cfg["alpha"], history_cfg["beta"])))
    coverage = rng.random((num_sellers, num_skus)) < float(cfg["seller_coverage_probability"])
    for seller_index in range(num_sellers):
        if not coverage[seller_index].any():
            coverage[seller_index, int(rng.integers(0, num_skus))] = True
    for sku_index in range(num_skus):
        if not coverage[:, sku_index].any():
            coverage[int(rng.integers(0, num_sellers)), sku_index] = True
    raw_capacity = rng.gamma(shape=2.0, scale=10.0, size=(num_sellers, num_skus)) * coverage
    ratio = float(cfg["supply_ratios"][cfg["supply_scenario"]])
    for sku_index, sku in enumerate(sku_ids):
        current = raw_capacity[:, sku_index].sum()
        if current > 0:
            raw_capacity[:, sku_index] *= total_demand[sku] * ratio / current
    dispersion = float(cfg["seller_price_dispersion"])
    sellers: dict[str, Seller] = {}
    for seller_index in range(num_sellers):
        seller_id = f"S{seller_index + 1}"
        seller_items: dict[str, SellerItem] = {}
        for sku_index, sku in enumerate(sku_ids):
            if coverage[seller_index, sku_index]:
                wta = reference_prices[sku] * (1 + float(rng.uniform(-dispersion, dispersion)))
                seller_items[sku] = SellerItem(sku, float(raw_capacity[seller_index, sku_index]), float(wta))
        sellers[seller_id] = Seller(seller_id, seller_items, float(rng.beta(history_cfg["alpha"], history_cfg["beta"])))
    return Instance(str(cfg.get("instance_id", f"instance_{seed}")), sku_ids, buyers, sellers, seed, int(cfg.get("period", 1)))


def save_instance(instance: Instance, path: str | Path) -> Path:
    """인스턴스를 UTF-8 JSON으로 저장한다."""
    output = Path(path)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(instance.to_dict(), handle, ensure_ascii=False, indent=2)
    return output
