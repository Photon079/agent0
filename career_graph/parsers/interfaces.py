from typing import Protocol, Dict, Any


class Parser(Protocol):
    """Parser transform raw input into the canonical parsed dict for GraphWriter."""

    def parse(self, raw: Any) -> Dict[str, Any]:
        ...