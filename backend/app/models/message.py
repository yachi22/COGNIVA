"""
Re-export Message model from conversation.py for modular imports.
"""
from app.models.conversation import Message

__all__ = ["Message"]
