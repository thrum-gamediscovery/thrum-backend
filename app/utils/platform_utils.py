# app/utils/platform_utils.py
from rapidfuzz import process

VALID_PLATFORMS = [
    "Xbox One", "PlayStation 4", "Xbox Series X|S", "Nintendo Switch", "Macintosh", "Windows", "Linux", "Android",
    "PlayStation 5", "iPhone / iPod Touch", "iPad", "Xbox 360", "Oculus Quest", "PlayStation 3", "Nintendo Wii U",
    "PlayStation Vita", "New Nintendo 3DS", "Meta Quest 2", "Web Browser", "Nintendo Switch 2", "Nintendo 3DS"
]

def get_best_platform_match(user_input: str, threshold: int = 65) -> str | None:
    match, score, _ = process.extractOne(user_input, VALID_PLATFORMS, score_cutoff=threshold)
    return match if match else None