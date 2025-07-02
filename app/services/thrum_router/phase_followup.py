from app.tasks.followup import handle_followup_logic

async def handle_followup(user_input, session, user):
    return await handle_followup_logic(user_input, session)
