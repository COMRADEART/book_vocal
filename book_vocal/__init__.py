"""Book Vocal: lightweight tools for book-focused text assistance."""

from .assistant import BookAssistant, NarrationPlan, SearchResult, SummaryResult
from .voice import VoiceProfile, build_voice_profile

__all__ = [
    "BookAssistant",
    "NarrationPlan",
    "SearchResult",
    "SummaryResult",
    "VoiceProfile",
    "build_voice_profile",
]
