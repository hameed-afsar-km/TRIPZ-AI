"""
Hotel Tool — zero AI calls.
Returns realistic hotel options for any destination.
Uses specific hotel names for major cities, templates for others.
"""

from typing import Any, Dict, List
from services.exchange_service import get_exchange_rate


def _default_hotels(destination: str) -> List[Dict[str, Any]]:
    d = destination
    return [
        {"name": f"Grand {d} Palace Hotel",     "stars": 5, "price_per_night": 280, "rating": 4.8, "amenities": ["pool", "spa", "gym", "restaurant", "bar"]},
        {"name": f"{d} Boutique Hotel",          "stars": 4, "price_per_night": 145, "rating": 4.5, "amenities": ["breakfast", "wifi", "bar", "gym"]},
        {"name": f"Central Inn {d}",             "stars": 3, "price_per_night": 85,  "rating": 4.1, "amenities": ["wifi", "breakfast", "24h-reception"]},
        {"name": f"{d} Budget Inn",              "stars": 2, "price_per_night": 45,  "rating": 3.7, "amenities": ["wifi"]},
        {"name": f"{d} Hostel & Rooms",          "stars": 2, "price_per_night": 28,  "rating": 4.0, "amenities": ["locker", "shared-bathroom", "wifi"]},
    ]


HOTEL_DB: Dict[str, List[Dict[str, Any]]] = {
    "dubai": [
        {"name": "Sonder by Marriott Bonvoy Business Bay Apartments", "stars": 4, "price_per_night": 80,  "rating": 4.3, "amenities": ["pool", "gym", "kitchen", "wifi", "parking"]},
        {"name": "Rove Downtown Dubai",                                "stars": 3, "price_per_night": 55,  "rating": 4.5, "amenities": ["pool", "gym", "wifi", "breakfast"]},
        {"name": "Ibis Al Rigga",                                       "stars": 3, "price_per_night": 35,  "rating": 3.9, "amenities": ["wifi", "restaurant", "parking"]},
        {"name": "Palazzo Versace Dubai",                               "stars": 5, "price_per_night": 350, "rating": 4.7, "amenities": ["pool", "spa", "gym", "fine-dining", "butler"]},
        {"name": "Hyatt Regency Dubai Creek Heights",                   "stars": 5, "price_per_night": 120, "rating": 4.4, "amenities": ["pool", "spa", "gym", "multiple-restaurants"]},
        {"name": "Premier Inn Dubai Investments Park",                  "stars": 3, "price_per_night": 30,  "rating": 4.0, "amenities": ["wifi", "restaurant", "parking"]},
        {"name": "XVA Art Hotel",                                       "stars": 3, "price_per_night": 65,  "rating": 4.2, "amenities": ["courtyard", "art-gallery", "breakfast"]},
        {"name": "JW Marriott Marquis Dubai",                           "stars": 5, "price_per_night": 150, "rating": 4.6, "amenities": ["pool", "spa", "multiple-restaurants", "gym"]},
    ],
    "paris": [
        {"name": "Hôtel Joke – Astotel",                                "stars": 4, "price_per_night": 180, "rating": 4.5, "amenities": ["breakfast", "bar", "wifi", "gym"]},
        {"name": "ibis Paris Tour Eiffel",                              "stars": 3, "price_per_night": 85,  "rating": 3.8, "amenities": ["wifi", "restaurant", "bar"]},
        {"name": "Generator Paris Hostel",                               "stars": 2, "price_per_night": 35,  "rating": 4.0, "amenities": ["bar", "wifi", "common-room"]},
        {"name": "Hotel Le Marais Boutique",                             "stars": 4, "price_per_night": 220, "rating": 4.4, "amenities": ["breakfast", "concierge", "wifi"]},
        {"name": "Citadines Saint-Germain-des-Prés",                     "stars": 3, "price_per_night": 130, "rating": 4.1, "amenities": ["kitchen", "wifi", "laundry"]},
    ],
    "london": [
        {"name": "Premier Inn London County Hall",                      "stars": 3, "price_per_night": 110, "rating": 4.3, "amenities": ["restaurant", "bar", "wifi"]},
        {"name": "The Hoxton Shoreditch",                               "stars": 4, "price_per_night": 160, "rating": 4.4, "amenities": ["restaurant", "bar", "coworking", "wifi"]},
        {"name": "YHA London Central Hostel",                            "stars": 2, "price_per_night": 30,  "rating": 3.9, "amenities": ["wifi", "common-room", "laundry"]},
        {"name": "The Ritz London",                                      "stars": 5, "price_per_night": 550, "rating": 4.8, "amenities": ["spa", "fine-dining", "butler", "pool"]},
        {"name": "Travelodge London Central",                            "stars": 3, "price_per_night": 65,  "rating": 3.7, "amenities": ["wifi", "breakfast"]},
    ],
    "new york": [
        {"name": "Pod 51 Hotel Manhattan",                              "stars": 3, "price_per_night": 95,  "rating": 4.0, "amenities": ["rooftop", "wifi", "laundry"]},
        {"name": "The Manhattan Club",                                   "stars": 4, "price_per_night": 250, "rating": 4.2, "amenities": ["gym", "concierge", "wifi", "kitchen"]},
        {"name": "HI NYC Hostel",                                        "stars": 2, "price_per_night": 45,  "rating": 4.1, "amenities": ["breakfast", "wifi", "common-room"]},
        {"name": "The Plaza Hotel",                                      "stars": 5, "price_per_night": 700, "rating": 4.7, "amenities": ["spa", "fine-dining", "butler", "pool"]},
        {"name": "Moxy NYC East Village",                                "stars": 4, "price_per_night": 140, "rating": 4.3, "amenities": ["bar", "gym", "wifi", "coworking"]},
    ],
    "tokyo": [
        {"name": "APA Hotel Shinjuku Gyoenmae",                         "stars": 3, "price_per_night": 65,  "rating": 4.0, "amenities": ["wifi", "laundry", "vending-machines"]},
        {"name": "Citadines Central Shinjuku",                           "stars": 4, "price_per_night": 120, "rating": 4.3, "amenities": ["kitchen", "wifi", "gym", "laundry"]},
        {"name": "Khaosan Tokyo Hostel",                                 "stars": 2, "price_per_night": 25,  "rating": 4.2, "amenities": ["wifi", "common-room", "kitchen"]},
        {"name": "Park Hyatt Tokyo",                                     "stars": 5, "price_per_night": 400, "rating": 4.6, "amenities": ["pool", "spa", "fine-dining", "gym", "view"]},
        {"name": "Toyoko Inn Tokyo Station",                             "stars": 3, "price_per_night": 50,  "rating": 3.9, "amenities": ["wifi", "breakfast", "laundry"]},
    ],
    "bangkok": [
        {"name": "Sukhumvit Boutique Hotel",                             "stars": 4, "price_per_night": 45,  "rating": 4.2, "amenities": ["pool", "gym", "wifi", "breakfast"]},
        {"name": "Lub d Bangkok Hostel",                                 "stars": 2, "price_per_night": 12,  "rating": 4.4, "amenities": ["rooftop", "bar", "wifi", "common-room"]},
        {"name": "Mandarin Oriental Bangkok",                            "stars": 5, "price_per_night": 250, "rating": 4.9, "amenities": ["spa", "pool", "fine-dining", "butler"]},
        {"name": "Nova Platinum Hotel",                                  "stars": 3, "price_per_night": 25,  "rating": 4.0, "amenities": ["wifi", "laundry", "breakfast"]},
        {"name": "Centre Point Pratunam",                                "stars": 4, "price_per_night": 35,  "rating": 4.1, "amenities": ["pool", "wifi", "kitchen", "laundry"]},
    ],
    "goa": [
        {"name": "The St. Regis Goa Resort",                             "stars": 5, "price_per_night": 200, "rating": 4.7, "amenities": ["pool", "spa", "beach-access", "fine-dining"]},
        {"name": "Martin's Comfort Inn",                                  "stars": 3, "price_per_night": 30,  "rating": 4.0, "amenities": ["wifi", "pool", "restaurant"]},
        {"name": "Casa Vagator Boutique Villa",                          "stars": 4, "price_per_night": 80,  "rating": 4.4, "amenities": ["pool", "breakfast", "wifi", "garden"]},
        {"name": "Zostel Goa Hostel",                                    "stars": 2, "price_per_night": 12,  "rating": 4.2, "amenities": ["wifi", "common-room", "cafe"]},
        {"name": "The Lalit Golf & Spa Resort Goa",                      "stars": 5, "price_per_night": 120, "rating": 4.5, "amenities": ["pool", "spa", "golf", "beach-access"]},
    ],
    "mumbai": [
        {"name": "The Taj Mahal Palace Mumbai",                          "stars": 5, "price_per_night": 250, "rating": 4.8, "amenities": ["pool", "spa", "fine-dining", "heritage"]},
        {"name": "Hotel Marine Plaza",                                   "stars": 4, "price_per_night": 80,  "rating": 4.2, "amenities": ["gym", "restaurant", "wifi", "sea-view"]},
        {"name": "FabHotel Prime Residency",                             "stars": 3, "price_per_night": 30,  "rating": 4.0, "amenities": ["wifi", "breakfast", "laundry"]},
        {"name": "Backpacker Panda Mumbai",                              "stars": 2, "price_per_night": 10,  "rating": 4.0, "amenities": ["wifi", "common-room", "cafe"]},
        {"name": "ITC Grand Central Mumbai",                             "stars": 5, "price_per_night": 150, "rating": 4.6, "amenities": ["pool", "spa", "multiple-restaurants", "gym"]},
    ],
    "delhi": [
        {"name": "The Imperial New Delhi",                               "stars": 5, "price_per_night": 180, "rating": 4.7, "amenities": ["pool", "spa", "heritage", "fine-dining"]},
        {"name": "Bloomrooms Connaught Place",                           "stars": 3, "price_per_night": 40,  "rating": 4.2, "amenities": ["wifi", "cafe", "laundry"]},
        {"name": "The LaLiT New Delhi",                                  "stars": 5, "price_per_night": 100, "rating": 4.4, "amenities": ["pool", "spa", "multiple-restaurants", "gym"]},
        {"name": "OYO Townhouse Paharganj",                              "stars": 3, "price_per_night": 18,  "rating": 3.6, "amenities": ["wifi", "breakfast"]},
        {"name": "Zostel Delhi Hostel",                                  "stars": 2, "price_per_night": 8,   "rating": 4.1, "amenities": ["wifi", "common-room", "rooftop"]},
    ],
    "singapore": [
        {"name": "Marina Bay Sands",                                     "stars": 5, "price_per_night": 350, "rating": 4.6, "amenities": ["infinity-pool", "casino", "spa", "fine-dining"]},
        {"name": "Hotel Boss",                                           "stars": 3, "price_per_night": 60,  "rating": 3.8, "amenities": ["wifi", "pool", "restaurant"]},
        {"name": "The Pod Boutique Capsule Hotel",                        "stars": 3, "price_per_night": 35,  "rating": 4.3, "amenities": ["wifi", "common-room", "locker"]},
        {"name": "YOTEL Singapore Orchard Road",                         "stars": 4, "price_per_night": 130, "rating": 4.2, "amenities": ["pool", "gym", "wifi", "bar"]},
    ],
    "sydney": [
        {"name": "Sydney Harbour Marriott",                              "stars": 5, "price_per_night": 240, "rating": 4.5, "amenities": ["pool", "gym", "waterfront", "multiple-restaurants"]},
        {"name": "Wake Up! Sydney Central Hostel",                        "stars": 2, "price_per_night": 30,  "rating": 4.0, "amenities": ["wifi", "bar", "common-room", "breakfast"]},
        {"name": "Meriton Suites World Tower",                           "stars": 4, "price_per_night": 150, "rating": 4.4, "amenities": ["pool", "spa", "gym", "kitchen"]},
        {"name": "ibis Sydney Barangaroo",                               "stars": 3, "price_per_night": 90,  "rating": 4.0, "amenities": ["wifi", "restaurant", "gym"]},
    ],
}


async def hotel_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    destination = state.get("destination", "Unknown")
    budget = float(state.get("budget", 500))
    currency = state.get("currency", "USD")

    dest_key = destination.lower().strip()
    if dest_key in HOTEL_DB:
        base_hotels = HOTEL_DB[dest_key]
    else:
        base_hotels = _default_hotels(destination)

    rate = await get_exchange_rate(currency)
    budget_usd = budget / rate if rate > 0 else 500
    num_days = max(float(state.get("duration_days", 7)), 1)
    daily_budget_usd = budget_usd / num_days
    trip_type = state.get("routing_decision", "standard")
    hotel_share = {"budget": 0.3, "standard": 0.4, "luxury": 0.55}.get(trip_type, 0.4)
    max_price = int(daily_budget_usd * hotel_share)

    affordable = [h for h in base_hotels if h["price_per_night"] <= max_price]
    if not affordable:
        affordable = [min(base_hotels, key=lambda h: h["price_per_night"])]

    affordable.sort(key=lambda h: h["rating"], reverse=True)

    for h in affordable:
        h["value_score"] = round(h["rating"] / (h["price_per_night"] / 100), 2)

    trace = state.get("execution_trace", [])
    return {
        **state,
        "hotels": affordable,
        "execution_trace": trace + ["hotel_tool"],
    }
