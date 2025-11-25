from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Union


@dataclass
class VoiceProfile:
    """Describes a personalized voice, including multilingual samples.

    The profile is intentionally model-agnostic: it only captures the target
    languages, vocal style, and pointers to reference clips so downstream text
    to speech (TTS) systems can clone or condition on the speaker.
    """

    name: str
    languages: Sequence[str]
    style: str = "natural and warm"
    sample_clips: Dict[str, Path] = field(default_factory=dict)
    articulation_notes: Optional[str] = None
    warmup_phrase: Optional[str] = None

    def __post_init__(self) -> None:
        self.languages = list(self.languages)
        self.sample_clips = {language: Path(path) for language, path in self.sample_clips.items()}

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "VoiceProfile":
        """Build a profile from a JSON/YAML-like mapping."""

        return cls(
            name=str(payload["name"]),
            languages=payload.get("languages", []) or [],
            style=str(payload.get("style", "natural and warm")),
            sample_clips={
                language: Path(path)
                for language, path in (payload.get("sample_clips", {}) or {}).items()
            },
            articulation_notes=payload.get("articulation_notes") or None,
            warmup_phrase=payload.get("warmup_phrase") or None,
        )

    def default_language(self) -> str:
        """Return the primary language, preferring the first declared entry."""

        if not self.languages:
            raise ValueError("VoiceProfile.languages must include at least one language.")
        return self.languages[0]

    def clip_for_language(self, language: Optional[str] = None) -> Optional[Path]:
        """Return the most relevant sample clip for the requested language.

        Falls back to the default language when a language-specific clip is not
        available, enabling graceful multilingual narration plans.
        """

        target = language or self.default_language()
        if target in self.sample_clips:
            return self.sample_clips[target]
        if self.sample_clips:
            return next(iter(self.sample_clips.values()))
        return None

    def describe(self) -> str:
        """Human-friendly description of the voice persona."""

        lines = [
            f"Voice: {self.name}",
            f"Style: {self.style}",
            f"Languages: {', '.join(self.languages)}",
        ]
        if self.articulation_notes:
            lines.append(f"Notes: {self.articulation_notes}")
        if self.warmup_phrase:
            lines.append(f"Warmup phrase: {self.warmup_phrase}")
        clip = self.clip_for_language()
        if clip:
            lines.append(f"Reference clip: {clip}")
        return "\n".join(lines)

    def narration_prompt(self, script: str, language: Optional[str] = None) -> str:
        """Generate a structured prompt describing how to voice a script."""

        target_language = language or self.default_language()
        clip = self.clip_for_language(target_language)
        header = [
            f"Narrate in {target_language} with voice '{self.name}'",
            f"Style: {self.style}",
        ]
        if clip:
            header.append(f"Use reference clip for timbre: {clip}")
        if self.articulation_notes:
            header.append(f"Articulation notes: {self.articulation_notes}")
        if self.warmup_phrase:
            header.append(f"Warmup phrase: {self.warmup_phrase}")

        body = script.strip()
        if not body:
            raise ValueError("Narration script cannot be empty.")

        return "\n".join(header + ["", body])


def build_voice_profile(
    name: str,
    languages: Iterable[str],
    sample_clip: Union[str, Path, None] = None,
    *,
    style: str = "natural and warm",
    articulation_notes: Optional[str] = None,
    warmup_phrase: Optional[str] = None,
) -> VoiceProfile:
    """Quick factory for single-clip profiles.

    This helper keeps configuration lightweight for demos: pass a primary
    language and an optional clip path, and it will wire a :class:`VoiceProfile`
    with sensible defaults.
    """

    clip_map: Dict[str, Path] = {}
    languages = list(languages)
    if sample_clip and languages:
        clip_map[languages[0]] = Path(sample_clip)

    return VoiceProfile(
        name=name,
        languages=languages,
        style=style,
        sample_clips=clip_map,
        articulation_notes=articulation_notes,
        warmup_phrase=warmup_phrase,
    )
