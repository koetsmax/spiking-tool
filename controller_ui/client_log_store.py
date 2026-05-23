from __future__ import annotations

from collections import defaultdict, deque


class ClientLogStore:
    def __init__(self, max_lines_per_client: int = 3000) -> None:
        self._max_lines = max_lines_per_client
        self._logs: dict[str, deque[str]] = defaultdict(
            lambda: deque(maxlen=self._max_lines)
        )

    def append(self, client_name: str, message: str) -> None:
        self._logs[client_name].append(message)

    def get_lines(self, client_name: str) -> list[str]:
        return list(self._logs.get(client_name, ()))

    def clear_client(self, client_name: str) -> None:
        self._logs.pop(client_name, None)

    def client_names(self) -> list[str]:
        return list(self._logs.keys())
