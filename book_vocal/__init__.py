"""Book Vocal: lightweight tools for book-focused text assistance.

Running this file directly (``python book_vocal/__init__.py``) is supported as
an alias for the CLI, even when the package is not installed. When imported as
part of the package, the public API remains unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if __name__ == "__main__":
    # Allow direct execution without requiring installation by temporarily
    # adding the repository root to ``sys.path``.
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from book_vocal.cli import main

    raise SystemExit(main())

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
