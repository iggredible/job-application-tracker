"""The pure functions that make the LLM calls.

They take an `AIClient`, make one call and return validated output. They touch no database: the
service around each one gathers the inputs and saves the result, and the eval (feature 16) calls
these directly with an in-memory log sink.
"""

from collections.abc import Sequence

from app.ai.prompts import PromptModule, posting_analysis, tailor_resume
from app.ai.schemas import PostingAnalysisOutput, Requirement, TailoredResume
from app.ai.types import AIClient, AIResult
from app.models import AIFeature
from app.services.retrieval import RetrievedExample, format_examples

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


def tailor(
    client: AIClient,
    *,
    base_resume: str,
    posting_text: str,
    keywords: list[str],
    application_id: int | None,
    examples: Sequence[RetrievedExample] = (),
    prompt: PromptModule = tailor_resume,
) -> AIResult[TailoredResume]:
    """Write a tailored resume from the base resume, the posting and the approved keywords.

    One call, logged by the client. The output is the model's structure, validated by the
    client; the Markdown is rendered from it by `render_tailored_markdown()`. A failed call
    raises the client's `AIError`.

    `examples` are past approved resumes that show style and emphasis only. They fill the
    prompt's examples section, which is part of the prompt, so the version does not change, and
    their resume ids are logged on the call. With none, the section stays empty.

    `prompt` is the tailoring prompt module. It defaults to v1, which is what the app runs: the
    services do not pass it. Only the eval passes another one (v2), to measure it.
    """
    return client.generate(
        feature=AIFeature.TAILOR_RESUME,
        prompt=prompt.render(
            base_resume, posting_text, keywords, examples=format_examples(examples)
        ),
        output_model=TailoredResume,
        application_id=application_id,
        retrieved_example_ids=[example.resume_id for example in examples],
    )


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
