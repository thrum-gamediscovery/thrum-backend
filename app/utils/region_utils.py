# 📄 File: app/utils/region_utils.py

# Maps phone prefixes to region codes
PHONE_REGION_MAP = {
    "+1": "US",
    "+44": "UK",
    "+91": "IN",
    "+61": "AU",
    "+81": "JP",
    "+49": "DE",
    "+33": "FR",
    "+34": "ES",
    "+55": "BR",
    "+7": "RU",
    "+82": "KR",
    "+39": "IT",
    "+86": "CN",
    "+3": "EU",
}

# Maps region codes to timezones
REGION_TIMEZONE_MAP = {
    "US": "America/New_York",
    "UK": "Europe/London",
    "IN": "Asia/Kolkata",
    "AU": "Australia/Sydney",
    "JP": "Asia/Tokyo",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "ES": "Europe/Madrid",
    "BR": "America/Sao_Paulo",
    "RU": "Europe/Moscow",
    "KR": "Asia/Seoul",
    "IT": "Europe/Rome",
    "CN": "Asia/Shanghai",
    "EU": "Europe/Brussels",
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

async def get_timezone_from_region(region: str) -> str | None:
    """
    Returns timezone string (e.g., "Asia/Kolkata") for a region code like "IN".
    """
    return REGION_TIMEZONE_MAP.get(region)