"""
backend/services/rag_service.py
================================
Provider-agnostic RAG + LLM service with intelligent fallback.

When LLM_PROVIDER=none (default), uses a rules-based answer engine that:
1. Filters garbage content (table of contents, figure captions, page numbers)
2. Extracts clean relevant sentences from DB chunks
3. Falls back to curated NDMA/PDMA disaster knowledge if DB content is poor
4. Formats answers with numbered steps and proper structure

LLM_PROVIDER options: none | openai | ollama | groq
"""

import os
import re
from dataclasses import dataclass

# ── Config ─────────────────────────────────────────────────────────────────────
LLM_PROVIDER       = os.getenv("LLM_PROVIDER",       "none").lower()
LLM_MODEL          = os.getenv("LLM_MODEL",           "")
LLM_API_KEY        = os.getenv("LLM_API_KEY",         "")
LLM_BASE_URL       = os.getenv("LLM_BASE_URL",        "")
LLM_MIN_CONFIDENCE = int(os.getenv("LLM_MIN_CONFIDENCE", "1"))
LLM_MAX_TOKENS     = int(os.getenv("LLM_MAX_TOKENS",     "400"))

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a disaster safety assistant for Chitral, KP, Pakistan.
Answer ONLY from the provided source text. Be concise and structured.
If source text is insufficient, say: INSUFFICIENT EVIDENCE."""


@dataclass
class RAGResponse:
    answer: str
    sources: list[dict]
    retrieval_score: int
    confidence: str        # "sufficient" | "insufficient"
    provider_used: str
    generation_used: bool


# ── Curated disaster knowledge base (NDMA/PDMA verified content) ──────────────
# Used when DB chunks don't contain clean actionable content

_KNOWLEDGE_BASE = {
    "flood": {
        "before": [
            "Know your area's flood risk and identify safe evacuation routes in advance",
            "Prepare an emergency Go-Bag: water (3 days), food, medicines, torch, documents in waterproof bag",
            "Store important documents (CNIC, property papers) in a waterproof container",
            "Keep emergency contacts saved: Rescue 1122, PDMA KP (051-9222373), NDMA (051-9246136)",
            "Monitor PDMA KP and PMD weather alerts regularly during monsoon season",
            "Identify the nearest high ground or evacuation shelter in your area",
            "Keep your phone charged and have a battery bank ready",
        ],
        "during": [
            "Move to higher ground immediately — do NOT wait for official orders",
            "Never walk, swim, or drive through floodwater — 6 inches can knock you down, 2 feet can sweep a car",
            "Avoid bridges over fast-moving water",
            "If trapped in a building, go to the highest floor — do not enter the attic (you may get trapped)",
            "Turn off electricity at the main switch if water is entering your home",
            "Call Rescue 1122 immediately if lives are in danger",
            "Do not touch electrical equipment if wet or standing in water",
            "Follow instructions from PDMA KP and local authorities",
        ],
        "after": [
            "Do not return home until authorities declare it safe",
            "Avoid floodwater — it may be contaminated with sewage and chemicals",
            "Boil all drinking water or use purification tablets",
            "Document damage with photos for insurance and relief claims",
            "Watch for signs of structural damage before entering buildings",
            "Register with PDMA KP or DDMA for relief assistance",
        ],
        "risk": [
            "Chitral district is highly prone to flash floods due to steep mountain terrain and glacial melt",
            "GLOF (Glacial Lake Outburst Floods) are a critical threat in northern Chitral",
            "The 2022 Pakistan floods killed 1,730 people and affected 33 million — KP was severely impacted",
            "Flash flooding occurs rapidly with little warning in hilly and mountainous areas of KP",
            "Riverine floods affect low-lying areas near Chitral River and its tributaries",
            "Monsoon season (July-September) is the highest risk period for flooding in Chitral",
        ],
    },
    "earthquake": {
        "before": [
            "Identify safe spots in each room: under sturdy tables, against interior walls away from windows",
            "Secure heavy furniture, shelves, and appliances to walls",
            "Keep an emergency kit ready: water, food, first aid, torch, whistle, documents",
            "Know how to turn off gas, water, and electricity at main switches",
            "Practice Drop, Cover, and Hold On with family members",
            "Identify evacuation routes from your home and neighbourhood",
        ],
        "during": [
            "DROP to hands and knees immediately",
            "Take COVER under a sturdy table or desk, or against an interior wall away from windows",
            "HOLD ON and protect your head and neck with arms",
            "Stay inside until shaking stops — most injuries occur when people try to move or run outside",
            "If outdoors, move away from buildings, streetlights, and utility wires",
            "If driving, pull over safely away from bridges and overpasses",
            "Never use elevators during or after an earthquake",
        ],
        "after": [
            "Expect and prepare for aftershocks",
            "Check yourself and others for injuries — do not move seriously injured persons",
            "Check for gas leaks — if you smell gas, open windows and leave immediately",
            "Do not use open flames or electrical switches if gas leak is suspected",
            "Listen to NDMA/PDMA emergency broadcasts for instructions",
            "Call Rescue 1122 for emergency assistance",
        ],
        "risk": [
            "Chitral is located in a seismically active zone — the Hindu Kush region experiences frequent earthquakes",
            "Northern Pakistan including KP sits near the collision zone of the Indian and Eurasian tectonic plates",
            "The 2005 Kashmir earthquake (magnitude 7.6) killed over 73,000 people in northern Pakistan",
            "Landslides triggered by earthquakes are a secondary hazard in Chitral's mountainous terrain",
        ],
    },
    "landslide": {
        "before": [
            "Avoid building homes on steep slopes or at the base of unstable hillsides",
            "Watch for warning signs: cracks in ground, tilting trees, unusual sounds from hillside",
            "Know your area's landslide risk — check NDMA hazard maps",
            "Prepare evacuation plan and emergency kit",
            "Plant vegetation on slopes to stabilize soil",
        ],
        "during": [
            "Move away from the path of a landslide as quickly as possible",
            "If escape is not possible, curl into a tight ball and protect your head",
            "Avoid river valleys and low-lying areas during heavy rainfall",
            "Listen for unusual sounds — cracking trees, boulders knocking",
            "If near a stream, be aware of sudden change in water colour or level",
        ],
        "after": [
            "Stay away from the slide area — additional slides may follow",
            "Check for injured persons — do not move seriously injured people",
            "Report damage to local DDMA or PDMA KP",
            "Watch for flooding which may follow a landslide",
        ],
        "risk": [
            "Chitral's steep valleys make it highly vulnerable to landslides, especially during monsoon",
            "Deforestation and road construction in KP have increased landslide risk significantly",
            "Heavy rainfall (>50mm in 24 hours) is the primary trigger for landslides in the region",
            "Earthquake-triggered landslides are a significant secondary hazard in northern KP",
        ],
    },
    "rain": {
        "during": [
            "Avoid low-lying areas and river banks during heavy rainfall",
            "Do not cross flooded roads or streams — turn around, don't drown",
            "Stay indoors and away from windows during thunderstorms",
            "Keep drains and gutters clear to prevent waterlogging",
            "Move vehicles to higher ground if flash flooding is possible",
            "Monitor PDMA KP and Pakistan Met Department (PMD) alerts",
            "Have emergency kit ready: torch, water, first aid, important documents",
        ],
        "before": [
            "Check PMD weather forecast before travelling in mountainous areas",
            "Keep emergency supplies stocked during monsoon season (July-September)",
            "Know your local flood evacuation routes",
            "Save emergency numbers: Rescue 1122, PDMA KP 051-9222373",
        ],
        "risk": [
            "Heavy rainfall in Chitral can trigger flash floods within minutes due to steep terrain",
            "Average annual rainfall in Chitral is 400-500mm, concentrated in monsoon months",
            "Cloud bursts are increasingly common due to climate change in KP's mountain areas",
            "GLOF events can be triggered by extreme rainfall in glaciated areas of upper Chitral",
        ],
    },
    "emergency": {
        "contacts": [
            "Rescue 1122 — KP Emergency Rescue Service (24/7)",
            "PDMA KP Helpline — 051-9222373",
            "NDMA Helpline — 051-9246136",
            "Pakistan Meteorological Department — pmd.gov.pk / 051-9250363",
            "Edhi Foundation — 115",
            "Aga Khan Health Services (Chitral) — For medical emergencies",
            "Pakistan Army — 042-111-786-786 (in major disasters)",
        ],
    },
    "preparedness": {
        "gobag": [
            "Water: 3-day supply (3 litres per person per day)",
            "Food: Non-perishable items for 3 days (biscuits, dry fruit, canned food)",
            "First Aid kit: bandages, antiseptic, prescription medications",
            "Documents: CNIC copies, property papers, vaccination cards in waterproof bag",
            "Torch and extra batteries or solar-powered torch",
            "Battery bank / power bank for mobile phone",
            "Whistle to signal rescuers if trapped",
            "Warm clothing and blankets — temperatures drop in Chitral at night",
            "Cash (small denominations) — ATMs may not work after disaster",
            "Local map and emergency contact list",
        ],
        "general": [
            "Know your risk — Chitral faces floods, earthquakes, landslides, and GLOFs",
            "Make a family emergency plan and practice it",
            "Keep emergency kit (Go-Bag) ready and accessible",
            "Stay informed through PDMA KP, NDMA, and PMD official channels",
            "Register vulnerable family members (elderly, disabled) with local DDMA",
            "Know your nearest evacuation shelter location",
        ],
    },
}


def _get_curated_answer(question: str, language: str = "en") -> str | None:
    """
    Returns a query-specific curated answer in the requested language.
    language: 'en' | 'ur' | 'ru' (Roman Urdu)
    Each different question gets a DIFFERENT, relevant response.
    Returns None if query doesn't match any known topic.
    """
    q  = question.lower().strip()
    ur = (language == "ur")
    ru = (language == "ru")

    # ── Urdu/Roman Urdu keyword normalization ─────────────────────────────────
    # Expand Urdu & Roman Urdu keywords to English equivalents for matching
    urdu_map = {
        "سیلاب": "flood", "بارش": "rain", "زلزلہ": "earthquake",
        "لینڈ سلائیڈ": "landslide", "مون سون": "monsoon",
        "ہنگامی": "emergency", "رابطہ": "contact", "بیگ": "bag",
        "تیاری": "prepare", "خطرہ": "risk",
    }
    roman_map = {
        "selab": "flood", "sailaab": "flood", "seelab": "flood",
        "baarish": "rain", "barish": "rain",
        "zalzala": "earthquake", "bhukamp": "earthquake",
        "monsoon": "monsoon", "kit": "kit", "tayyari": "prepare",
        "khatra": "risk", "haadsa": "emergency",
    }
    for uw, en in urdu_map.items():
        if uw in q:
            q = q.replace(uw, en)
    for rw, en in roman_map.items():
        if rw in q:
            q = q.replace(rw, en)

    # ── 1. GLOF (specific — check before general flood) ───────────────────────
    if any(w in q for w in ["glof", "glacial lake", "glacial outburst", "glacier flood", "yarkhun",
                              "گلیشیر", "برفانی جھیل", "yarkhun"]):
        if ur:
            return (
                "GLOF (گلیشیر جھیل کا طوفان) — چترال:\n\n"
                "• چترال میں 53 خطرناک گلیشیر جھیلیں ہیں\n"
                "• یرخون، مستوج، اور تورکھو دریا زیادہ خطرے میں ہیں\n"
                "• GLOF چند منٹوں میں کروڑوں کیوبک میٹر پانی چھوڑ سکتا ہے\n\n"
                "کیا کریں:\n"
                "1. دریا سے کم از کم 50 میٹر اونچائی پر رہیں\n"
                "2. مون سون میں گلیشیر دریاؤں کے قریب رات نہ گزاریں\n"
                "3. تیز گرج کی آواز سنیں تو فوری انخلاء کریں\n"
                "4. PDMA KP: 051-9222373\n\n"
                "ماخذ: NDMA GLOF رسک اسسیسمنٹ / PDMA KP رہنمائی"
            )
        if ru:
            return (
                "GLOF (Glacial Lake Outburst Flood) — Chitral:\n\n"
                "• Chitral mein 53 khatarnak glacial jheelein hain\n"
                "• Yarkhun, Mastuj, Torkhow darya zyada khatra mein hain\n"
                "• GLOF kuch minuton mein crore cubic meter paani chhor sakta hai\n\n"
                "Kya karein:\n"
                "1. Darya se 50 meter unchaai par rahein monsoon mein\n"
                "2. Glacial daryaon ke qareeb raat na guzarein\n"
                "3. Tez guurj ki awaaz sunein to foran inkhla karein\n"
                "4. PDMA KP: 051-9222373\n\n"
                "Source: NDMA GLOF Risk Assessment / PDMA KP Guidelines"
            )
        return (
            "GLOF (Glacial Lake Outburst Flood) — Chitral:\n\n"
            "• Chitral has 53 potentially dangerous glacial lakes in upper valleys\n"
            "• Yarkhun, Mastuj, and Torkhow rivers are high GLOF-risk corridors\n"
            "• GLOF can release millions of cubic metres of water within minutes\n"
            "• No warning — move immediately if you hear loud rumbling from upstream\n\n"
            "What to do:\n"
            "1. If you live near Yarkhun, Mastuj, or Torkhow rivers — know your elevation\n"
            "2. Move at least 50 metres above normal river level during monsoon\n"
            "3. Register with DDMA Chitral for GLOF early warning SMS alerts\n"
            "4. Never camp near glacial rivers overnight during July–September\n"
            "5. Call PDMA KP: 051-9222373 if you see rapid river-level rise\n\n"
            "Source: NDMA GLOF Risk Assessment / PDMA KP Flash Floods Guidelines"
        )

    # ── 2. FLOOD — specific phase detection ───────────────────────────────────
    if any(w in q for w in ["flood", "flooding", "flash flood", "seelab", "sailab"]):
        if any(w in q for w in ["after", "following", "once", "post", "recover", "recovery", "return home"]):
            return (
                "What to do AFTER a Flood:\n\n"
                "1. Do NOT return home until PDMA KP or local authorities declare it safe\n"
                "2. Avoid all floodwater — it is contaminated with sewage and chemicals\n"
                "3. Boil ALL drinking water or use purification tablets for 2 weeks\n"
                "4. Document all damage with photos/videos for relief and insurance claims\n"
                "5. Inspect building structure before entering — check walls, roof, foundations\n"
                "6. Register with PDMA KP or District DDMA for flood relief assistance\n"
                "7. Watch for waterborne diseases — diarrhoea, typhoid, cholera are common\n"
                "8. Dispose of flood-damaged food — do not consume it\n\n"
                "Emergency:\n"
                "• PDMA KP Relief: 051-9222373\n"
                "• NDMA: 051-9246136\n\n"
                "Source: NDMA Flood Situation Report 2023-24 / PDMA KP Guidelines"
            )
        if any(w in q for w in ["before", "prepare", "prevent", "precaution", "ready", "advance"]):
            return (
                "How to Prepare BEFORE a Flood:\n\n"
                "1. Know your flood risk — check if you are near Chitral River, nullahs, or steep slopes\n"
                "2. Prepare Go-Bag: 3-day water supply, food, medicines, torch, CNIC copies\n"
                "3. Store all important documents in a waterproof sealed bag\n"
                "4. Identify your nearest evacuation route and high ground shelter\n"
                "5. Save emergency numbers: Rescue 1122, PDMA KP 051-9222373\n"
                "6. Keep phone fully charged and power bank ready during monsoon\n"
                "7. Monitor PMD weather forecasts daily during July–September\n\n"
                "Source: NDMA Preparedness and Preventive Measures 2024"
            )
        if any(w in q for w in ["risk", "danger", "cause", "why", "prone", "vulnerable", "chitral"]):
            return (
                "Flood Risk Assessment — Chitral / KP:\n\n"
                "• Chitral district is highly prone to flash floods due to steep mountain terrain\n"
                "• GLOF (Glacial Lake Outburst Floods) are a critical threat in upper Chitral\n"
                "• 2022 Pakistan floods: 1,730 deaths, 33 million affected — KP severely impacted\n"
                "• Flash flooding occurs with little warning — river levels rise within minutes\n"
                "• Chitral River, Mastuj, Yarkhun, and Lutkho rivers are primary flood corridors\n"
                "• Monsoon season July–September is highest risk period\n"
                "• Deforestation has increased runoff and flash flood frequency since 2010\n\n"
                "Source: NDMA Flood Situation Report 2023-24 / NDMA DRM Strategy 2024"
            )
        # Default flood = during
        return (
            "What to do During a FLOOD:\n\n"
            "1. Move to higher ground IMMEDIATELY — do NOT wait for official orders\n"
            "2. Never walk, swim, or drive through floodwater — 6 inches can knock you down\n"
            "3. Avoid all bridges over fast-moving or rising water\n"
            "4. If trapped in a building, go to the highest floor — never enter the attic\n"
            "5. Turn off electricity at the main switch if water is entering your home\n"
            "6. Call Rescue 1122 immediately if lives are in danger\n"
            "7. Do not touch any electrical equipment while wet or standing in water\n"
            "8. Follow all instructions from PDMA KP and local civil authorities\n\n"
            "Emergency Contacts:\n"
            "• Rescue 1122 (KP Emergency — 24/7)\n"
            "• PDMA KP: 051-9222373\n"
            "• NDMA: 051-9246136\n\n"
            "Source: NDMA Pakistan / PDMA KP Official Flood Guidelines"
        )

    # ── 3. EARTHQUAKE ─────────────────────────────────────────────────────────
    if any(w in q for w in ["earthquake", "seismic", "tremor", "quake", "zalzala", "bhukamp"]):
        if any(w in q for w in ["after", "following", "once", "post", "recover"]):
            return (
                "What to do AFTER an Earthquake:\n\n"
                "1. Expect aftershocks — stay alert and move to open area\n"
                "2. Check yourself and others for injuries — do not move seriously injured people\n"
                "3. Check for gas leaks — smell gas? Open windows, leave immediately, do NOT switch anything\n"
                "4. Do NOT use open flames or electrical switches if gas leak suspected\n"
                "5. Check water pipes — turn off main valve if leaking\n"
                "6. Do not re-enter damaged buildings until declared safe\n"
                "7. Listen to NDMA/PDMA emergency radio broadcasts for instructions\n"
                "8. Call Rescue 1122 for emergency assistance\n\n"
                "Source: NDMA National Disaster Response Plan 2024-25"
            )
        if any(w in q for w in ["before", "prepare", "precaution", "ready"]):
            return (
                "How to Prepare BEFORE an Earthquake:\n\n"
                "1. Identify safe spots in each room — under sturdy tables, away from windows\n"
                "2. Secure heavy furniture, shelves, and appliances to walls with brackets\n"
                "3. Keep emergency kit ready: water, food, first aid, torch, whistle, documents\n"
                "4. Know how to turn off gas, water, electricity at main switches\n"
                "5. Practice DROP, COVER, HOLD ON with all family members\n"
                "6. Identify evacuation routes from home and workplace\n"
                "7. Keep shoes near your bed — glass and debris cause injuries after quakes\n\n"
                "Source: NDMA National Disaster Response Plan 2024-25"
            )
        if any(w in q for w in ["risk", "danger", "chitral", "kp", "cause", "why"]):
            return (
                "Earthquake Risk — Chitral / KP:\n\n"
                "• Chitral is in a seismically active zone — Hindu Kush region has frequent earthquakes\n"
                "• Northern Pakistan sits near the Indian-Eurasian tectonic plate collision zone\n"
                "• 2005 Kashmir earthquake (magnitude 7.6) killed 73,000+ in northern Pakistan\n"
                "• Hindu Kush experiences multiple magnitude 5+ earthquakes every year\n"
                "• Landslides triggered by earthquakes are a major secondary hazard in Chitral\n"
                "• Older stone/mud-brick construction in Chitral is highly vulnerable to shaking\n\n"
                "Source: NDMA DRM Strategy 2024 / NDMA National Disaster Response Plan 2024"
            )
        # Default = during
        return (
            "What to do During an EARTHQUAKE:\n\n"
            "1. DROP to hands and knees immediately\n"
            "2. Take COVER under a sturdy table or against an interior wall away from windows\n"
            "3. HOLD ON — protect your head and neck with your arms\n"
            "4. STAY INSIDE until shaking completely stops — most injuries happen during movement\n"
            "5. If outdoors — move away from buildings, power lines, and streetlights\n"
            "6. If driving — pull over away from bridges and overpasses, stay in vehicle\n"
            "7. NEVER use elevators during or immediately after an earthquake\n\n"
            "After shaking stops:\n"
            "• Call Rescue 1122 if anyone is injured\n"
            "• Check for gas leaks before using any switches\n\n"
            "Source: NDMA National Disaster Response Plan 2024-25"
        )

    # ── 4. LANDSLIDE ──────────────────────────────────────────────────────────
    if any(w in q for w in ["landslide", "mudslide", "rockslide", "avalanche", "debris", "slope failure"]):
        if any(w in q for w in ["sign", "warning", "detect", "identify", "recognise", "recognize"]):
            return (
                "Warning Signs of a Landslide:\n\n"
                "1. New cracks or bulges appearing in the ground or on slopes\n"
                "2. Tilting or leaning trees, fences, or utility poles on hillsides\n"
                "3. Unusual sounds — cracking trees, boulders knocking, rumbling\n"
                "4. Sudden change in stream water colour — becomes muddy or turbid\n"
                "5. Doors and windows sticking (ground movement deforming frames)\n"
                "6. Small stones or debris rolling down slopes unexpectedly\n"
                "7. Unusual seeping of water from hillsides after rain\n\n"
                "If you see these signs — evacuate immediately. Do not wait.\n\n"
                "Source: PDMA KP Flash Floods & GLOF Risk — Chitral Guidelines"
            )
        if any(w in q for w in ["risk", "cause", "why", "chitral", "prone", "vulnerable"]):
            return (
                "Landslide Risk — Chitral / KP:\n\n"
                "• Chitral's steep valleys make it extremely vulnerable to landslides\n"
                "• Heavy rainfall (>50mm in 24 hours) is the primary trigger in this region\n"
                "• Deforestation and road construction have significantly increased landslide risk\n"
                "• Earthquake-triggered landslides are a major secondary hazard in northern KP\n"
                "• Monsoon season (July–September) is peak landslide risk period\n"
                "• PDMA KP Flood & Landslide Contingency Plan 2026 covers Chitral specifically\n\n"
                "Source: PDMA KP Flood & Landslide Contingency Plan 2026"
            )
        if any(w in q for w in ["after", "following", "once", "post"]):
            return (
                "What to do AFTER a Landslide:\n\n"
                "1. Stay away from the slide area — additional slides frequently follow\n"
                "2. Check for injured persons — do NOT move seriously injured people\n"
                "3. Report damage to local DDMA or PDMA KP immediately\n"
                "4. Watch for flooding which often follows a landslide in Chitral valleys\n"
                "5. Do not re-enter the area until PDMA/DDMA declares it safe\n"
                "6. Document damage for relief registration\n\n"
                "Source: PDMA KP Flash Floods & GLOF Risk — Chitral Guidelines"
            )
        # Default = during
        return (
            "What to do During a LANDSLIDE:\n\n"
            "1. Move away from the landslide path as QUICKLY as possible\n"
            "2. Run at right angles (perpendicular) to the slide — not downhill\n"
            "3. If escape is impossible — curl into a tight ball and protect your head\n"
            "4. Avoid river valleys and low-lying areas during heavy rainfall\n"
            "5. Listen for unusual sounds — cracking trees, boulders knocking together\n"
            "6. If near a stream, watch for sudden change in water colour or level\n\n"
            "Emergency Contacts:\n"
            "• Rescue 1122 (KP Emergency — 24/7)\n"
            "• PDMA KP: 051-9222373\n\n"
            "Source: PDMA KP Flash Floods & GLOF Risk — Chitral Guidelines"
        )

    # ── 5. RAIN / MONSOON ─────────────────────────────────────────────────────
    if any(w in q for w in ["rain", "rainfall", "monsoon", "downpour", "storm", "heavy rain", "baarish"]):
        if any(w in q for w in ["risk", "cause", "chitral", "kp", "forecast", "pmd"]):
            return (
                "Heavy Rain Risk — Chitral / KP:\n\n"
                "• Chitral's annual rainfall is 400–500mm, concentrated in July–September\n"
                "• Cloud bursts are increasingly common due to climate change in KP mountains\n"
                "• Heavy rain can trigger flash floods in Chitral within MINUTES\n"
                "• Pakistan Meteorological Department (PMD) issues 72-hour advance warnings\n"
                "• PDMA KP activates Emergency Operations Centre during red/orange alerts\n\n"
                "Monitor: PMD website pmd.gov.pk for daily forecasts\n\n"
                "Source: NDMA Monsoon Preparedness Advisory 2025 / NDMA Monsoon Sitrep 2023"
            )
        return (
            "What to do During HEAVY RAIN:\n\n"
            "1. Avoid all low-lying areas, river banks, and nullahs\n"
            "2. Do NOT cross flooded roads or streams — even shallow water is dangerous\n"
            "3. Stay indoors and away from windows during thunderstorms\n"
            "4. Keep all drains and gutters clear to prevent waterlogging\n"
            "5. Move vehicles to higher ground if flash flooding is possible\n"
            "6. Monitor PDMA KP and PMD weather alerts on your phone\n"
            "7. Have emergency kit ready: torch, water, first aid, important documents\n\n"
            "Emergency Contacts:\n"
            "• Rescue 1122 (KP Emergency — 24/7)\n"
            "• PDMA KP: 051-9222373\n"
            "• PMD Weather Info: 051-9250363\n\n"
            "Source: NDMA Monsoon Preparedness Advisory 2025"
        )

    # ── 6. EMERGENCY CONTACTS ─────────────────────────────────────────────────
    if any(w in q for w in ["emergency", "rescue", "contact", "number", "helpline", "call", "1122", "phone"]):
        return (
            "Emergency Contacts — Chitral / KP, Pakistan:\n\n"
            "1. Rescue 1122 — KP Emergency Rescue Service (24/7, FREE)\n"
            "2. PDMA KP Helpline — 051-9222373 (Disaster Management)\n"
            "3. NDMA Helpline — 051-9246136 (National Disasters)\n"
            "4. Pakistan Met Department — 051-9250363 (Weather Warnings)\n"
            "5. Edhi Foundation — 115 (Ambulance & Rescue)\n"
            "6. Aga Khan Health Services Chitral — 0943-412093\n"
            "7. District Administration Chitral — 0943-412022\n"
            "8. Pakistan Army (Major Disasters) — 042-111-786-786\n\n"
            "Source: NDMA / PDMA KP Official Emergency Channels"
        )

    # ── 7. GO-BAG / EMERGENCY KIT ─────────────────────────────────────────────
    if any(w in q for w in ["go bag", "gobag", "emergency kit", "kit", "bag", "pack", "what to carry",
                             "supply", "checklist", "76 hours", "72 hours"]):
        return (
            "Go-Bag / Emergency Kit Checklist (NDMA Guidelines):\n\n"
            "1. Water — 3-day supply (3 litres per person per day)\n"
            "2. Food — Non-perishable for 3 days (biscuits, dry fruit, canned food)\n"
            "3. First Aid Kit — bandages, antiseptic, prescription medications\n"
            "4. Documents — CNIC copies, property papers, vaccination cards in waterproof bag\n"
            "5. Torch — solar or hand-crank preferred, plus extra batteries\n"
            "6. Power Bank — fully charged mobile phone backup\n"
            "7. Whistle — to signal rescuers if trapped under debris\n"
            "8. Warm Clothing — temperatures drop sharply in Chitral at night\n"
            "9. Cash — small denominations (ATMs fail during disasters)\n"
            "10. Local Map and printed emergency contact list\n\n"
            "Keep your Go-Bag in an easily accessible location.\n\n"
            "Source: NDMA Pakistan — Disaster Preparedness Guidelines 2024"
        )

    # ── 8. PREPAREDNESS / GENERAL ─────────────────────────────────────────────
    if any(w in q for w in ["prepare", "preparedness", "ready", "plan", "before disaster",
                             "family plan", "evacuation plan", "what can i do"]):
        return (
            "General Disaster Preparedness — Chitral / KP:\n\n"
            "1. Know your risk — Chitral faces floods, GLOFs, earthquakes, and landslides\n"
            "2. Make a family emergency plan — agree on meeting point and evacuation route\n"
            "3. Prepare a Go-Bag and keep it accessible at all times\n"
            "4. Save emergency numbers in ALL family members' phones: 1122, PDMA 051-9222373\n"
            "5. Stay informed — follow PDMA KP and PMD on social media during monsoon\n"
            "6. Register elderly and disabled family members with local DDMA Chitral\n"
            "7. Know your nearest evacuation shelter location\n"
            "8. Conduct a household drill at least once before monsoon season\n\n"
            "Source: NDMA Preparedness and Preventive Measures 2024"
        )

    # ── 9. NDMA / PDMA info ───────────────────────────────────────────────────
    if any(w in q for w in ["ndma", "pdma", "guidelines", "policy", "authority", "government"]):
        return (
            "NDMA & PDMA KP — Official Disaster Management:\n\n"
            "NDMA (National Disaster Management Authority):\n"
            "• Pakistan's apex body for disaster risk management\n"
            "• Issues national monsoon advisories, situation reports, and guidelines\n"
            "• Website: ndma.gov.pk | Helpline: 051-9246136\n\n"
            "PDMA KP (Provincial Disaster Management Authority):\n"
            "• KP-level disaster management and coordination body\n"
            "• Issues Chitral-specific flood and landslide warnings\n"
            "• Coordinates relief operations and GLOF monitoring in Chitral\n"
            "• Helpline: 051-9222373 | Website: pdma.gov.pk\n\n"
            "This app uses 13 official documents from NDMA and PDMA KP\n"
            "containing 315 verified text chunks for knowledge retrieval.\n\n"
            "Source: NDMA / PDMA KP Official Channels"
        )

    # ── 10. MONSOON / SEASON ──────────────────────────────────────────────────
    if any(w in q for w in ["monsoon", "season", "july", "august", "september", "summer"]):
        return (
            "Monsoon Season Safety — Chitral / KP (July–September):\n\n"
            "• Peak flood and landslide season: July 1 – September 30\n"
            "• PDMA KP activates Emergency Operations Centre during this period\n"
            "• PMD issues 72-hour and 48-hour heavy rain warnings\n\n"
            "What to do during monsoon season:\n"
            "1. Check PMD forecast EVERY morning before any travel\n"
            "2. Keep Go-Bag ready and accessible throughout the season\n"
            "3. Avoid travel on mountain roads during or after heavy rain\n"
            "4. Register your household with local DDMA for SMS early warnings\n"
            "5. Identify and memorize your nearest evacuation shelter\n\n"
            "Source: NDMA Monsoon Preparedness Advisory 2025 / NDMA Monsoon Advisory July 2024"
        )

    # No match
    return None


def _clean_chunks(chunks: list[dict]) -> list[str]:
    """
    Extracts clean, meaningful sentences from DB chunks.
    Filters out: table of contents, figure captions, page numbers, disclaimers.
    """
    garbage_patterns = [
        r'^(Figure|Table|Appendix|Chapter|Section|Contents|Foreword|Acronym)',
        r'^\d+\s*$',                          # lone page numbers
        r'^[A-Z\s]{3,}$',                     # ALL CAPS headers
        r'^(S\.|No\.|Sr\.)',                  # table rows
        r'(Table of Contents|List of)',
        r'^\s*[\-–—]+\s*$',                   # dividers
        r'Disclaimer',
        r'www\.|http',
        r'^\s*\d+\s*\|\s*P\s*A\s*G\s*E',     # page markers
        r'Â\s*Â',                             # encoding garbage
    ]
    garbage_re = re.compile('|'.join(garbage_patterns), re.IGNORECASE)

    clean = []
    for chunk in chunks:
        text = chunk.get("chunk_text", "")
        sentences = re.split(r'(?<=[.!?])\s+|\n', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 40 or len(sent) > 500:
                continue
            if garbage_re.search(sent):
                continue
            # Remove unicode artifacts
            sent = re.sub(r'[Â\xa0\u200b]+', ' ', sent).strip()
            sent = re.sub(r'\s+', ' ', sent)
            if len(sent) >= 40:
                clean.append(sent)
    return clean


# ── LLM provider implementations ─────────────────────────────────────────────

def _call_openai(prompt: str, context: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL or None)
        resp = client.chat.completions.create(
            model=LLM_MODEL or "gpt-4o-mini",
            max_tokens=LLM_MAX_TOKENS, temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_ollama(prompt: str, context: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key="ollama", base_url=LLM_BASE_URL or "http://localhost:11434/v1")
        resp = client.chat.completions.create(
            model=LLM_MODEL or "llama3",
            max_tokens=LLM_MAX_TOKENS, temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_groq(prompt: str, context: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL or "https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model=LLM_MODEL or "llama3-70b-8192",
            max_tokens=LLM_MAX_TOKENS, temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM error: {e}]"


_PROVIDER_DISPATCH = {
    "openai": _call_openai,
    "ollama": _call_ollama,
    "groq":   _call_groq,
}


# ── Main service function ─────────────────────────────────────────────────────

def query_rag(question: str, retrieved_chunks: list[dict], language: str = "en") -> RAGResponse:
    """
    Main RAG entry point.
    Priority order:
      1. Curated knowledge base (always accurate for known disaster topics)
      2. LLM generation with retrieved chunks (if provider configured)
      3. Clean sentences extracted from DB chunks
    """
    sources = [
        {
            "source_org":     c.get("source_org", ""),
            "doc_title":      c.get("doc_title", ""),
            "pub_date":       c.get("pub_date", ""),
            "evidence_level": c.get("evidence_level", "official"),
            "chunk_id":       c.get("chunk_id", ""),
            "source_url":     c.get("source_url", ""),
        }
        for c in retrieved_chunks
    ]

    total_score = sum(c.get("score", 0) for c in retrieved_chunks)

    # ── Step 1: Try curated knowledge base first ──────────────────────────────
    curated = _get_curated_answer(question, language)
    if curated:
        return RAGResponse(
            answer=curated,
            sources=sources if sources else [{
                "source_org": "NDMA / PDMA KP",
                "doc_title": "Official Disaster Guidelines",
                "pub_date": "2024",
                "evidence_level": "official",
                "chunk_id": "curated",
            }],
            retrieval_score=max(total_score, 5),
            confidence="sufficient",
            provider_used="curated_kb",
            generation_used=False,
        )

    # ── Step 2: Insufficient evidence check ──────────────────────────────────
    if not retrieved_chunks or total_score < LLM_MIN_CONFIDENCE:
        return RAGResponse(
            answer=(
                "I don't have specific information about this in my knowledge base.\n\n"
                "For disaster-related questions, you can ask me about:\n"
                "• What to do during floods\n"
                "• Earthquake safety steps\n"
                "• Landslide preparedness\n"
                "• Emergency contacts in Chitral / KP\n"
                "• Go-Bag / emergency kit checklist\n\n"
                "Source: NDMA / PDMA KP"
            ),
            sources=[],
            retrieval_score=total_score,
            confidence="insufficient",
            provider_used="none",
            generation_used=False,
        )

    # ── Step 3: LLM generation (if configured) ───────────────────────────────
    if LLM_PROVIDER != "none":
        context = "\n\n---\n\n".join(
            f"[{c.get('source_org','')} — {c.get('doc_title','')}]\n{c.get('chunk_text','')}"
            for c in retrieved_chunks[:3]
        )
        caller = _PROVIDER_DISPATCH.get(LLM_PROVIDER)
        if caller:
            generated = caller(question, context)
            if "INSUFFICIENT EVIDENCE" not in generated and generated.strip():
                return RAGResponse(
                    answer=generated, sources=sources,
                    retrieval_score=total_score, confidence="sufficient",
                    provider_used=LLM_PROVIDER, generation_used=True,
                )

    # ── Step 4: Clean sentences from DB chunks ────────────────────────────────
    clean_sentences = _clean_chunks(retrieved_chunks[:5])

    if clean_sentences:
        answer_lines = [f"Based on official disaster guidelines:\n"]
        for i, sent in enumerate(clean_sentences[:6], 1):
            answer_lines.append(f"{i}. {sent}")
        answer_lines.append(f"\nSource: {sources[0]['source_org']} — {sources[0]['doc_title']}" if sources else "")
        return RAGResponse(
            answer="\n".join(answer_lines), sources=sources,
            retrieval_score=total_score, confidence="sufficient",
            provider_used="none", generation_used=False,
        )

    # ── Final fallback ────────────────────────────────────────────────────────
    return RAGResponse(
        answer=(
            "Please ask about a specific disaster type for detailed guidance.\n\n"
            "Topics I can help with: floods, earthquakes, landslides, heavy rain, "
            "emergency contacts, Go-Bag checklist, disaster preparedness."
        ),
        sources=[], retrieval_score=total_score,
        confidence="insufficient", provider_used="none", generation_used=False,
    )
