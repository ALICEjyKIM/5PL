# src/config.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.types import (
    Buyer,
    BuyerItem,
    Seller,
    SellerItem,
    Instance,
)


# ============================================================
# 1. 프로젝트 루트 경로
# ============================================================

# 현재 파일 위치:
# 5pl/src/config.py
#
# parent      -> src
# parent.parent -> 5pl
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# 2. 일반 JSON 읽기
# ============================================================

def load_json(path: str | Path) -> Dict[str, Any]:
    """
    JSON 파일을 읽어서 Python dictionary로 반환한다.

    Parameters
    ----------
    path : str | Path
        읽을 JSON 파일 경로

    Returns
    -------
    Dict[str, Any]
        JSON 내용을 담은 dictionary
    """

    path = Path(path)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ============================================================
# 3. 실험 설정 파일 읽기
# ============================================================

def load_config(
    config_path: str | Path = "configs/smoke.json"
) -> Dict[str, Any]:
    """
    smoke.json, baseline.json 등
    실험 설정 파일을 읽는다.

    Example
    -------
    config = load_config("configs/smoke.json")

    print(config["seed"])
    print(config["num_buyers"])
    """

    return load_json(config_path)


# ============================================================
# 4. JSON -> Buyer 객체
# ============================================================

def _parse_buyer(buyer_data: Dict[str, Any]) -> Buyer:
    """
    JSON의 buyer 정보를 Buyer 객체로 변환한다.
    """

    items = {}

    for sku_id, item_data in buyer_data["items"].items():

        items[sku_id] = BuyerItem(
            sku_id=item_data["sku_id"],
            min_qty=float(item_data["min_qty"]),
            max_qty=float(item_data["max_qty"]),
            wtp=float(item_data["wtp"]),
        )

    return Buyer(
        buyer_id=buyer_data["buyer_id"],
        items=items,
        delivery_cost=float(
            buyer_data.get("delivery_cost", 0.0)
        ),
        match_history=float(
            buyer_data.get("match_history", 0.0)
        ),
    )


# ============================================================
# 5. JSON -> Seller 객체
# ============================================================

def _parse_seller(seller_data: Dict[str, Any]) -> Seller:
    """
    JSON의 seller 정보를 Seller 객체로 변환한다.
    """

    items = {}

    for sku_id, item_data in seller_data["items"].items():

        items[sku_id] = SellerItem(
            sku_id=item_data["sku_id"],
            capacity=float(item_data["capacity"]),
            wta=float(item_data["wta"]),
        )

    return Seller(
        seller_id=seller_data["seller_id"],
        items=items,
        match_history=float(
            seller_data.get("match_history", 0.0)
        ),
    )


# ============================================================
# 6. 시장 Instance 읽기
# ============================================================

def load_instance(
    instance_path: str | Path
) -> Instance:
    """
    manual_test.json 또는 generator가 생성한 JSON을 읽어서
    MILP가 사용할 Instance 객체로 변환한다.

    Example
    -------
    instance = load_instance(
        "data/generated/smoke/manual_test.json"
    )
    """

    data = load_json(instance_path)

    # -------------------------
    # Buyers
    # -------------------------

    buyers = {}

    for buyer_id, buyer_data in data["buyers"].items():
        buyers[buyer_id] = _parse_buyer(buyer_data)

    # -------------------------
    # Sellers
    # -------------------------

    sellers = {}

    for seller_id, seller_data in data["sellers"].items():
        sellers[seller_id] = _parse_seller(seller_data)

    # -------------------------
    # Instance
    # -------------------------

    instance = Instance(
        instance_id=data["instance_id"],
        sku_ids=list(data["sku_ids"]),
        buyers=buyers,
        sellers=sellers,
        seed=int(data.get("seed", 0)),
        period=int(data.get("period", 1)),
    )

    return instance