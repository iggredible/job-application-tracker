"""The pure functions that make the LLM calls.

They take an `AIClient`, make one call and return validated output. They touch no database: the
service around each one gathers the inputs and saves the result, and the eval (feature 16) calls
these directly with an in-memory log sink.
"""

from app.ai.prompts import posting_analysis
from app.ai.schemas import PostingAnalysisOutput, Requirement
from app.ai.types import AIClient, AIResult
from app.models import AIFeature

MAX_KEYWORDS = 25


def analyze(
    client: AIClient, *, posting_text: str, application_id: int | None
) -> AIResult[PostingAnalysisOutput]:
    """Extract requirements and keywords from a posting. One call, logged by the client.

    The model's output is parsed and validated by the client. Lowercase, deduplication and the
    keyword cap are enforced here, in code. Extra keywords are trimmed, not treated as a
    failure. A failed call raises the client's `AIError`.
    """
    result = client.generate(
        feature=AIFeature.POSTING_ANALYSIS,
        prompt=posting_analysis.render(posting_text),
        output_model=PostingAnalysisOutput,
        application_id=application_id,
    )
    return AIResult(output=_normalize(result.output), ai_call_id=result.ai_call_id)


def _normalize(output: PostingAnalysisOutput) -> PostingAnalysisOutput:
    requirements = [
        Requirement(text=text, category=requirement.category)
        for requirement in output.requirements
        if (text := requirement.text.strip())
    ]
    # dict.fromkeys drops duplicates and keeps the first occurrence's position.
    keywords = list(
        dict.fromkeys(k for keyword in output.keywords if (k := keyword.strip().lower()))
    )
    return PostingAnalysisOutput(requirements=requirements, keywords=keywords[:MAX_KEYWORDS])
