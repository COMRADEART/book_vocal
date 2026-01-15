from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from .memory import BubbleMemory, BubbleMemoryStore, build_memory, compute_book_id, default_state_dir
from .voice import VoiceProfile

if TYPE_CHECKING:
    from .assistant import BookAssistant, SummaryResult

try:
    from flask import Flask, redirect, render_template_string, request, url_for
except ImportError:  # pragma: no cover - optional dependency
    Flask = None  # type: ignore[assignment]


STATE_DIR = default_state_dir()
BOOK_DIR = STATE_DIR / "books"
MEMORY_PATH = STATE_DIR / "bubble_memory.json"

VOICE_PRESETS = {
    "chatgpt": {
        "name": "ChatGPT",
        "style": "clear, friendly, and supportive",
        "notes": "Reference voice: ChatGPT-style narration.",
    },
    "gemini": {
        "name": "Gemini",
        "style": "warm, articulate, and curious",
        "notes": "Reference voice: Gemini-style narration.",
    },
    "custom": {
        "name": "Custom",
        "style": "natural and warm",
        "notes": "",
    },
}


def _ensure_flask() -> None:
    if Flask is None:
        raise SystemExit("Flask is required for the web app. Install with: pip install flask")


def _save_book_text(book_id: str, text: str) -> Path:
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    path = BOOK_DIR / f"{book_id}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _load_book_text(book_id: str) -> str:
    path = BOOK_DIR / f"{book_id}.txt"
    return path.read_text(encoding="utf-8")


def _format_summary(items: List["SummaryResult"]) -> str:
    return " ".join(item.sentence for item in items)


def _build_voice_profile(
    preset_key: str,
    *,
    language: str,
    style_override: Optional[str],
) -> Tuple[VoiceProfile, str]:
    preset = VOICE_PRESETS.get(preset_key, VOICE_PRESETS["custom"])
    style = style_override or preset["style"]
    profile = VoiceProfile(name=preset["name"], languages=[language], style=style, sample_clips={})
    return profile, preset["notes"]


def _update_memory(
    store: BubbleMemoryStore,
    book_id: str,
    assistant: "BookAssistant",
    *,
    last_index: int,
    last_question: Optional[str],
) -> BubbleMemory:
    summary_items = assistant.summarize_span(max(0, last_index - 2), last_index + 3, max_sentences=2)
    summary_text = _format_summary(summary_items)
    memory = build_memory(
        book_id,
        last_index=last_index,
        last_question=last_question,
        last_summary=summary_text,
    )
    store.save(memory)
    return memory


def create_app() -> "Flask":
    _ensure_flask()
    try:
        from .assistant import BookAssistant
    except (SyntaxError, IndentationError) as exc:
        raise SystemExit(
            "BookAssistant failed to import. Please ensure your local checkout is up to date and "
            "uses compatible typing (no `|` union syntax on Python <3.10)."
        ) from exc

    app = Flask(__name__)
    store = BubbleMemoryStore(MEMORY_PATH)

    @app.route("/", methods=["GET", "POST"])
    def index() -> str:
        output_sections: List[Tuple[str, str]] = []
        book_id = request.values.get("book_id")
        memory = store.load(book_id) if book_id else None

        if request.method == "POST":
            action = request.form.get("action")
            if action == "upload":
                file = request.files.get("book_file")
                if file and file.filename:
                    text = file.read().decode("utf-8", errors="ignore")
                    book_id = compute_book_id(text)
                    _save_book_text(book_id, text)
                    memory = store.load(book_id)
                    output_sections.append(("Upload", "Book uploaded successfully."))
                else:
                    output_sections.append(("Upload", "Please choose a UTF-8 text file."))
            elif action in {"ask", "read", "recap"} and book_id:
                text = _load_book_text(book_id)
                assistant = BookAssistant(text)
                language = request.form.get("language") or "en"
                preset_key = request.form.get("voice_preset") or "custom"
                style_override = request.form.get("style_override") or None
                voice_profile, preset_note = _build_voice_profile(
                    preset_key, language=language, style_override=style_override
                )

                if action == "ask":
                    question = request.form.get("question", "").strip()
                    if question:
                        hits = assistant.search(question, top_k=1, context_window=2)
                        if hits:
                            best = hits[0]
                            context = " ".join(best.context)
                            output_sections.append(("Answer", context))
                            memory = _update_memory(
                                store, book_id, assistant, last_index=best.index, last_question=question
                            )
                        else:
                            output_sections.append(("Answer", "No relevant passages were found."))
                    else:
                        output_sections.append(("Answer", "Add a question to search the book."))

                if action == "read":
                    start_index = memory.last_index if memory else 0
                    step = int(request.form.get("read_count", 3))
                    end_index = min(len(assistant.sentences), start_index + max(step, 1))
                    passage = " ".join(assistant.sentences[start_index:end_index])
                    output_sections.append(("Reading", passage))
                    memory = _update_memory(
                        store,
                        book_id,
                        assistant,
                        last_index=end_index - 1 if end_index > 0 else 0,
                        last_question=None,
                    )

                if action == "recap":
                    if memory and memory.last_summary:
                        output_sections.append(("Recap", memory.last_summary))
                    else:
                        summary_items = assistant.summarize_span(0, min(5, len(assistant.sentences)), 2)
                        output_sections.append(("Recap", _format_summary(summary_items)))

                if output_sections:
                    plan = assistant.narration_plan(
                        question="Continue the story",
                        voice=voice_profile,
                        language=language,
                        context_window=2,
                    )
                    note = f"{preset_note}\n\n" if preset_note else ""
                    output_sections.append(("Narration Prompt", note + plan.voice_prompt))

        template = """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>Book Vocal Assistant</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 32px; max-width: 960px; }
            section { margin-bottom: 24px; padding: 16px; border: 1px solid #ddd; border-radius: 8px; }
            textarea, input, select { width: 100%; padding: 8px; margin-top: 4px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
            .output { white-space: pre-wrap; background: #fafafa; padding: 12px; border-radius: 6px; }
          </style>
        </head>
        <body>
          <h1>Book Vocal Assistant</h1>
          <p>Upload a book and get multilingual, styled narration prompts with bubble memory recaps.</p>

          <section>
            <h2>1) Upload a book</h2>
            <form method="post" enctype="multipart/form-data">
              <input type="hidden" name="action" value="upload">
              <input type="file" name="book_file" accept=".txt">
              <button type="submit">Upload</button>
            </form>
            {% if book_id %}
              <p><strong>Loaded book ID:</strong> {{ book_id }}</p>
            {% endif %}
          </section>

          {% if book_id %}
          <section>
            <h2>2) Configure voice & style</h2>
            <form method="post">
              <input type="hidden" name="book_id" value="{{ book_id }}">
              <div class="grid">
                <label>Voice preset
                  <select name="voice_preset">
                    <option value="chatgpt">ChatGPT</option>
                    <option value="gemini">Gemini</option>
                    <option value="custom" selected>Custom</option>
                  </select>
                </label>
                <label>Language code
                  <input type="text" name="language" value="en">
                </label>
                <label>Style override
                  <input type="text" name="style_override" placeholder="e.g., cinematic, calm, playful">
                </label>
              </div>

              <h3>Ask a question</h3>
              <input type="hidden" name="action" value="ask">
              <textarea name="question" rows="2" placeholder="Ask something about the book"></textarea>
              <button type="submit">Ask</button>
            </form>

            <form method="post" style="margin-top: 16px;">
              <input type="hidden" name="book_id" value="{{ book_id }}">
              <input type="hidden" name="action" value="read">
              <div class="grid">
                <label>Read next (sentences)
                  <input type="number" name="read_count" value="3" min="1" max="10">
                </label>
              </div>
              <button type="submit">Read next</button>
            </form>

            <form method="post" style="margin-top: 16px;">
              <input type="hidden" name="book_id" value="{{ book_id }}">
              <input type="hidden" name="action" value="recap">
              <button type="submit">Recap last session</button>
            </form>
          </section>
          {% endif %}

          {% if memory %}
          <section>
            <h2>Bubble memory</h2>
            <p><strong>Last position:</strong> Sentence {{ memory.last_index + 1 }}</p>
            {% if memory.last_question %}
              <p><strong>Last question:</strong> {{ memory.last_question }}</p>
            {% endif %}
            {% if memory.last_summary %}
              <div class="output">{{ memory.last_summary }}</div>
            {% endif %}
            <p><em>Last updated: {{ memory.updated_at }}</em></p>
          </section>
          {% endif %}

          {% if output_sections %}
          <section>
            <h2>Output</h2>
            {% for title, content in output_sections %}
              <h3>{{ title }}</h3>
              <div class="output">{{ content }}</div>
            {% endfor %}
          </section>
          {% endif %}
        </body>
        </html>
        """

        return render_template_string(
            template,
            book_id=book_id,
            output_sections=output_sections,
            memory=memory,
        )

    return app


def main() -> int:
    _ensure_flask()
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
