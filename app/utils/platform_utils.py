from rapidfuzz import process  # For fuzzy string matching
from sqlalchemy.orm import Session  # DB session
from app.db.models.unique_value import UniqueValue  # Model for unique fields
from typing import Optional  # For optional return type

async def get_valid_platforms_from_db(db: Session) -> list[str]:
    # Get platform list from unique_values table
    row = db.query(UniqueValue).filter(UniqueValue.field == "platform").first()
    return row.unique_values if row and row.unique_values else []

async def get_best_platform_match(user_input: str, db: Session, threshold: int = 65) -> Optional[str]:
    # Match user input to closest platform name
    valid_platforms = get_valid_platforms_from_db(db)
    if not valid_platforms:
        return None

    result = process.extractOne(user_input, valid_platforms, score_cutoff=threshold)
    return result[0] if result else None
