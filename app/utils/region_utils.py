# 📄 File: app/utils/region_utils.py

# Maps phone prefixes to region codes
PHONE_REGION_MAP  = {
    "+1": "United States/Canada",
    "+7": "Russia/Kazakhstan",
    "+20": "Egypt",
    "+27": "South Africa",
    "+30": "Greece",
    "+31": "Netherlands",
    "+32": "Belgium",
    "+33": "France",
    "+34": "Spain",
    "+36": "Hungary",
    "+39": "Italy",
    "+40": "Romania",
    "+41": "Switzerland",
    "+43": "Austria",
    "+44": "United Kingdom",
    "+45": "Denmark",
    "+46": "Sweden",
    "+47": "Norway",
    "+48": "Poland",
    "+49": "Germany",
    "+51": "Peru",
    "+52": "Mexico",
    "+53": "Cuba",
    "+54": "Argentina",
    "+55": "Brazil",
    "+56": "Chile",
    "+57": "Colombia",
    "+58": "Venezuela",
    "+60": "Malaysia",
    "+61": "Australia",
    "+62": "Indonesia",
    "+63": "Philippines",
    "+64": "New Zealand",
    "+65": "Singapore",
    "+66": "Thailand",
    "+81": "Japan",
    "+82": "South Korea",
    "+84": "Vietnam",
    "+86": "China",
    "+91": "India",
    "+92": "Pakistan",
    "+93": "Afghanistan",
    "+94": "Sri Lanka",
    "+95": "Myanmar",
    "+98": "Iran",
}

# Maps region codes to timezones
PHONE_TIMEZONE_MAP = {
    "+1": "America/New_York",         # United States/Canada (Eastern Time)
    "+7": "Europe/Moscow",            # Russia/Kazakhstan (Moscow Time)
    "+20": "Africa/Cairo",            # Egypt
    "+27": "Africa/Johannesburg",     # South Africa
    "+30": "Europe/Athens",           # Greece
    "+31": "Europe/Amsterdam",        # Netherlands
    "+32": "Europe/Brussels",         # Belgium
    "+33": "Europe/Paris",            # France
    "+34": "Europe/Madrid",           # Spain
    "+36": "Europe/Budapest",         # Hungary
    "+39": "Europe/Rome",             # Italy
    "+40": "Europe/Bucharest",        # Romania
    "+41": "Europe/Zurich",           # Switzerland
    "+43": "Europe/Vienna",           # Austria
    "+44": "Europe/London",           # United Kingdom
    "+45": "Europe/Copenhagen",       # Denmark
    "+46": "Europe/Stockholm",        # Sweden
    "+47": "Europe/Oslo",             # Norway
    "+48": "Europe/Warsaw",           # Poland
    "+49": "Europe/Berlin",           # Germany
    "+51": "America/Lima",            # Peru
    "+52": "America/Mexico_City",     # Mexico
    "+53": "America/Havana",          # Cuba
    "+54": "America/Argentina/Buenos_Aires", # Argentina
    "+55": "America/Sao_Paulo",       # Brazil
    "+56": "America/Santiago",        # Chile
    "+57": "America/Bogota",          # Colombia
    "+58": "America/Caracas",         # Venezuela
    "+60": "Asia/Kuala_Lumpur",       # Malaysia
    "+61": "Australia/Sydney",        # Australia
    "+62": "Asia/Jakarta",            # Indonesia
    "+63": "Asia/Manila",             # Philippines
    "+64": "Pacific/Auckland",        # New Zealand
    "+65": "Asia/Singapore",          # Singapore
    "+66": "Asia/Bangkok",            # Thailand
    "+81": "Asia/Tokyo",              # Japan
    "+82": "Asia/Seoul",              # South Korea
    "+84": "Asia/Ho_Chi_Minh",        # Vietnam
    "+86": "Asia/Shanghai",           # China
    "+91": "Asia/Kolkata",            # India
    "+92": "Asia/Karachi",            # Pakistan
    "+93": "Asia/Kabul",              # Afghanistan
    "+94": "Asia/Colombo",            # Sri Lanka
    "+95": "Asia/Yangon",             # Myanmar
    "+98": "Asia/Tehran",             # Iran
}

async def clean_phone_number(raw: str) -> str:
    """
    Removes prefixes like 'whatsapp:', 'discord:', etc.
    """
    if not raw:
        return ""
    return raw.split(":")[-1]

async def infer_region_from_phone(phone: str) -> str | None:
    """
    Returns region code (e.g., 'US', 'UK') from phone prefix.
    """
    if not phone:
        return None
    phone = await clean_phone_number(phone)
    for prefix, region in PHONE_REGION_MAP.items():
        if phone.startswith(prefix):
            return region
    return None

async def get_timezone_from_region(phone: str) -> str | None:
    """
    Returns timezone string (e.g., "Asia/Kolkata") for a region code like "IN".
    """
    if not phone:
        return None
    phone = await clean_phone_number(phone)
    for prefix, region in PHONE_TIMEZONE_MAP.items():
        if phone.startswith(prefix):
            return region
    return None