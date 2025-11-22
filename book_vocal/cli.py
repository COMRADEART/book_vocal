"""Command-line helpers for exploring a book with :class:`BookAssistant`."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assistant import BookAssistant
from .voice import VoiceProfile


SECTION_SEPARATOR = "\n" + "-" * 60 + "\n"


def _print_section(title: str) -> None:
    print(SECTION_SEPARATOR)
    print(title)
    print(SECTION_SEPARATOR)


def _validate_book_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        raise SystemExit(f"Book file not found: {resolved}")
    return resolved


def _load_voice_profile(path: str | Path) -> VoiceProfile:
    profile_path = Path(path)
    if not profile_path.exists():
        raise SystemExit(f"Voice profile not found: {profile_path}")

    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return VoiceProfile.from_dict(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explore a book with search, summary, and quick character helpers.",
    )
    parser.add_argument("--book", required=True, help="Path to the book text file (UTF-8).")
    parser.add_argument("--question", help="Question to search for in the book.")
    parser.add_argument(
        "--context",
        type=int,
        default=1,
        help="Number of neighboring sentences to include for answers (default: 1).",
    )
    parser.add_argument(
        "--summary",
        type=int,
        metavar="N",
        help="Number of sentences to include in the extractive summary.",
    )
    parser.add_argument(
        "--characters",
        type=int,
        metavar="N",
        help="Show the top N recurring capitalized names.",
    )
    parser.add_argument(
        "--keywords",
        type=int,
        metavar="N",
        help="Show the top N informative keywords.",
    )
    parser.add_argument(
        "--voice-profile",
        metavar="VOICE.json",
        help="Optional JSON file describing a personalized, multilingual voice.",
    )
    parser.add_argument(
        "--language",
        metavar="LANG",
        help="Target language code for narration (defaults to voice profile primary).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    book_path = _validate_book_path(args.book)
    voice_profile = _load_voice_profile(args.voice_profile) if args.voice_profile else None

    assistant = BookAssistant.from_file(book_path)

    any_action = False

    if args.question:
        any_action = True
        _print_section("Contextual answer")
        answer = assistant.contextual_answer(args.question, context_window=args.context)
        print(answer)

        _print_section("Top passages")
        for result in assistant.search(args.question, context_window=args.context):
            print(f"[score={result.score:.3f}] {result.sentence}")

        if voice_profile:
            _print_section("Narration plan")
            plan = assistant.narration_plan(
                args.question,
                voice_profile,
                language=args.language,
                context_window=args.context,
            )
            print(f"Language: {plan.language}")
            print(f"Source sentence indices: {plan.source_indices or 'none'}")
            print("Voice prompt:\n" + plan.voice_prompt)

    if args.summary:
        any_action = True
        _print_section(f"Summary (top {args.summary} sentences)")
        summary = assistant.summarize(max_sentences=args.summary)
        for item in summary:
            print(f"[{item.index + 1}] {item.sentence}")

    if args.characters:
        any_action = True
        _print_section("Character glossary")
        glossary = assistant.character_glossary(limit=args.characters)
        for name, count in glossary:
            print(f"{name} ({count})")

    if args.keywords:
        any_action = True
        _print_section("Top keywords")
        for keyword, score in assistant.top_keywords(limit=args.keywords):
            print(f"{keyword}: {score:.3f}")

    if not any_action:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover - manual invocation entrypoint
    main()
