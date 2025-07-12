from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm.attributes import flag_modified
from app.db.models.interaction import Interaction
from app.db.models.enums import SenderEnum

class InteractionTracker:
    def __init__(self, user, session, db):
        self.user = user
        self.session = session
        self.db = db

    async def log_interaction(self, user_input: str, thrum_response: str, metadata: Dict[Any, Any] = None):
        """Log user and Thrum interactions with metadata"""
        
        # Log user message
        user_interaction = Interaction(
            session_id=self.session.session_id,
            sender=SenderEnum.User,
            content=user_input,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.db.add(user_interaction)
        
        # Log Thrum response
        thrum_interaction = Interaction(
            session_id=self.session.session_id,
            sender=SenderEnum.Thrum,
            content=thrum_response,
            timestamp=datetime.utcnow(),
            metadata={"response_type": "natural_conversation"}
        )
        self.db.add(thrum_interaction)
        
        # Update session metadata
        await self._update_session_stats()
        
        self.db.commit()

    async def _update_session_stats(self):
        """Update session statistics"""
        if not self.session.meta_data:
            self.session.meta_data = {}
        
        # Update interaction counts
        total_interactions = len(self.session.interactions) + 2  # +2 for current exchange
        self.session.meta_data["total_interactions"] = total_interactions
        self.session.meta_data["last_interaction"] = datetime.utcnow().isoformat()
        
        # Track conversation depth
        if total_interactions <= 3:
            self.session.meta_data["conversation_stage"] = "introduction"
        elif total_interactions <= 8:
            self.session.meta_data["conversation_stage"] = "discovery"
        elif total_interactions <= 15:
            self.session.meta_data["conversation_stage"] = "recommendation"
        else:
            self.session.meta_data["conversation_stage"] = "ongoing"
        
        flag_modified(self.session, "meta_data")

    def get_conversation_context(self) -> Dict:
        """Get current conversation context"""
        recent_interactions = self.session.interactions[-6:] if self.session.interactions else []
        
        return {
            "total_interactions": len(self.session.interactions),
            "recent_messages": [
                {
                    "sender": interaction.sender.name,
                    "content": interaction.content,
                    "timestamp": interaction.timestamp.isoformat() if interaction.timestamp else None
                }
                for interaction in recent_interactions
            ],
            "conversation_stage": self.session.meta_data.get("conversation_stage", "introduction") if self.session.meta_data else "introduction",
            "user_engagement": self._calculate_engagement_score()
        }

    def _calculate_engagement_score(self) -> str:
        """Calculate user engagement level"""
        if not self.session.interactions:
            return "new"
        
        recent_interactions = self.session.interactions[-5:]
        avg_length = sum(len(i.content) for i in recent_interactions) / len(recent_interactions)
        
        if avg_length > 50:
            return "high"
        elif avg_length > 20:
            return "medium"
        else:
            return "low"

async def create_interaction_tracker(user, session, db):
    """Factory function to create interaction tracker"""
    return InteractionTracker(user, session, db)