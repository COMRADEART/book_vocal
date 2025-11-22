# book_vocal

Lightweight, offline-friendly helpers for turning any plain-text book into a quick personal assistant. The `BookAssistant` class builds a sentence-level index so you can search, summarize, and extract recurring characters without external API calls.

## Quick start
1. Save your book as a UTF-8 text file, e.g. `novel.txt`.
2. Ask questions, summarize, or surface characters via the CLI:

```bash
python -m book_vocal.cli --book novel.txt --question "Who rescues the captain?" --summary 4 --characters 8 --keywords 6
```

The command prints a contextual passage for the question, the top matching sentences, an extractive summary, recurring character names, and the most informative keywords.

### Add a personalized, multilingual voice
Create a lightweight voice profile that points to your reference vocals for one or more languages:

```json
{
  "name": "Amina",
  "languages": ["en", "fr"],
  "style": "warm and calm",
  "sample_clips": {
    "en": "samples/amina_en.wav",
    "fr": "samples/amina_fr.wav"
  },
  "articulation_notes": "Soft consonants, gentle pace",
  "warmup_phrase": "Welcome back to the story"
}
```

Pass the profile to the CLI to produce a narration prompt that downstream TTS systems can use to speak in your voice:

```bash
python -m book_vocal.cli --book novel.txt --question "Who rescues the captain?" --voice-profile voice.json --language fr
```

## Programmatic usage

```python
from book_vocal import BookAssistant

assistant = BookAssistant.from_file("novel.txt")

# Ask a question and get neighboring context
print(assistant.contextual_answer("How do they escape the city?", context_window=2))

# Extract a compact summary
top_sentences = assistant.summarize(max_sentences=5)
for item in top_sentences:
    print(f"Sentence #{item.index + 1}: {item.sentence}")

# Identify recurring characters
print(assistant.character_glossary(limit=10))

# Build a multilingual voice profile and generate a narration plan
from book_vocal import VoiceProfile

voice = VoiceProfile(
    name="Amina",
    languages=["en", "fr"],
    style="warm and calm",
    sample_clips={"en": "samples/amina_en.wav", "fr": "samples/amina_fr.wav"},
)
plan = assistant.narration_plan("Who rescues the captain?", voice, language="fr")
print(plan.voice_prompt)
```
