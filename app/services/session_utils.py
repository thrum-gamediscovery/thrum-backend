"""
Session utilities for managing conversation memory and state
"""
from app.db.models.session import Session

def initialize_session_memory(session: Session):
    """
    Initialize session memory fields if they don't exist
    """
    if not session.meta_data:
        session.meta_data = {}
    
    if 'asked_questions' not in session.meta_data:
        session.meta_data['asked_questions'] = []
    
    return session

def get_asked_questions(session: Session) -> list:
    """
    Get list of asked questions from session metadata
    """
    if not session.meta_data:
        return []
    return session.meta_data.get('asked_questions', [])

def mark_question_asked(session: Session, question_type: str):
    """
    Mark a question type as asked in session metadata
    """
    if not session.meta_data:
        session.meta_data = {}
    
    asked_questions = session.meta_data.get('asked_questions', [])
    if question_type not in asked_questions:
        asked_questions.append(question_type)
        session.meta_data['asked_questions'] = asked_questions

def has_asked_question(session: Session, question_type: str) -> bool:
    """
    Check if a question type has been asked
    """
    asked_questions = get_asked_questions(session)
    return question_type in asked_questions