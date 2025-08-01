def maybe_add_link_hint(user_prompt: str, platform_link: str, request_link: bool) -> str:
    """Adds a casual store link offer inline so the model naturally includes it."""
    if platform_link and not request_link:
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