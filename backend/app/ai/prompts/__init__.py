"""Prompt templates are versioned modules in this package.

Each module exposes a `VERSION` string and a `render()` function that returns a
`RenderedPrompt`. Changing a prompt means a new version, never an edit in place. The prompts
themselves arrive with the features that use them (posting analysis, tailored draft).
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RenderedPrompt:
    """A prompt ready to send: the version that produced it, the system text and the user text."""

    version: str
    system: str
    user: str


@runtime_checkable
class PromptModule(Protocol):
    VERSION: str

    def render(self, *args: object, **kwargs: object) -> RenderedPrompt: ...
