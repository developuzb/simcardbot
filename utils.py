import math
from data import REGIONS_COORDS
from config import DELIVERY_PRICES, DEFAULT_DELIVERY_PRICE


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def detect_region(lat: float, lon: float) -> str:
    closest_region = None
    min_distance = float("inf")
    for region, (r_lat, r_lon) in REGIONS_COORDS.items():
        dist = haversine(lat, lon, r_lat, r_lon)
        if dist < min_distance:
            min_distance = dist
            closest_region = region
    return closest_region


def get_delivery_price(region: str) -> int:
    return DELIVERY_PRICES.get(region, DEFAULT_DELIVERY_PRICE)


def format_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


def build_order_summary(data: dict) -> str:
    tariff_price = data.get("tariff_price", 0)
    delivery_price = data.get("delivery_price", 0)
    total = tariff_price + delivery_price

    return (
        f"📋 <b>Buyurtma tafsilotlari</b>\n\n"
        f"👤 <b>Mijoz:</b> {data.get('name', '—')}\n"
        f"📞 <b>Tel:</b> {data.get('contact_phone', '—')}\n\n"
        f"📡 <b>Operator:</b> {data.get('operator_emoji', '')} {data.get('operator_name', '—')}\n"
        f"📦 <b>Tarif:</b> {data.get('tariff_name', '—')}\n"
        f"   └ {data.get('tariff_desc', '')}\n"
        f"📱 <b>Sim raqami:</b> {data.get('sim_number', '—')}\n\n"
        f"📍 <b>Hudud:</b> {data.get('region', '—')}\n\n"
        f"💰 <b>Tarif narxi:</b> {format_price(tariff_price)}\n"
        f"🚚 <b>Yetkazib berish:</b> {format_price(delivery_price)}\n"
        f"{'─' * 30}\n"
        f"💳 <b>Jami:</b> {format_price(total)}\n"
    )
