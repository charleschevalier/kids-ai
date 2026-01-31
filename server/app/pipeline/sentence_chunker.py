from __future__ import annotations

import re


class SentenceChunker:
    """Accumulates streaming LLM tokens and yields complete sentences.

    This allows TTS to start speaking the first sentence while the LLM
    is still generating subsequent ones.
    """

    # Sentence-ending punctuation followed by whitespace or end-of-string.
    _SENTENCE_END = re.compile(r"[.!?…]+(?:\s|$)")

    def __init__(self) -> None:
        self.buffer = ""

    def add_token(self, token: str) -> list[str]:
        """Add a token, return any complete sentences found."""
        self.buffer += token
        sentences: list[str] = []

        while True:
            match = self._SENTENCE_END.search(self.buffer)
            if not match:
                break
            end_pos = match.end()
            sentence = self.buffer[:end_pos].strip()
            self.buffer = self.buffer[end_pos:]
            if sentence:
                sentences.append(sentence)

        return sentences

    def flush(self) -> str | None:
        """Flush any remaining text as a final chunk."""
        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining if remaining else None

    def reset(self) -> None:
        self.buffer = ""
