from __future__ import annotations


class StubAdapter:
    def __init__(self, result: str = "https://example.com/result.png", exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc

    async def process_image(self, image_bytes: bytes, image_mime: str, prompt: str) -> str:
        if self._exc is not None:
            raise self._exc
        return self._result

