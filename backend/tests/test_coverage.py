"""keyword_coverage(): the pure function. No database, no AI."""

import pytest

from app.services.coverage import keyword_coverage


def covered(keywords: list[str], text: str) -> list[str]:
    return keyword_coverage(keywords, text).covered


# --- Word boundaries ---------------------------------------------------------------------


def test_a_keyword_does_not_match_inside_a_longer_word():
    result = keyword_coverage(["java"], "Built apps in JavaScript.")
    assert result.covered == []
    assert result.missing == ["java"]


def test_a_keyword_matches_as_a_whole_word_next_to_punctuation():
    assert covered(["java"], "Skills: Java, Kotlin") == ["java"]
    assert covered(["java"], "(Java)") == ["java"]
    assert covered(["java"], "Java") == ["java"]


def test_a_keyword_does_not_match_as_a_prefix_or_suffix_of_a_word():
    assert covered(["rail"], "Ruby on Rails") == []
    assert covered(["script"], "JavaScript") == []


# --- Case and whitespace -----------------------------------------------------------------


def test_matching_ignores_case():
    assert covered(["PostgreSQL"], "postgresql and POSTGRESQL") == ["PostgreSQL"]
    assert covered(["postgresql"], "Experience with PostgreSQL") == ["postgresql"]


def test_whitespace_in_the_resume_is_normalized():
    text = "Ruby   on\n  Rails\tservices"
    assert covered(["ruby on rails"], text) == ["ruby on rails"]


def test_whitespace_in_the_keyword_is_normalized():
    assert covered(["ruby   on  rails"], "Ruby on Rails") == ["ruby   on  rails"]


# --- Terms with punctuation --------------------------------------------------------------


@pytest.mark.parametrize(
    ("keyword", "text"),
    [
        ("c++", "Languages: C++, Go"),
        ("c++", "I write C++"),
        ("c++", "(C++)"),
        ("c++", "C++ and Rust"),
        ("ci/cd", "Built CI/CD pipelines"),
        ("ci/cd", "Owned CI/CD."),
        ("ci/cd", "tools (CI/CD)"),
        (".net", "Experience with .NET, C#"),
        (".net", "Built on .NET"),
        (".net", "(.NET)"),
        ("node.js", "Node.js services"),
        ("node.js", "Backend in Node.js."),
        ("node.js", "Node.js"),
    ],
)
def test_terms_with_punctuation_match(keyword: str, text: str):
    assert covered([keyword], text) == [keyword]


@pytest.mark.parametrize(
    ("keyword", "text"),
    [
        ("c++", "c#"),
        ("c++", "cpp"),
        ("node.js", "nodexjs"),
        ("node.js", "Node.jsx"),
        (".net", "asp.net"),
        (".net", "netflix"),
        ("ci/cd", "CI-CD"),
        ("ci/cd", "ci/cdn"),
    ],
)
def test_terms_with_punctuation_do_not_match_lookalikes(keyword: str, text: str):
    assert covered([keyword], text) == []


def test_characters_that_mean_something_in_a_regex_are_taken_literally():
    # An unescaped "c++" is an invalid pattern; an unescaped "." matches any character.
    assert covered(["c++", "a.b", "(x)", "[y]", "z*"], "a.b (x) [y] z* c++") == [
        "c++",
        "a.b",
        "(x)",
        "[y]",
        "z*",
    ]
    assert covered(["a.b"], "axb") == []


# --- Phrases -----------------------------------------------------------------------------


def test_a_multi_word_keyword_matches_as_a_phrase():
    assert covered(["background jobs"], "Moved work into background jobs") == ["background jobs"]


def test_a_phrase_does_not_match_when_its_words_are_apart():
    text = "Ran jobs in the background"
    assert covered(["background jobs"], text) == []
    assert covered(["background jobs"], "background and jobs") == []


def test_a_phrase_does_not_match_with_its_words_in_another_order():
    assert covered(["ruby on rails"], "rails on ruby") == []


def test_a_phrase_needs_whole_words_at_both_ends():
    assert covered(["rest apis"], "Built REST APIs") == ["rest apis"]
    assert covered(["rest apis"], "Built forest apis") == []


# --- Empty input -------------------------------------------------------------------------


def test_no_keywords_gives_empty_lists_and_a_zero_ratio():
    result = keyword_coverage([], "Anything at all")
    assert result.covered == []
    assert result.missing == []
    assert result.ratio == 0.0


def test_an_empty_resume_leaves_every_keyword_missing():
    for text in ("", "   \n\t "):
        result = keyword_coverage(["python", "sql"], text)
        assert result.covered == []
        assert result.missing == ["python", "sql"]
        assert result.ratio == 0.0


def test_blank_keywords_are_ignored():
    result = keyword_coverage(["", "   ", "python"], "I like python")
    assert result.covered == ["python"]
    assert result.missing == []
    assert result.ratio == 1.0


def test_empty_keywords_and_empty_resume_do_not_divide_by_zero():
    result = keyword_coverage([], "")
    assert (result.covered, result.missing, result.ratio) == ([], [], 0.0)


# --- Result shape ------------------------------------------------------------------------


def test_covered_and_missing_keep_the_keyword_order_and_casing():
    result = keyword_coverage(
        ["PostgreSQL", "Kubernetes", "Ruby on Rails", "AWS"],
        "ruby on rails and postgresql",
    )
    assert result.covered == ["PostgreSQL", "Ruby on Rails"]
    assert result.missing == ["Kubernetes", "AWS"]


def test_duplicate_keywords_count_once_whatever_their_case():
    result = keyword_coverage(["React", "react", "REACT", "go"], "React")
    assert result.covered == ["React"]
    assert result.missing == ["go"]
    assert result.ratio == 0.5


@pytest.mark.parametrize(
    ("resume", "expected"),
    [
        ("", 0.0),
        ("a", 0.25),
        ("a b", 0.5),
        ("a b c", 0.75),
        ("a b c d", 1.0),
    ],
)
def test_ratio_is_covered_over_the_unique_keywords(resume: str, expected: float):
    assert keyword_coverage(["a", "b", "c", "d"], resume).ratio == expected


def test_every_keyword_is_either_covered_or_missing():
    keywords = ["python", "sql", "c++", "ci/cd", "react"]
    result = keyword_coverage(keywords, "python and c++")
    assert sorted(result.covered + result.missing) == sorted(keywords)
    assert not set(result.covered) & set(result.missing)


def test_the_inputs_are_not_changed():
    keywords = ["Python", "python"]
    keyword_coverage(keywords, "python")
    assert keywords == ["Python", "python"]
