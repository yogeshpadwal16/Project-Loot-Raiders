# -*- coding: utf-8 -*-
"""
deal_engine/festival_bot.py
Year-Aware Dynamic Indian Festival & Holiday Greeting Automation Engine.
Supports movable lunar & solar Hindu festival dates across multiple years,
with a 3-tier fallback hierarchy:
  Tier 1: Google Imagen 3 AI-Generated Poster
  Tier 2: Dynamic Local PIL Festive Graphic Card
  Tier 3: Formatted HTML Text Greeting Broadcast
"""

import io
import os
import re
import json
import logging
import base64
import requests
from datetime import datetime, date
from typing import Optional, Dict, Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("loot_raiders.festival")

# ==============================================================================
# 1. YEAR-AWARE FESTIVAL CALENDAR DEFINITIONS
# ==============================================================================

# Fixed Annual National & Regional Festivals (Month-Day)
FIXED_FESTIVALS: Dict[str, Dict[str, Any]] = {
    "01-01": {
        "name": "New Year",
        "theme": "golden_midnight",
        "desc": "An epic cinematic poster for New Year celebration, fireworks over horizon, glowing gold sparkles, bokeh lights, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>नवीन वर्षाच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "नवीन वर्ष तुमच्या आयुष्यात सुख, समृद्धी, समाधान आणि उत्तम आरोग्य घेऊन येवो. "
            "तुमची सर्व स्वप्ने आणि संकल्प पूर्ण होवोत!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "01-14": {
        "name": "Makar Sankranti",
        "theme": "saffron_sun",
        "desc": "An epic cinematic poster for Makar Sankranti, vibrant kites flying in bright golden sunny sky, traditional sesame tilgul sweets in brass bowl, soft sunlight, 8k resolution, no text, clean composition",
        "caption": (
            "🪁 <b>मकर संक्रांतीच्या गोड गोड शुभेच्छा!</b> 🪁\n\n"
            "तिळगुळ घ्या, गोड गोड बोला! हे नववर्ष आणि मकर संक्रांतीचा सण तुमच्या आयुष्यात गोडवा, भरभराट आणि उत्तम आरोग्य घेऊन येवो.\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "01-26": {
        "name": "Republic Day",
        "theme": "tricolor",
        "desc": "An epic cinematic Indian Republic Day illustration, Indian tricolor saffron white green ribbons, glowing Ashoka Chakra, patriotic volumetric golden rays, 8k resolution, no text, clean composition",
        "caption": (
            "🇮🇳 <b>प्रजासत्ताक दिनाच्या हार्दिक शुभेच्छा!</b> 🇮🇳\n\n"
            "भारतीय प्रजासत्ताक दिनानिमित्त सर्व देशबांधवांना मनःपूर्वक शुभेच्छा. आपल्या देशाचा गौरव, एकता आणि अखंडता सदैव अशीच वृद्धिंगत राहो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "02-19": {
        "name": "Chhatrapati Shivaji Maharaj Jayanti",
        "theme": "saffron_royalty",
        "desc": "An epic cinematic majestic poster of Chhatrapati Shivaji Maharaj on golden royal throne, saffron flag background, Raigad fort silhouette, volumetric dramatic lighting, 8k resolution, no text, clean composition",
        "caption": (
            "🚩 <b>शिवजयंतीच्या हार्दिक शुभेच्छा!</b> 🚩\n\n"
            "प्रौढ प्रताप पुरंदर, क्षत्रिय कुलावतंस, सिंहासनाधीश्वर, महाराजाधिराज छत्रपती शिवाजी महाराज की जय! "
            "अखंड महाराष्ट्राचे आराध्य दैवत छत्रपती शिवाजी महाराज यांच्या जयंतीनिमित्त त्रिवार वंदन!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "04-14": {
        "name": "Dr. B.R. Ambedkar Jayanti",
        "theme": "blue_gold",
        "desc": "An epic cinematic dignified poster for Dr. B.R. Ambedkar Jayanti, golden constitution book, soft blue and gold aura, Ashoka Stambh background, 8k resolution, no text, clean composition",
        "caption": (
            "⚖️ <b>महामानव डॉ. बाबासाहेब आंबेडकर जयंतीच्या हार्दिक शुभेच्छा!</b> ⚖️\n\n"
            "भारतीय संविधानाचे शिल्पकार, भारतरत्न परमपूज्य डॉ. बाबासाहेब आंबेडकर यांच्या जयंतीनिमित्त विनम्र अभिवादन!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "05-01": {
        "name": "Maharashtra Day",
        "theme": "saffron_royalty",
        "desc": "An epic cinematic poster for Maharashtra Day, waving saffron flag, Gateway of India and Sahyadri mountains silhouette, dramatic golden sunlight, 8k resolution, no text, clean composition",
        "caption": (
            "🚩 <b>महाराष्ट्र दिन व कामगार दिनाच्या हार्दिक शुभेच्छा!</b> 🚩\n\n"
            "जय जय महाराष्ट्र माझा, गर्जा महाराष्ट्र माझा! "
            "महाराष्ट्र दिन आणि आंतरराष्ट्रीय कामगार दिनानिमित्त सर्व नागरिकांना मनःपूर्वक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "08-15": {
        "name": "Independence Day",
        "theme": "tricolor",
        "desc": "An epic cinematic Indian Independence Day poster, flying tricolor flag with dramatic volumetric sunlight, Red Fort silhouette, golden glowing bokeh, 8k resolution, no text, clean composition",
        "caption": (
            "🇮🇳 <b>स्वातंत्र्य दिनाच्या हार्दिक शुभेच्छा!</b> 🇮🇳\n\n"
            "भारतीय स्वातंत्र्य दिनाच्या सर्व देशबांधवांना मनःपूर्वक शुभेच्छा! "
            "स्वातंत्र्यासाठी बलिदान देणाऱ्या सर्व शूर हुतात्म्यांना कोटी कोटी प्रणाम!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "10-02": {
        "name": "Mahatma Gandhi Jayanti",
        "theme": "white_gold",
        "desc": "An epic cinematic peaceful poster for Gandhi Jayanti, spinning charkha wheel, soft warm morning rays, lotus flowers, 8k resolution, no text, clean composition",
        "caption": (
            "🕊️ <b>महात्मा गांधी व लाल बहादूर शास्त्री जयंतीच्या शुभेच्छा!</b> 🕊️\n\n"
            "सत्य आणि अहिंसेचे पुजारी राष्ट्रपिता महात्मा गांधी व 'जय जवान जय किसान'चे प्रणेते लाल बहादूर शास्त्री यांच्या जयंतीनिमित्त विनम्र अभिवादन!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "12-25": {
        "name": "Christmas",
        "theme": "green_red",
        "desc": "An epic cinematic Christmas poster, glowing illuminated pine tree, golden bells, warm candlelight, soft snowflakes falling, 8k resolution, no text, clean composition",
        "caption": (
            "🎄 <b>मेरी ख्रिसमस / नाताळच्या हार्दिक शुभेच्छा!</b> 🎄\n\n"
            "नाताळचा हा सण तुमच्या व तुमच्या कुटुंबाच्या आयुष्यात सुख, शांती, आरोग्य आणि अमाप आनंद घेऊन येवो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    }
}

# Movable Indian Lunar & Solar Festivals Calendar (Year-Aware YYYY-MM-DD Table)
MOVABLE_FESTIVALS: Dict[str, Dict[str, Any]] = {
    # 2024
    "2024-03-08": {"name": "Mahashivratri", "theme": "blue_divine", "motif": "shiv"},
    "2024-03-25": {"name": "Holi", "theme": "colors", "motif": "holi"},
    "2024-04-09": {"name": "Gudi Padwa", "theme": "saffron_gudi", "motif": "gudi"},
    "2024-04-17": {"name": "Ram Navami", "theme": "gold_saffron", "motif": "ram"},
    "2024-08-19": {"name": "Raksha Bandhan", "theme": "gold_rakhi", "motif": "rakhi"},
    "2024-08-26": {"name": "Krishna Janmashtami", "theme": "blue_krishna", "motif": "krishna"},
    "2024-09-07": {"name": "Ganesh Chaturthi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2024-09-17": {"name": "Anant Chaturdashi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2024-10-03": {"name": "Navratri Ghatsthapana", "theme": "red_gold", "motif": "durga"},
    "2024-10-12": {"name": "Dussehra", "theme": "gold_saffron", "motif": "dussehra"},
    "2024-10-29": {"name": "Dhanteras", "theme": "gold_diya", "motif": "diwali"},
    "2024-10-31": {"name": "Diwali Lakshmi Pujan", "theme": "gold_diya", "motif": "diwali"},
    "2024-11-02": {"name": "Diwali Padwa", "theme": "gold_diya", "motif": "diwali"},
    "2024-11-03": {"name": "Bhai Dooj", "theme": "gold_diya", "motif": "diwali"},

    # 2025
    "2025-02-26": {"name": "Mahashivratri", "theme": "blue_divine", "motif": "shiv"},
    "2025-03-14": {"name": "Holi", "theme": "colors", "motif": "holi"},
    "2025-03-30": {"name": "Gudi Padwa", "theme": "saffron_gudi", "motif": "gudi"},
    "2025-04-06": {"name": "Ram Navami", "theme": "gold_saffron", "motif": "ram"},
    "2025-08-09": {"name": "Raksha Bandhan", "theme": "gold_rakhi", "motif": "rakhi"},
    "2025-08-16": {"name": "Krishna Janmashtami", "theme": "blue_krishna", "motif": "krishna"},
    "2025-08-27": {"name": "Ganesh Chaturthi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2025-09-06": {"name": "Anant Chaturdashi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2025-09-22": {"name": "Navratri Ghatsthapana", "theme": "red_gold", "motif": "durga"},
    "2025-10-02": {"name": "Dussehra", "theme": "gold_saffron", "motif": "dussehra"},
    "2025-10-18": {"name": "Dhanteras", "theme": "gold_diya", "motif": "diwali"},
    "2025-10-20": {"name": "Diwali Lakshmi Pujan", "theme": "gold_diya", "motif": "diwali"},
    "2025-10-22": {"name": "Diwali Padwa", "theme": "gold_diya", "motif": "diwali"},
    "2025-10-23": {"name": "Bhai Dooj", "theme": "gold_diya", "motif": "diwali"},

    # 2026
    "2026-02-15": {"name": "Mahashivratri", "theme": "blue_divine", "motif": "shiv"},
    "2026-03-04": {"name": "Holi", "theme": "colors", "motif": "holi"},
    "2026-03-19": {"name": "Gudi Padwa", "theme": "saffron_gudi", "motif": "gudi"},
    "2026-03-27": {"name": "Ram Navami", "theme": "gold_saffron", "motif": "ram"},
    "2026-08-02": {"name": "Sankashti Chaturthi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2026-08-28": {"name": "Raksha Bandhan", "theme": "gold_rakhi", "motif": "rakhi"},
    "2026-09-04": {"name": "Krishna Janmashtami", "theme": "blue_krishna", "motif": "krishna"},
    "2026-09-14": {"name": "Ganesh Chaturthi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2026-09-24": {"name": "Anant Chaturdashi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2026-10-11": {"name": "Navratri Ghatsthapana", "theme": "red_gold", "motif": "durga"},
    "2026-10-20": {"name": "Dussehra", "theme": "gold_saffron", "motif": "dussehra"},
    "2026-11-06": {"name": "Dhanteras", "theme": "gold_diya", "motif": "diwali"},
    "2026-11-08": {"name": "Diwali Lakshmi Pujan", "theme": "gold_diya", "motif": "diwali"},
    "2026-11-10": {"name": "Diwali Padwa", "theme": "gold_diya", "motif": "diwali"},
    "2026-11-11": {"name": "Bhai Dooj", "theme": "gold_diya", "motif": "diwali"},

    # 2027
    "2027-03-06": {"name": "Mahashivratri", "theme": "blue_divine", "motif": "shiv"},
    "2027-03-22": {"name": "Holi", "theme": "colors", "motif": "holi"},
    "2027-04-07": {"name": "Gudi Padwa", "theme": "saffron_gudi", "motif": "gudi"},
    "2027-04-15": {"name": "Ram Navami", "theme": "gold_saffron", "motif": "ram"},
    "2027-08-17": {"name": "Raksha Bandhan", "theme": "gold_rakhi", "motif": "rakhi"},
    "2027-08-25": {"name": "Krishna Janmashtami", "theme": "blue_krishna", "motif": "krishna"},
    "2027-09-04": {"name": "Ganesh Chaturthi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2027-09-14": {"name": "Anant Chaturdashi", "theme": "gold_ganesh", "motif": "ganesh"},
    "2027-09-30": {"name": "Navratri Ghatsthapana", "theme": "red_gold", "motif": "durga"},
    "2027-10-09": {"name": "Dussehra", "theme": "gold_saffron", "motif": "dussehra"},
    "2027-10-27": {"name": "Dhanteras", "theme": "gold_diya", "motif": "diwali"},
    "2027-10-29": {"name": "Diwali Lakshmi Pujan", "theme": "gold_diya", "motif": "diwali"},
    "2027-10-31": {"name": "Diwali Padwa", "theme": "gold_diya", "motif": "diwali"},
    "2027-11-01": {"name": "Bhai Dooj", "theme": "gold_diya", "motif": "diwali"}
}

# Template metadata for movable festival content
MOVABLE_FESTIVAL_METADATA: Dict[str, Dict[str, str]] = {
    "Mahashivratri": {
        "desc": "An epic cinematic poster of Lord Shiva in deep meditation, glowing trident and crescent moon, Himalayas snowy mountain background, soft blue glowing aura, 8k resolution, no text, clean composition",
        "caption": (
            "🔱 <b>महाशिवरात्रीच्या मनःपूर्वक हार्दिक शुभेच्छा!</b> 🔱\n\n"
            "हर हर महादेव! भगवान भोलेनाथांच्या कृपेने तुमच्या जीवनातील सर्व संकटे दूर होवोत आणि तुमचे आयुष्य सुख, शांती व आनंदाने भरून जावो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Holi": {
        "desc": "An epic cinematic poster for Holi, featuring vibrant splashes of colourful gulal powders, joyful festive spirit background, dynamic lighting, floating powder particles, professional digital art, 8k resolution, no text, clean composition",
        "caption": (
            "🎨 <b>धुलिवंदन व होळीच्या हार्दिक शुभेच्छा!</b> 🎨\n\n"
            "रंगांचा हा सण तुमच्या आयुष्यात नवी उमेद, उत्साह आणि आनंद घेऊन येवो. तुम्हाला आणि तुमच्या संपूर्ण कुटुंबाला होळीच्या मनःपूर्वक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Gudi Padwa": {
        "desc": "An epic cinematic poster for Gudi Padwa, traditional decorated Gudi with bright silk cloth, neem leaves, marigold flowers, warm sunrise background, 8k resolution, no text, clean composition",
        "caption": (
            "🚩 <b>गुढीपाडवा व मराठी नववर्षाच्या हार्दिक शुभेच्छा!</b> 🚩\n\n"
            "नवीन वर्ष, नवीन उमेद, नवी आशा! हे नववर्ष तुमच्या आयुष्यात सुख, समृद्धी आणि यशाची उंच गुढी उभारो, हीच सदिच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Ram Navami": {
        "desc": "An epic cinematic poster of Prabhu Shri Ram, holding bow and arrow, divine golden aura, Ayodhya temple background with floating dust particles, 8k resolution, no text, clean composition",
        "caption": (
            "🏹 <b>श्रीराम नवमीच्या हार्दिक शुभेच्छा!</b> 🏹\n\n"
            "मर्यादा पुरुषोत्तम प्रभू श्रीरामांच्या चरणी नतमस्तक होऊन आपणा सर्वांना श्रीराम नवमीच्या मंगलमय शुभेच्छा! जय श्री राम!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Raksha Bandhan": {
        "desc": "An epic cinematic poster for Raksha Bandhan, golden decorative rakhi on silk plate with sweets, warm festive bokeh lights, 8k resolution, no text, clean composition",
        "caption": (
            "🧵 <b>रक्षाबंधनाच्या पवित्र सणाच्या हार्दिक शुभेच्छा!</b> 🧵\n\n"
            "भावा-बहिणीच्या अतूट प्रेमाचा आणि विश्वासाचा हा पवित्र सण तुमच्या नात्यातील गोडवा आणि प्रेम वृद्धिंगत करो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Krishna Janmashtami": {
        "desc": "An epic cinematic poster of Lord Krishna with glowing flute, peacock feather, golden Dahi Handi, soft blue divine lighting, 8k resolution, no text, clean composition",
        "caption": (
            "🦚 <b>गोकुळाष्टमी व दहीहंडीच्या हार्दिक शुभेच्छा!</b> 🦚\n\n"
            "गोविंद आला रे आला! बाळकृष्णाच्या आगमनाने तुमच्या घरात सुख, आनंद आणि भरभराट नांदो! दहीहंडीच्या सर्व गोविंदांना शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Ganesh Chaturthi": {
        "desc": "An epic cinematic poster of Lord Ganesha, seated majestically on a golden throne, realistic detailed textures, dramatic volumetric lighting, bright golden temple background with soft glowing smoke, 8k resolution, no text, clean composition",
        "caption": (
            "🐘 <b>गणेश चतुर्थीच्या हार्दिक शुभेच्छा!</b> 🐘\n\n"
            "गणपती बाप्पा मोरया! बाप्पाच्या आगमनाने तुमच्या घरी सुख, समृद्धी आणि ऐश्वर्य नांदो. विघ्नहर्ता तुमच्या सर्व मनोकामना पूर्ण करो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Anant Chaturdashi": {
        "desc": "An epic cinematic poster of Ganpati Visarjan, Lord Ganesha idol with glowing garland, festive gulal in air, sunset lighting, 8k resolution, no text, clean composition",
        "caption": (
            "🙏 <b>अनंत चतुर्दशीच्या हार्दिक शुभेच्छा!</b> 🙏\n\n"
            "गणपती बाप्पा मोरया, पुढच्या वर्षी लवकर या! बाप्पा तुमच्या सर्व संकटांचे निवारण करोत आणि सुख-समृद्धी देवोत!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Navratri Ghatsthapana": {
        "desc": "An epic cinematic poster for Navratri, Goddess Durga seated on lion, glowing trident, festive Dandiya Garba background with warm diya lights, 8k resolution, no text, clean composition",
        "caption": (
            "🪔 <b>नवरात्रौत्सवाच्या हार्दिक शुभेच्छा!</b> 🪔\n\n"
            "आई जगदंबेच्या आशीर्वादाने तुमच्या आयुष्यात शक्ती, भक्ती, सुख आणि भरभराट नांदो! नवरात्रौत्सवाच्या मनःपूर्वक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Dussehra": {
        "desc": "An epic cinematic poster for Dussehra, golden Apta leaves, Lord Ram with fiery bow and arrow, Ravana dahan background, 8k resolution, no text, clean composition",
        "caption": (
            "🌾 <b>दसरा व विजयादशमीच्या हार्दिक शुभेच्छा!</b> 🌾\n\n"
            "सोन्यासारख्या माणसांना दसऱ्याच्या सोन्यासारख्या शुभेच्छा! वाईटावर चांगल्याचा विजय साजरा करणारा हा सण तुमच्या आयुष्यात यश घेऊन येवो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Dhanteras": {
        "desc": "An epic cinematic poster for Dhanteras, golden pot full of gold coins, glowing diyas, Goddess Lakshmi golden feet, rich warm lighting, 8k resolution, no text, clean composition",
        "caption": (
            "💰 <b>धनत्रयोदशीच्या मनःपूर्वक शुभेच्छा!</b> 💰\n\n"
            "धनत्रयोदशीच्या शुभ मुहूर्तावर धन्वंतरी व माता लक्ष्मीच्या कृपेने तुम्हाला उत्तम आरोग्य, सुख व विपुल धनसंपत्ती लाभो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Diwali Lakshmi Pujan": {
        "desc": "An epic cinematic poster for Diwali, traditional glowing oil lamps, rich gold accents, warm bokeh lights, volumetric smoke, floating dust embers, professional digital art, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>शुभ दीपावली व लक्ष्मीपूजनाच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "तुम्हाला आणि तुमच्या संपूर्ण कुटुंबाला दीपावलीच्या निमित्ताने सुख, समृद्धी आणि उत्तम आरोग्य लाभो, हीच प्रार्थना. हा दिव्यांचा सण तुमच्या आयुष्यात प्रकाश आणि आनंद घेऊन येवो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Diwali Padwa": {
        "desc": "An epic cinematic poster for Diwali Padwa and Balipratipada, glowing diyas, couple offering traditional aarti, warm gold lighting, 8k resolution, no text, clean composition",
        "caption": (
            "🪔 <b>दिवाळी पाडवा व बलिप्रतिपदेच्या हार्दिक शुभेच्छा!</b> 🪔\n\n"
            "पती-पत्नीच्या अतूट प्रेमाचा आणि विश्वासाचा मंगल सण! दिवाळी पाडव्याच्या सर्व जोडप्यांना व नागरिकांना मनःपूर्वक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Bhai Dooj": {
        "desc": "An epic cinematic poster for Bhai Dooj, traditional aarti plate with glowing diya and sweets, silk background, 8k resolution, no text, clean composition",
        "caption": (
            "💖 <b>भाऊबीजेच्या हार्दिक शुभेच्छा!</b> 💖\n\n"
            "भाऊ-बहिणीच्या पवित्र नात्याचा गोड सण! भाऊबीजेच्या निमित्ताने सर्व भाऊ-बहिणींना मनःपूर्वक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "Sankashti Chaturthi": {
        "desc": "An epic cinematic poster of Lord Ganesha, seated majestically on a golden throne, realistic detailed textures, dramatic volumetric lighting, warm golden and deep orange background, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>संकष्टी चतुर्थीच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "तुम्हाला आणि तुमच्या संपूर्ण कुटुंबाला संकष्टी चतुर्थीच्या निमित्ताने सुख, समृद्धी आणि उत्तम आरोग्य लाभो, हीच गणरायाच्या चरणी प्रार्थना. बाप्पा तुमच्या आयुष्यातील सर्व संकटे दूर करोत!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    }
}


def get_festival_for_date(target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Year-Aware Festival Resolver.
    Resolves the active festival for a given date, prioritizing specific YYYY-MM-DD movable
    festivals over fixed annual MM-DD holidays.
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    full_date_key = target_date.strftime("%Y-%m-%d")
    month_day_key = target_date.strftime("%m-%d")

    # 1. Check Year-Aware Movable Festival Table (e.g. 2026-09-14 Ganesh Chaturthi)
    if full_date_key in MOVABLE_FESTIVALS:
        movable_entry = MOVABLE_FESTIVALS[full_date_key]
        fest_name = movable_entry["name"]
        meta = MOVABLE_FESTIVAL_METADATA.get(fest_name, {})
        return {
            "name": fest_name,
            "theme": movable_entry.get("theme", "gold_saffron"),
            "motif": movable_entry.get("motif", "festival"),
            "desc": meta.get("desc", f"An epic cinematic festive poster for {fest_name}, professional digital art, 8k resolution, no text, clean composition"),
            "caption": meta.get("caption", f"✨ <b>{fest_name}च्या हार्दिक शुभेच्छा!</b> ✨\n\n🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸")
        }

    # 2. Check Fixed Annual Holiday Table (e.g. 01-26 Republic Day, 08-15 Independence Day)
    if month_day_key in FIXED_FESTIVALS:
        fixed_entry = FIXED_FESTIVALS[month_day_key]
        return {
            "name": fixed_entry["name"],
            "theme": fixed_entry.get("theme", "gold_saffron"),
            "motif": "fixed",
            "desc": fixed_entry["desc"],
            "caption": fixed_entry["caption"]
        }

    return None


# ==============================================================================
# 2. TIER 1: GOOGLE IMAGEN 3 AI POSTER GENERATION
# ==============================================================================

def generate_festival_poster(prompt_details: str) -> Optional[bytes]:
    """
    Generates a high-res festival poster using Google Imagen 3 API.
    Gracefully returns None if API credentials are not configured or call fails.
    """
    from config.settings import load_settings
    settings = load_settings()
    api_key = settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        logger.info("[FESTIVAL] GEMINI_API_KEY not configured. Bypassing AI generation to local asset fallback.")
        return None

    # Google Imagen 3 official Generative Language API endpoints
    imagen_models = [
        "imagen-3.0-generate-002",
        "imagen-3.0-fast-generate-001"
    ]

    for model in imagen_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "instances": [{"prompt": prompt_details}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "1:1",
                "outputOptions": {"mimeType": "image/jpeg"}
            }
        }
        try:
            logger.info(f"[FESTIVAL] Requesting Imagen 3 poster generation via model '{model}'...")
            res = requests.post(url, json=payload, headers=headers, timeout=45)
            if res.status_code == 200:
                data = res.json()
                predictions = data.get("predictions", [])
                if predictions and predictions[0].get("bytesBase64Encoded"):
                    logger.info(f"[FESTIVAL] Successfully generated AI poster via {model}!")
                    return base64.b64decode(predictions[0]["bytesBase64Encoded"])
            else:
                logger.warning(f"[FESTIVAL] Imagen API ({model}) returned HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            logger.warning(f"[FESTIVAL] Failed calling Imagen API ({model}): {e}")

    logger.info("[FESTIVAL] AI generation unavailable. Proceeding to Tier 2 local artwork fallback.")
    return None


# ==============================================================================
# 3. TIER 2: LOCAL DYNAMIC PIL FESTIVE GRAPHIC CARD
# ==============================================================================

def generate_local_festival_card(festival_info: Dict[str, Any]) -> Optional[bytes]:
    """
    Renders an 800x1000 branded festive graphic card with gradient backgrounds,
    ornamental gold borders, glowing festival typography, and team watermark.
    """
    try:
        fest_name = festival_info.get("name", "Festival")
        theme = festival_info.get("theme", "gold_saffron")

        # 1. Canvas Setup (800x1000)
        canvas = Image.new("RGB", (800, 1000), color="#1a0005")
        draw = ImageDraw.Draw(canvas)

        # 2. Theme Gradient Rendering
        color_schemes = {
            "gold_diya": ((30, 8, 4), (180, 83, 9)),           # Deep Maroon -> Warm Gold Diya
            "gold_ganesh": ((45, 10, 5), (217, 119, 6)),        # Deep Saffron -> Bright Gold
            "saffron_royalty": ((40, 12, 0), (234, 88, 12)),    # Royal Saffron Orange
            "tricolor": ((15, 23, 42), (255, 153, 51)),         # Deep Navy -> Indian Saffron
            "colors": ((35, 10, 50), (236, 72, 153)),          # Festive Purple -> Gulal Pink
            "blue_divine": ((5, 15, 35), (37, 99, 235)),        # Deep Midnight -> Shiv Blue
            "green_red": ((20, 4, 10), (16, 185, 129)),        # Festive Red -> Emerald Green
            "gold_saffron": ((35, 10, 10), (217, 119, 6))      # Default Gold/Saffron
        }
        top_color, bottom_color = color_schemes.get(theme, color_schemes["gold_saffron"])

        for y in range(1000):
            ratio = y / 1000.0
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            draw.line([(0, y), (800, y)], fill=(r, g, b))

        # 3. Ornamental Gold Borders
        gold_border = (234, 179, 8)
        draw.rectangle([(20, 20), (780, 980)], outline=gold_border, width=3)
        draw.rectangle([(28, 28), (772, 972)], outline=(253, 224, 71, 160), width=1)

        # Corner Ornaments
        corner_size = 35
        for (cx, cy) in [(20, 20), (780 - corner_size, 20), (20, 980 - corner_size), (780 - corner_size, 980 - corner_size)]:
            draw.rectangle([(cx, cy), (cx + corner_size, cy + corner_size)], fill=(234, 179, 8, 80), outline=gold_border, width=2)

        # 4. Central Festive Embellishment Box
        draw.rounded_rectangle([(60, 120), (740, 840)], radius=20, fill=(15, 23, 42, 220), outline=(250, 204, 21), width=2)

        # 5. Festive Text and Header
        font_candidates_title = ["C:\\Windows\\Fonts\\segoeuib.ttf", "C:\\Windows\\Fonts\\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        font_candidates_sub = ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

        title_font = None
        sub_font = None
        for fc in font_candidates_title:
            if os.path.exists(fc):
                try:
                    title_font = ImageFont.truetype(fc, 36)
                    break
                except Exception:
                    pass
        if not title_font:
            title_font = ImageFont.load_default()

        for fc in font_candidates_sub:
            if os.path.exists(fc):
                try:
                    sub_font = ImageFont.truetype(fc, 22)
                    break
                except Exception:
                    pass
        if not sub_font:
            sub_font = ImageFont.load_default()

        # Header Badge
        draw.text((400, 170), "✨ FESTIVE GREETINGS ✨", fill=(253, 224, 71), font=sub_font, anchor="mm")
        draw.line([(220, 200), (580, 200)], fill=(234, 179, 8), width=2)

        # Festival Name
        draw.text((400, 270), fest_name.upper(), fill=(255, 255, 255), font=title_font, anchor="mm")

        # Decorative Motif Ring
        draw.ellipse([(330, 360), (470, 500)], fill=(234, 179, 8, 40), outline=(253, 224, 71), width=3)
        draw.text((400, 430), "🪔", fill=(255, 255, 255), font=title_font, anchor="mm")

        # Warm Blessings & Text Lines
        draw.text((400, 570), "May this joyous occasion bring", fill=(241, 245, 249), font=sub_font, anchor="mm")
        draw.text((400, 610), "Happiness, Good Health & Prosperity", fill=(253, 224, 71), font=sub_font, anchor="mm")
        draw.text((400, 650), "to you and your entire family!", fill=(241, 245, 249), font=sub_font, anchor="mm")

        # Footer Team Brand
        draw.line([(150, 750), (650, 750)], fill=(234, 179, 8), width=1)
        draw.text((400, 790), "Team @LootRaidersDeals", fill=(251, 191, 36), font=sub_font, anchor="mm")

        # Save to buffer
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=95)
        logger.info(f"[FESTIVAL] Generated high-res local festive card for '{fest_name}'.")
        return buf.getvalue()
    except Exception as err:
        logger.error(f"[FESTIVAL] Local card generation failed: {err}")
        return None


# ==============================================================================
# 4. TELEGRAM DISPATCHER WITH 3-TIER RESILIENCE
# ==============================================================================

def send_festival_greeting(image_bytes: Optional[bytes], caption: str) -> bool:
    """
    Dispatches the festival greeting to the official Telegram channel.
    If image_bytes is provided, attempts sendPhoto. If photo fails or image_bytes
    is None, falls back to rich HTML sendMessage.
    """
    from config.settings import load_settings
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = settings.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID", "@LootRaidersDeals")

    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "" or not chat_id:
        logger.warning("[FESTIVAL] Telegram bot credentials not configured in settings. Skipping broadcast.")
        return False

    # Tier 1 & 2: Send Photo if artwork exists
    if image_bytes and len(image_bytes) > 500:
        try:
            endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("festival_poster.jpg", io.BytesIO(image_bytes), "image/jpeg")}
            payload = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            res = requests.post(endpoint, data=payload, files=files, timeout=30)
            if res.status_code == 200:
                logger.info("[FESTIVAL] Successfully broadcasted festive artwork card to Telegram channel!")
                return True
            else:
                logger.warning(f"[FESTIVAL] Telegram sendPhoto returned HTTP {res.status_code}: {res.text}. Attempting text fallback...")
        except Exception as e:
            logger.warning(f"[FESTIVAL] Telegram sendPhoto exception: {e}. Falling back to sendMessage.")

    # Tier 3: Send HTML Text Greeting
    try:
        endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        res = requests.post(endpoint, data=payload, timeout=20)
        if res.status_code == 200:
            logger.info("[FESTIVAL] Successfully broadcasted HTML festive text greeting to Telegram channel!")
            return True
        else:
            logger.error(f"[FESTIVAL] Telegram sendMessage failed ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        logger.error(f"[FESTIVAL] Telegram sendMessage exception: {e}")
        return False


# ==============================================================================
# 5. MAIN CHECK RUNNER (CALLED BY NOTIFIER WORKER HOURLY)
# ==============================================================================

async def check_and_run_festival_bot(target_date: Optional[date] = None) -> bool:
    """
    Main festival greeting runner with atomic same-day idempotency.
    Evaluates current calendar date, executes 3-tier fallback greeting hierarchy,
    and records completion state upon successful broadcast.
    """
    from config.settings import load_settings, save_settings

    try:
        check_date = target_date if target_date else datetime.now().date()
        today_str = check_date.strftime("%Y-%m-%d")

        festival_info = get_festival_for_date(check_date)
        if not festival_info:
            return False

        fest_name = festival_info["name"]
        festival_desc = festival_info["desc"]
        caption = festival_info["caption"]

        settings = load_settings()
        if settings.get("last_festival_greeting_date") == today_str:
            logger.debug(f"[FESTIVAL] Greeting for {today_str} ({fest_name}) already published. Skipping duplicate.")
            return False

        logger.info(f"[FESTIVAL] Active festival detected for {today_str}: '{fest_name}'! Initiating 3-tier broadcast...")

        # Tier 1: Try AI Poster
        poster_bytes = generate_festival_poster(festival_desc)

        # Tier 2: Try Local Graphic Card if AI poster was None
        if not poster_bytes:
            poster_bytes = generate_local_festival_card(festival_info)

        # Tier 1/2/3 Broadcast
        posted = send_festival_greeting(poster_bytes, caption)
        if posted:
            settings["last_festival_greeting_date"] = today_str
            save_settings(settings)
            logger.info(f"[FESTIVAL] State updated: 'last_festival_greeting_date' set to {today_str}.")
            return True
        else:
            logger.warning(f"[FESTIVAL] Broadcast failed to deliver greeting for {fest_name}.")
            return False
    except Exception as err:
        logger.error(f"[FESTIVAL] Unexpected error in check_and_run_festival_bot: {err}", exc_info=True)
        return False
