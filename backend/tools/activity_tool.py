"""
Activity Tool — zero AI calls.
Returns a curated list of activities specific to the destination,
filtered by user preferences and budget. Templates work for ANY city.
"""

from typing import Any, Dict, List


def _build_default_pool(destination: str) -> List[Dict[str, Any]]:
    d = destination
    return [
        # ── Culture / History ──
        {"name": f"Visit {d} National Museum",           "category": "culture",    "cost": 15,  "duration_hours": 3,  "indoor": True,  "description": f"Explore the rich history and art collections at {d}'s premier museum"},
        {"name": f"Guided Walking Tour of {d} Old Town",   "category": "culture",    "cost": 20,  "duration_hours": 3,  "indoor": False, "description": f"Stroll through historic streets with a local guide"},
        {"name": f"{d} Art Gallery Walk",                  "category": "art",        "cost": 10,  "duration_hours": 2,  "indoor": True,  "description": f"Browse contemporary and classic art in {d}'s gallery district"},
        {"name": f"{d} Historical Landmarks Tour",         "category": "history",    "cost": 25,  "duration_hours": 4,  "indoor": False, "description": f"Visit the most iconic historical sites in {d}"},

        # ── Food ──
        {"name": f"Street Food Tour of {d}",               "category": "food",       "cost": 25,  "duration_hours": 3,  "indoor": False, "description": f"Sample {d}'s best street food with a knowledgeable guide"},
        {"name": f"Cooking Class at {d} Culinary Institute", "category": "food",    "cost": 55,  "duration_hours": 4,  "indoor": True,  "description": f"Learn to cook authentic local dishes from expert chefs"},
        {"name": f"Local Market Food Walk in {d}",         "category": "food",       "cost": 15,  "duration_hours": 2,  "indoor": False, "description": f"Taste fresh produce and local specialties at {d}'s markets"},
        {"name": f"Dinner at Traditional {d} Restaurant",  "category": "food",       "cost": 40,  "duration_hours": 2,  "indoor": True,  "description": f"Enjoy an authentic local meal at a beloved {d} eatery"},

        # ── Adventure ──
        {"name": f"{d} Sunset Hike",                       "category": "adventure",  "cost": 15,  "duration_hours": 3,  "indoor": False, "description": f"Guided hike to the best sunset viewpoint in {d}"},
        {"name": f"Bicycle Tour of {d}",                   "category": "adventure",  "cost": 30,  "duration_hours": 4,  "indoor": False, "description": f"Explore {d}'s highlights by bike with a small group"},
        {"name": f"Kayaking along {d} Waterfront",         "category": "adventure",  "cost": 45,  "duration_hours": 3,  "indoor": False, "description": f"Paddle along the scenic coastline or river of {d}"},
        {"name": f"{d} Nature Reserve Walk",               "category": "nature",    "cost": 10,  "duration_hours": 3,  "indoor": False, "description": f"Discover local flora and fauna in {d}'s nature reserve"},

        # ── Shopping ──
        {"name": f"{d} Souk & Market Tour",                "category": "shopping",   "cost": 0,   "duration_hours": 3,  "indoor": False, "description": f"Wander through {d}'s most vibrant traditional markets"},
        {"name": f"{d} Shopping District Exploration",     "category": "shopping",   "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": f"Browse {d}'s main shopping streets and malls"},

        # ── Nature / Relaxation ──
        {"name": f"Morning Yoga at {d} Park",              "category": "relaxation", "cost": 10,  "duration_hours": 2,  "indoor": False, "description": f"Start the day with outdoor yoga in {d}'s best park"},
        {"name": f"Spa & Wellness at {d} Retreat",         "category": "relaxation", "cost": 65,  "duration_hours": 3,  "indoor": True,  "description": f"Unwind with a massage and spa treatments in central {d}"},
        {"name": f"{d} Seaside Promenade Stroll",          "category": "relaxation", "cost": 0,   "duration_hours": 2,  "indoor": False, "description": f"Leisurely walk along {d}'s waterfront promenade"},

        # ── Nightlife ──
        {"name": f"{d} Rooftop Bar Evening",               "category": "nightlife",  "cost": 25,  "duration_hours": 3,  "indoor": True,  "description": f"Drinks with panoramic views at {d}'s best rooftop bar"},
        {"name": f"{d} Live Music Night",                  "category": "nightlife",  "cost": 20,  "duration_hours": 3,  "indoor": True,  "description": f"Enjoy local bands and artists at a popular {d} venue"},

        # ── Photography / Experiences ──
        {"name": f"{d} Sunrise Photography Tour",          "category": "culture",    "cost": 20,  "duration_hours": 3,  "indoor": False, "description": f"Capture {d}'s beauty at golden hour with a pro photographer"},
        {"name": f"{d} Ferry or River Cruise",             "category": "adventure",  "cost": 35,  "duration_hours": 2,  "indoor": False, "description": f"See {d} from the water on a scenic boat ride"},
    ]


# ── Specific city overrides with REAL venue names ─────────────────────────
ACTIVITY_DB: Dict[str, List[Dict[str, Any]]] = {
    "dubai": [
        {"name": "Burj Khalifa Observation Deck",            "category": "culture",   "cost": 40,  "duration_hours": 2,  "indoor": True,  "description": "Stunning panoramic views from the world's tallest building"},
        {"name": "Dubai Marina Walk",                         "category": "relaxation","cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Scenic waterfront promenade lined with cafes and shops"},
        {"name": "Kite Beach Day",                            "category": "nature",    "cost": 0,   "duration_hours": 4,  "indoor": False, "description": "Popular public beach with food trucks and water sports"},
        {"name": "Old Dubai & Gold Souk Tour",                "category": "history",   "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Wander through historic Al Fahidi and traditional markets"},
        {"name": "Dinner at PUBLIC Dubai",                    "category": "food",      "cost": 25,  "duration_hours": 2,  "indoor": True,  "description": "Casual dining with Burj Khalifa views in Downtown Dubai"},
        {"name": "SALT Kite Beach",                           "category": "food",      "cost": 12,  "duration_hours": 1,  "indoor": False, "description": "Famous gourmet smash burgers right on Kite Beach"},
        {"name": "Naughty Pizza Dubai",                       "category": "food",      "cost": 20,  "duration_hours": 2,  "indoor": True,  "description": "Popular pizza spot in JLT known for creative toppings"},
        {"name": "Desert Safari & Dune Bashing",              "category": "adventure", "cost": 55,  "duration_hours": 6,  "indoor": False, "description": "Thrilling desert drive with BBQ dinner and cultural show"},
        {"name": "Mall of the Emirates Visit",                 "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "World-class shopping with indoor ski slope and dining"},
        {"name": "Jumeirah Beach Walk",                       "category": "relaxation","cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Picturesque beachfront path past luxury resorts"},
        {"name": "Pickl JLT",                                 "category": "food",      "cost": 18,  "duration_hours": 1,  "indoor": True,  "description": "Trendy fried chicken sandwich spot in Jumeirah Lakes Towers"},
        {"name": "Dubai Fountain Show",                       "category": "culture",   "cost": 0,   "duration_hours": 1,  "indoor": False, "description": "Free nightly water, music and light show at Burj Khalifa Lake"},
        {"name": "Museum of the Future",                      "category": "culture",   "cost": 35,  "duration_hours": 3,  "indoor": True,  "description": "Immersive exhibitions exploring tomorrow's innovations"},
        {"name": "La Mer Beachfront",                         "category": "relaxation","cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Chic beachside development with dining and water activities"},
        {"name": "Blu Pizzeriá Dubai",                        "category": "food",      "cost": 22,  "duration_hours": 2,  "indoor": True,  "description": "Sourdough pizza with Burj Khalifa views at Souk Al Bahar"},
        {"name": "Dubai Creek Abra Ride",                     "category": "adventure", "cost": 3,   "duration_hours": 1,  "indoor": False, "description": "Traditional boat crossing Dubai Creek for 1 AED"},
        {"name": "The Dubai Mall",                            "category": "shopping",  "cost": 0,   "duration_hours": 4,  "indoor": True,  "description": "Massive shopping and entertainment complex with aquarium"},
        {"name": "Shake Shack Dubai Mall",                    "category": "food",      "cost": 15,  "duration_hours": 1,  "indoor": True,  "description": "Popular American burger chain at The Dubai Mall food court"},
        {"name": "Alserkal Avenue Arts District",             "category": "art",       "cost": 0,   "duration_hours": 2,  "indoor": True,  "description": "Contemporary art galleries and creative spaces in Al Quoz"},
        {"name": "Spa at Palazzo Versace",                    "category": "relaxation","cost": 120, "duration_hours": 3,  "indoor": True,  "description": "Luxury spa treatments at the Palazzo Versace Dubai hotel"},
    ],

    "paris": [
        {"name": "Eiffel Tower Summit Visit",                 "category": "culture",   "cost": 30,  "duration_hours": 2,  "indoor": False, "description": "Ascend the iconic iron tower for panoramic Paris views"},
        {"name": "Louvre Museum",                             "category": "culture",   "cost": 22,  "duration_hours": 4,  "indoor": True,  "description": "World's largest art museum housing the Mona Lisa"},
        {"name": "Montmartre Walking Tour",                   "category": "culture",   "cost": 15,  "duration_hours": 3,  "indoor": False, "description": "Explore the artistic hilltop neighborhood and Sacré-Cœur"},
        {"name": "Seine River Evening Cruise",                "category": "adventure", "cost": 20,  "duration_hours": 2,  "indoor": False, "description": "Romantic boat ride past Notre-Dame and the Eiffel Tower"},
        {"name": "Le Marais Food Walk",                       "category": "food",      "cost": 35,  "duration_hours": 3,  "indoor": False, "description": "Taste Parisian specialties in the trendy Le Marais district"},
        {"name": "Luxembourg Gardens Picnic",                 "category": "relaxation","cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Beautiful formal gardens perfect for a relaxing afternoon"},
        {"name": "Musée d'Orsay",                             "category": "art",       "cost": 16,  "duration_hours": 3,  "indoor": True,  "description": "Impressionist masterpieces housed in a former railway station"},
        {"name": "Bouillon Pigalle Dinner",                   "category": "food",      "cost": 25,  "duration_hours": 2,  "indoor": True,  "description": "Traditional French cuisine at a beloved Parisian bistro"},
        {"name": "Champs-Élysées & Arc de Triomphe",          "category": "shopping",  "cost": 13,  "duration_hours": 3,  "indoor": False, "description": "Famous avenue and monumental arch with rooftop views"},
        {"name": "Catacombs of Paris Tour",                   "category": "history",   "cost": 29,  "duration_hours": 2,  "indoor": True,  "description": "Underground ossuaries holding millions of Parisian remains"},
    ],

    "london": [
        {"name": "British Museum",                            "category": "culture",   "cost": 0,   "duration_hours": 4,  "indoor": True,  "description": "World-class free museum with the Rosetta Stone and Elgin Marbles"},
        {"name": "Tower of London & Crown Jewels",            "category": "history",   "cost": 35,  "duration_hours": 3,  "indoor": True,  "description": "Historic castle home to the Crown Jewels and Beefeaters"},
        {"name": "Borough Market Food Tour",                  "category": "food",      "cost": 20,  "duration_hours": 2,  "indoor": False, "description": "London's oldest food market with artisanal vendors"},
        {"name": "Hyde Park Walk & Serpentine",              "category": "nature",    "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Royal park with lake, gardens and the Serpentine Galleries"},
        {"name": "Camden Market",                             "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Eclectic market with vintage fashion, street food and crafts"},
        {"name": "West End Theatre Show",                     "category": "nightlife", "cost": 45,  "duration_hours": 3,  "indoor": True,  "description": "World-famous theatre district with musicals and plays"},
        {"name": "Tate Modern Gallery",                       "category": "art",       "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Contemporary art in a converted Bankside power station"},
        {"name": "Dishoom Shoreditch Dinner",                 "category": "food",      "cost": 28,  "duration_hours": 2,  "indoor": True,  "description": "Buzzy Bombay-style café serving Indian comfort food"},
        {"name": "Thames River Cruise to Greenwich",          "category": "adventure", "cost": 18,  "duration_hours": 3,  "indoor": False, "description": "Boat ride to Greenwich for the Meridian Line and maritime museum"},
        {"name": "Sky Garden Viewing Platform",               "category": "culture",   "cost": 0,   "duration_hours": 1,  "indoor": True,  "description": "Free public garden and observation deck atop the Walkie-Talkie"},
    ],

    "new york": [
        {"name": "Statue of Liberty & Ellis Island",          "category": "history",   "cost": 24,  "duration_hours": 5,  "indoor": False, "description": "Ferry to Lady Liberty and the immigrant museum"},
        {"name": "Metropolitan Museum of Art",                "category": "art",       "cost": 30,  "duration_hours": 4,  "indoor": True,  "description": "World's greatest art collection spanning 5,000 years"},
        {"name": "Central Park Walk & Boat Rental",          "category": "nature",    "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Explore NYC's iconic urban park with lakes and trails"},
        {"name": "Katz's Delicatessen Lunch",                 "category": "food",      "cost": 20,  "duration_hours": 1,  "indoor": True,  "description": "Legendary Lower East Side deli famous for pastrami sandwiches"},
        {"name": "Broadway Show",                             "category": "nightlife", "cost": 60,  "duration_hours": 3,  "indoor": True,  "description": "World-class theatre performance in the Theater District"},
        {"name": "Brooklyn Bridge Walk to DUMBO",             "category": "adventure", "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Scenic walk across the iconic bridge to trendy DUMBO"},
        {"name": "Chelsea Market & High Line",                "category": "food",      "cost": 10,  "duration_hours": 3,  "indoor": False, "description": "Food hall and elevated park on Manhattan's West Side"},
        {"name": "9/11 Memorial & Museum",                    "category": "history",   "cost": 33,  "duration_hours": 3,  "indoor": True,  "description": "Solemn tribute and museum at the World Trade Center site"},
        {"name": "Soho Shopping Walk",                        "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Cast-iron architecture district with boutiques and galleries"},
        {"name": "Joe's Pizza Greenwich Village",             "category": "food",      "cost": 5,   "duration_hours": 1,  "indoor": True,  "description": "Classic NYC slice since 1975 — a true New York institution"},
    ],

    "tokyo": [
        {"name": "Senso-ji Temple & Asakusa",                 "category": "culture",   "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Tokyo's oldest temple in the traditional Asakusa district"},
        {"name": "Tsukiji Outer Market Food Walk",            "category": "food",      "cost": 20,  "duration_hours": 2,  "indoor": False, "description": "Fresh seafood and street food at Tokyo's famous market"},
        {"name": "Shibuya Crossing & Hachiko Statue",         "category": "culture",   "cost": 0,   "duration_hours": 1,  "indoor": False, "description": "World's busiest pedestrian crossing and beloved dog statue"},
        {"name": "Meiji Shrine & Yoyogi Park",               "category": "nature",    "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Serene Shinto shrine surrounded by vast forested park"},
        {"name": "Akihabara Electric Town",                   "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Anime, manga and electronics mecca in central Tokyo"},
        {"name": "Ichiran Ramen Shibuya",                     "category": "food",      "cost": 15,  "duration_hours": 1,  "indoor": True,  "description": "Famous solo-booth tonkotsu ramen experience"},
        {"name": "teamLab Borderless Digital Art",            "category": "art",       "cost": 35,  "duration_hours": 3,  "indoor": True,  "description": "Immersive digital art installation in Azabudai Hills"},
        {"name": "Shinjuku Gyoen National Garden",            "category": "relaxation","cost": 5,   "duration_hours": 2,  "indoor": False, "description": "Beautiful Japanese landscape garden in central Shinjuku"},
        {"name": "Odaiba Waterfront & Rainbow Bridge",        "category": "adventure", "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Futuristic island with skyline views and entertainment"},
        {"name": "Golden Gai Bar Hopping",                    "category": "nightlife", "cost": 30,  "duration_hours": 3,  "indoor": True,  "description": "Tiny themed bars in Shinjuku's legendary alleyway district"},
    ],

    "bangkok": [
        {"name": "Grand Palace & Wat Phra Kaew",              "category": "culture",   "cost": 15,  "duration_hours": 3,  "indoor": False, "description": "Thailand's most sacred temple and former royal palace"},
        {"name": "Chatuchak Weekend Market",                  "category": "shopping",  "cost": 0,   "duration_hours": 4,  "indoor": False, "description": "One of the world's largest weekend markets with 8,000 stalls"},
        {"name": "Yaowarat (Chinatown) Street Food Walk",     "category": "food",      "cost": 10,  "duration_hours": 3,  "indoor": False, "description": "Bangkok's best street food in the vibrant Chinatown district"},
        {"name": "Wat Arun (Temple of Dawn)",                 "category": "culture",   "cost": 3,   "duration_hours": 1,  "indoor": False, "description": "Iconic riverside temple with stunning porcelain decoration"},
        {"name": "Khao San Road Evening",                     "category": "nightlife", "cost": 8,   "duration_hours": 3,  "indoor": False, "description": "Backpacker hub with budget bars, street food and shopping"},
        {"name": "Thai Cooking Class with Market Tour",       "category": "food",      "cost": 30,  "duration_hours": 4,  "indoor": True,  "description": "Shop at a local market then cook authentic Thai dishes"},
        {"name": "Lumphini Park Morning Walk",                "category": "nature",    "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Green oasis in the heart of Bangkok with monitor lizards"},
        {"name": "Bangkok River Taxi Adventure",             "category": "adventure", "cost": 3,   "duration_hours": 2,  "indoor": False, "description": "Hop on the Chao Phraya express boat for a local commute"},
        {"name": "Jim Thompson House Museum",                 "category": "history",   "cost": 8,   "duration_hours": 2,  "indoor": True,  "description": "Traditional Thai house and silk museum of the American architect"},
        {"name": "Rooftop Bar at Octave Sukhumvit",           "category": "nightlife", "cost": 15,  "duration_hours": 2,  "indoor": True,  "description": "360-degree Bangkok skyline views with affordable drinks"},
    ],

    "goa": [
        {"name": "Baga Beach & Tito's Lane",                  "category": "nature",    "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Popular North Goa beach with water sports and nightlife"},
        {"name": "Old Goa Churches Tour",                     "category": "history",   "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "UNESCO-listed Basilica of Bom Jesus and Sé Cathedral"},
        {"name": "Anjuna Flea Market",                        "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": False, "description": "Iconic Wednesday market with hippie vibes and handicrafts"},
        {"name": "Fisherman's Wharf Lunch",                   "category": "food",      "cost": 20,  "duration_hours": 2,  "indoor": True,  "description": "Famous Goan seafood restaurant overlooking the river"},
        {"name": "Spice Plantation Tour",                     "category": "adventure", "cost": 12,  "duration_hours": 3,  "indoor": False, "description": "Guided walk through a tropical spice farm with traditional lunch"},
        {"name": "Palolem Beach Kayaking",                    "category": "adventure", "cost": 15,  "duration_hours": 2,  "indoor": False, "description": "Kayak through the scenic Palolem Bay in South Goa"},
        {"name": "Sunset at Chapora Fort",                    "category": "culture",   "cost": 0,   "duration_hours": 1,  "indoor": False, "description": "Famous sunset viewpoint from the 'Dil Chahta Hai' fort"},
        {"name": "Vinzul Restaurant & Bar",                   "category": "food",      "cost": 12,  "duration_hours": 2,  "indoor": True,  "description": "Affordable Goan-Portuguese fusion in Assagao"},
        {"name": "Dudhsagar Waterfalls Trek",                 "category": "adventure", "cost": 25,  "duration_hours": 6,  "indoor": False, "description": "Trek to one of India's tallest waterfalls in the Western Ghats"},
        {"name": "Mandovi River Sunset Cruise",               "category": "relaxation","cost": 10,  "duration_hours": 2,  "indoor": False, "description": "Relaxing evening cruise on the Mandovi with live music"},
    ],

    "mumbai": [
        {"name": "Gateway of India & Colaba Walk",            "category": "history",   "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Iconic arch monument overlooking the Arabian Sea"},
        {"name": "Marine Drive Evening Walk",                 "category": "relaxation","cost": 0,   "duration_hours": 1,  "indoor": False, "description": "The Queen's Necklace — scenic coastal promenade at sunset"},
        {"name": "Shree Siddhivinayak Temple",                "category": "culture",   "cost": 0,   "duration_hours": 1,  "indoor": True,  "description": "Mumbai's most revered Ganesh temple in Prabhadevi"},
        {"name": "Bademiya Colaba Dinner",                    "category": "food",      "cost": 8,   "duration_hours": 1,  "indoor": True,  "description": "Legendary street-side kebab joint serving Mumbai since 1970"},
        {"name": "Crawford Market & Kala Ghoda Art District", "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Historic market and surrounding art galleries in South Mumbai"},
        {"name": "Dharavi Slum Tour",                         "category": "culture",   "cost": 10,  "duration_hours": 3,  "indoor": False, "description": "Eye-opening guided tour of Asia's largest slum's recycling industry"},
        {"name": "Elephanta Caves Ferry",                     "category": "adventure", "cost": 15,  "duration_hours": 5,  "indoor": False, "description": "UNESCO rock-cut temple caves on Elephanta Island"},
        {"name": "Sassanian Dock Bar & Kitchen",              "category": "food",      "cost": 22,  "duration_hours": 2,  "indoor": True,  "description": "Trendy seafood spot on the water at the Sassanian Dock"},
        {"name": "Bandra-Worli Sea Link & Bandstand",         "category": "adventure", "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "Drive/walk past Mumbai's engineering marvel and promenade"},
        {"name": "Prithvi Theatre Cafe Evening",              "category": "nightlife", "cost": 8,   "duration_hours": 3,  "indoor": True,  "description": "Iconic cafe-theatre in Juhu with open-air seating and performances"},
    ],

    "delhi": [
        {"name": "Red Fort & Chandni Chowk Rickshaw Ride",    "category": "history",   "cost": 5,   "duration_hours": 3,  "indoor": False, "description": "UNESCO fort and chaotic old Delhi market by rickshaw"},
        {"name": "Qutub Minar Complex",                       "category": "history",   "cost": 7,   "duration_hours": 2,  "indoor": False, "description": "India's tallest minaret and UNESCO World Heritage site"},
        {"name": "India Gate & Rajpath Walk",                 "category": "culture",   "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "War memorial and ceremonial boulevard in New Delhi"},
        {"name": "Karim's Jama Masjid Lunch",                 "category": "food",      "cost": 6,   "duration_hours": 1,  "indoor": True,  "description": "Legendary Mughlai restaurant near Jama Masjid since 1913"},
        {"name": "Hauz Khas Village Exploration",             "category": "nightlife", "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Bohemian village with boutiques, cafés and a historic lake"},
        {"name": "Humayun's Tomb",                            "category": "history",   "cost": 5,   "duration_hours": 2,  "indoor": False, "description": "UNESCO Persian garden tomb that inspired the Taj Mahal"},
        {"name": "Dilli Haat Market Lunch",                   "category": "food",      "cost": 10,  "duration_hours": 2,  "indoor": False, "description": "Open-air craft market with regional Indian street food stalls"},
        {"name": "Lodhi Art District Walk",                   "category": "art",       "cost": 0,   "duration_hours": 2,  "indoor": False, "description": "India's largest public art district with 50+ murals"},
        {"name": "Connaught Place Shopping Circuit",          "category": "shopping",  "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Georgian-style colonial arcade with mainstream and luxury brands"},
        {"name": "Akshardham Temple Light Show",              "category": "culture",   "cost": 0,   "duration_hours": 3,  "indoor": True,  "description": "Stunning Hindu temple complex with evening water show"},
    ],
}


async def activity_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    destination = state.get("destination", "")
    preferences = state.get("preferences", [])
    budget = float(state.get("budget", 500))
    weather = state.get("weather", {})
    has_bad_weather = weather.get("any_bad_weather", False)

    visit_all_places = any("all" in str(p).lower() for p in preferences)

    dest_key = destination.lower().strip()
    if dest_key in ACTIVITY_DB:
        pool = ACTIVITY_DB[dest_key]
    else:
        pool = _build_default_pool(destination)

    if budget >= 999999 or visit_all_places:
        max_activity_cost = float('inf')
    else:
        max_activity_cost = budget * 0.25

    filtered = []
    for act in pool:
        if max_activity_cost != float('inf') and act["cost"] > max_activity_cost:
            continue

        if has_bad_weather and not act["indoor"]:
            act["weather_warning"] = True
        else:
            act["weather_warning"] = False

        act["recommended"] = any(pref.lower() in act["category"] for pref in preferences)

        if visit_all_places:
            act["recommended"] = True

        filtered.append(act)

    filtered.sort(key=lambda a: (not a["recommended"], a["cost"]))

    trace = state.get("execution_trace", [])
    return {
        **state,
        "activities": filtered,
        "execution_trace": trace + ["activity_tool"],
    }
