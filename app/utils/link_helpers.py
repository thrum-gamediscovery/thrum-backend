from app.services.user_profile_update import consume_pending_action
from sqlalchemy.orm.attributes import flag_modified

async def maybe_add_link_hint(db, session, user_prompt: str, platform_link: str) -> str:
    """Adds a casual store link offer inline so the model naturally includes it."""
    pending_action = session.meta_data.get('pending_action') if session.meta_data else None
    ask_for_link = pending_action.get('type') == 'send_link' if pending_action else False
    request_link = session.meta_data.get('request_link')
    print(f"platform_link : {platform_link}, request_link : {request_link} , ask_for_link : {ask_for_link}")
    if platform_link and not request_link and ask_for_link:
        await consume_pending_action(db,session)
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data['ask_for_link'] = True
        flag_modified(session, "meta_data")
        db.commit()
        user_prompt += f"""
        ---
        The user hasn’t asked for the store link yet, but it’s available: {platform_link}.
        
        Reply casually in a friend-like tone.
        - Slip in a short, varied offer for the link near the end of your message.
        - Keep it in flow with the current conversation.
        - Example tone (don’t repeat exactly): “Want me to send the link?”, “Need the link for it?”, “Should I drop the store link?”
        - Only one sentence offering it, no over-explaining.
        """
    return user_prompt