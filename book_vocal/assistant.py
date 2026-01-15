from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from .voice import VoiceProfile


_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class SearchResult:
    """An individual search hit extracted from the book text."""

    sentence: str
    score: float
    index: int
    context: List[str]


@dataclass
class SummaryResult:
    """Represents a single sentence that is part of a summary."""

    sentence: str
    index: int
    score: float


@dataclass
class NarrationPlan:
    """Structured narration details for downstream text to speech (TTS)."""

    language: str
    script: str
    voice_prompt: str
    source_indices: List[int]


class BookAssistant:
    """Lightweight text tools for exploring and summarizing a book.

    The assistant keeps a sentence-level index of the book text and provides
    keyword search, extractive summaries, a quick character glossary, and a
    context-aware answer helper that surfaces nearby sentences.
    """

    def __init__(self, text: str) -> None:
        normalized = text.strip()
        self.raw_text = normalized
        self.sentences = self._split_sentences(normalized)
        self._tokenized = [self._tokenize(sentence) for sentence in self.sentences]
        self._idf = self._compute_idf(self._tokenized)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "BookAssistant":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        return cls(text)

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        raw = _SENTENCE_RE.split(text.replace("\n", " "))
        return [sentence.strip() for sentence in raw if sentence.strip()]

    @staticmethod
    def _tokenize(sentence: str) -> List[str]:
        return [token.lower() for token in _WORD_RE.findall(sentence)]

    @staticmethod
    def _compute_idf(tokenized_sentences: Sequence[Sequence[str]]):
        document_count = Counter()
        for sentence_tokens in tokenized_sentences:
            for token in set(sentence_tokens):
                document_count[token] += 1

        total_documents = len(tokenized_sentences)
        idf = {}
        for token, freq in document_count.items():
            idf[token] = math.log((1 + total_documents) / (1 + freq)) + 1
        return idf

    def _tfidf_score(self, query_tokens: Sequence[str], sentence_tokens: Sequence[str]) -> float:
        if not query_tokens or not sentence_tokens:
            return 0.0
        sentence_length = len(sentence_tokens)
        tf = Counter(sentence_tokens)
        return sum((tf[token] / sentence_length) * self._idf.get(token, 0.0) for token in query_tokens)

    def _context_window(self, index: int, window: int = 1) -> List[str]:
        start = max(0, index - window)
        end = min(len(self.sentences), index + window + 1)
        return self.sentences[start:end]

    def search(self, query: str, top_k: int = 5, context_window: int = 1) -> List[SearchResult]:
        """Return the top sentences that best match the query keywords."""

        query_tokens = self._tokenize(query)
        scored: List[SearchResult] = []
        for idx, tokens in enumerate(self._tokenized):
            score = self._tfidf_score(query_tokens, tokens)
            if score <= 0:
                continue
            context = self._context_window(idx, window=context_window)
            scored.append(
                SearchResult(
                    sentence=self.sentences[idx],
                    score=score,
                    index=idx,
                    context=context,
                )
            )
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def summarize(self, max_sentences: int = 5) -> List[SummaryResult]:
        """Generate an extractive summary of the book.

        Sentences are ranked using TF-IDF against the most informative words
        (excluding very short words). The top sentences are returned in their
        original order so the summary reads smoothly.
        """

        if not self.sentences:
            return []

        vocabulary = Counter(token for tokens in self._tokenized for token in tokens)
        candidate_keywords = [word for word, _ in vocabulary.most_common(50) if len(word) > 3]
        scored: List[SummaryResult] = []
        for idx, tokens in enumerate(self._tokenized):
            primary_score = self._tfidf_score(candidate_keywords, tokens)
            position_bonus = 0.2 * (1 - idx / max(len(self.sentences), 1))
            score = primary_score + position_bonus
            scored.append(
                SummaryResult(
                    sentence=self.sentences[idx],
                    index=idx,
                    score=score,
                )
            )

        scored.sort(key=lambda result: result.score, reverse=True)
        top = sorted(scored[:max_sentences], key=lambda result: result.index)
        return top

    def summarize_span(
        self, start: int, end: int, max_sentences: int = 3
    ) -> List[SummaryResult]:
        """Summarize a specific sentence range in the book."""

        start = max(0, start)
        end = min(len(self.sentences), end)
        if start >= end:
            return []

        span_sentences = self.sentences[start:end]
        span_tokens = self._tokenized[start:end]
        vocabulary = Counter(token for tokens in span_tokens for token in tokens)
        candidate_keywords = [word for word, _ in vocabulary.most_common(50) if len(word) > 3]
        scored: List[SummaryResult] = []
        for offset, tokens in enumerate(span_tokens):
            primary_score = self._tfidf_score(candidate_keywords, tokens)
            position_bonus = 0.2 * (1 - offset / max(len(span_sentences), 1))
            score = primary_score + position_bonus
            scored.append(
                SummaryResult(
                    sentence=span_sentences[offset],
                    index=start + offset,
                    score=score,
                )
            )
        scored.sort(key=lambda result: result.score, reverse=True)
        top = sorted(scored[:max_sentences], key=lambda result: result.index)
        return top

    def character_glossary(self, limit: int = 10, min_occurrences: int = 2) -> List[Tuple[str, int]]:
        """Extract a simple character glossary using capitalized words.

        The heuristic focuses on repeated capitalized words that are unlikely to
        be at the start of a sentence-only capitalization.
        """

        stopwords = {
            "i",
            "the",
            "a",
            "an",
            "he",
            "she",
            "they",
            "his",
            "her",
            "mr",
            "mrs",
            "ms",
        }
        candidate_counts = Counter()
        for sentence in self.sentences:
            tokens = sentence.split()
            for token in tokens:
                stripped = token.strip(".,;:!?")
                if not stripped or not stripped[0].isupper():
                    continue
                cleaned = re.sub(r"[^A-Za-z']", "", stripped)
                lowered = cleaned.lower()
                if lowered in stopwords or len(cleaned) < 2:
                    continue
                candidate_counts[cleaned] += 1

        frequent = [(name, count) for name, count in candidate_counts.most_common() if count >= min_occurrences]
        return frequent[:limit]

    def contextual_answer(self, question: str, context_window: int = 1) -> str:
        """Return a context-aware snippet addressing the question.

        The method surfaces the best matching sentence along with neighboring
        sentences to provide light-weight grounding without requiring a model.
        """

        hits = self.search(question, top_k=1, context_window=context_window)
        if not hits:
            return "No relevant passages were found."

        result = hits[0]
        passage = " ".join(result.context)
        return passage

    def narration_plan(
        self,
        question: str,
        voice: VoiceProfile,
        *,
        language: Optional[str] = None,
        context_window: int = 1,
    ) -> NarrationPlan:
        """Build a multilingual narration plan for the given question.

        The plan packages a script grounded in the book and a structured prompt
        for downstream TTS systems that support personalized voice cloning.
        """

        hits = self.search(question, top_k=1, context_window=context_window)
        if not hits:
            script = "No relevant passages were found."
            source_indices: List[int] = []
        else:
            result = hits[0]
            script = " ".join(result.context)
            source_indices = list(range(max(0, result.index - context_window), result.index + context_window + 1))

        target_language = language or voice.default_language()
        voice_prompt = voice.narration_prompt(script, language=target_language)

        return NarrationPlan(
            language=target_language,
            script=script,
            voice_prompt=voice_prompt,
            source_indices=source_indices,
        )

    def top_keywords(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Return the most informative keywords ranked by IDF-weighted frequency."""

        stopwords = {
            "the",
            "and",
            "for",
            "that",
            "with",
            "this",
            "from",
            "have",
            "has",
            "was",
            "were",
            "are",
            "not",
            "you",
            "your",
            "his",
            "her",
            "she",
            "him",
            "had",
            "they",
            "them",
            "there",
            "here",
            "into",
            "out",
            "who",
            "what",
            "when",
            "where",
            "how",
            "why",
            "can",
            "could",
            "would",
            "should",
        }
        scores = Counter()
        for tokens in self._tokenized:
            for token in tokens:
                if len(token) < 3 or token in stopwords:
                    continue
                scores[token] += self._idf.get(token, 0.0)

        return scores.most_common(limit)

    def explain(self) -> str:
        """Human-readable description of available helpers."""

        lines = [
            "BookAssistant capabilities:",
            "- search(query): keyword search with TF-IDF scoring",
            "- summarize(max_sentences): extractive summary",
            "- character_glossary(): quick list of recurring names",
            "- contextual_answer(question): nearby passages for a question",
            "- top_keywords(): most informative terms",
        ]
        return "\n".join(lines)


def load_book(path: Union[str, Path]) -> BookAssistant:
    """Convenience loader that mirrors :meth:`BookAssistant.from_file`."""

    return BookAssistant.from_file(path)
