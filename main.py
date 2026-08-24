from src.config import load_instance


instance = load_instance(
    "data/generated/smoke/manual_test.json"
)


print("Instance ID:", instance.instance_id)
print("Buyers:", instance.buyer_ids)
print("Sellers:", instance.seller_ids)
print("SKUs:", instance.sku_ids)

print()

print("B1 정보:")
print(instance.buyers["B1"])

print()

print("B1의 K1 주문:")
print(instance.buyers["B1"].items["K1"])

print(instance.buyers["B1"].items["K1"].min_qty)
print(instance.sellers["S1"].items["K1"].capacity)