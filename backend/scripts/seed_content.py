"""Fictional content for the seed: one base resume, company names, and what postings are made of.

Everything here is invented. No real person, employer or posting.
"""

from dataclasses import dataclass

from app.ai.schemas import Experience, TailoredResume
from app.models import Stage

# --- the base resume -----------------------------------------------------------------------------

NAME = "Riley Hartwell"
CONTACT = "riley.hartwell@example.com | Portland, OR"
EDUCATION = "B.Sc. Computer Science, Eastfield State University (2017)"

BASE_SUMMARY = (
    "Backend engineer who builds dependable, well-tested web services and likes owning them from "
    "design through production."
)

# Other summaries a tailored draft can use. None has a number the base resume lacks.
SUMMARY_VARIANTS = [
    "Backend engineer focused on clear APIs, steady delivery and services that are easy to run.",
    "Software engineer who turns messy requirements into simple, tested and observable systems.",
    "Engineer with a record of speeding up slow systems and keeping them reliable in production.",
    BASE_SUMMARY,
]

BASE_EXPERIENCES = [
    Experience(
        employer="Lumenfield Systems",
        title="Senior Backend Engineer",
        dates="Mar 2022 – Present",
        bullets=[
            "Cut p95 API latency from 480ms to 190ms with Redis caching in front of PostgreSQL",
            "Led the move of a Django monolith to FastAPI services serving 2M requests a day",
            "Built a Celery job pipeline that processes 40k invoices a night with retries",
            "Introduced contract tests with pytest that caught breaking API changes before release",
            "Mentored four engineers and ran the weekly design review for the payments team",
            "Reduced cloud spend by 22% by right-sizing AWS instances and removing idle resources",
        ],
    ),
    Experience(
        employer="Brightwater Labs",
        title="Software Engineer",
        dates="Jun 2019 – Feb 2022",
        bullets=[
            "Designed a REST API for partner integrations used by 60 customers",
            "Shipped a React and TypeScript dashboard that replaced a manual reporting process",
            "Moved deployments to Docker and GitHub Actions, cutting release time from 3h to 20min",
            "Wrote SQL migrations and query fixes that removed a nightly 9 minute lock on orders",
            "Added structured logging and alerts that halved the time to find production errors",
            "Pair-programmed with support to fix the 15 most reported bugs in one quarter",
        ],
    ),
    Experience(
        employer="Corvane Digital",
        title="Junior Developer",
        dates="Aug 2017 – May 2019",
        bullets=[
            "Built customer-facing features in Django for an online booking product",
            "Wrote unit tests that raised coverage from 31% to 74% across the main app",
            "Automated the weekly data export with a Python script and a Linux cron job",
            "Fixed accessibility issues across the site and documented the patterns used",
        ],
    ),
]

BASE_SKILLS = [
    "Python", "Django", "FastAPI", "PostgreSQL", "SQL", "Redis", "Celery", "REST APIs", "Docker",
    "AWS", "CI/CD", "GitHub Actions", "pytest", "React", "TypeScript", "Git", "Linux",
]  # fmt: skip

# Skills the base resume does not have. A flagged draft invents one of these.
INVENTED_SKILLS = ["Kubernetes", "Terraform", "GraphQL", "Go", "Elasticsearch", "Snowflake"]
INVENTED_TITLES = ["Staff Engineer", "Engineering Manager"]
INVENTED_NUMBERS = ["73%", "2.5x", "$1.4M", "300k"]  # none appears in the base resume


def base_resume() -> TailoredResume:
    """Everything the base resume says, in the structure the tailored drafts use."""
    return TailoredResume(
        summary=BASE_SUMMARY, experiences=BASE_EXPERIENCES, skills=list(BASE_SKILLS)
    )


def base_markdown() -> str:
    lines = [f"# {NAME}", "", CONTACT, "", "## Summary", BASE_SUMMARY, "", "## Experience", ""]
    for job in BASE_EXPERIENCES:
        lines.append(f"### {job.title} — {job.employer} ({job.dates})")
        lines.extend(f"- {bullet}" for bullet in job.bullets)
        lines.append("")
    lines += ["## Skills", ", ".join(BASE_SKILLS), "", "## Education", EDUCATION, ""]
    return "\n".join(lines)


# --- applications --------------------------------------------------------------------------------

COMPANIES = [
    "Aldermoor Health", "Brindle Freight", "Cobaltine Labs", "Dunmere Pay", "Elmstead Cloud",
    "Fennick Analytics", "Garnetly", "Halcyon Row", "Ironquill Software", "Juniper Fold",
    "Kestrel Wharf", "Larkspur Data", "Marlowe & Finch", "Nettlebrook", "Ostrander Systems",
    "Pellucid Health", "Quillmark", "Ravenhill Logistics", "Saltmarsh Labs", "Tessaly",
    "Umberfield", "Voltmere Energy", "Wrenfield Software", "Xanthe Pay", "Yarrowby",
    "Zephyrine Cloud", "Ashgrove Media", "Blythe Robotics", "Cindermoor", "Driftwood Analytics",
    "Eastlake Insurance", "Foxglove Learning", "Greywater Security", "Hollowell Travel",
    "Inkwell Games", "Jasperline", "Kinfolk Foods", "Loomis Park", "Mistral Ledger",
    "Northgate Mobility",
]  # fmt: skip


@dataclass(frozen=True)
class Family:
    """A kind of job: its titles, the keywords its postings use and what the work is."""

    roles: list[str]
    covered: list[str]  # keywords the base resume has
    missing: list[str]  # keywords it does not
    duties: list[str]


FAMILIES = {
    "backend": Family(
        roles=["Backend Engineer", "Senior Backend Engineer", "Software Engineer, Payments"],
        covered=[
            "python",
            "django",
            "fastapi",
            "postgresql",
            "redis",
            "celery",
            "rest apis",
            "pytest",
        ],
        missing=["kubernetes", "go", "grpc", "kafka", "elasticsearch"],
        duties=[
            "Design and run the services behind our customer-facing product",
            "Keep latency low and errors visible as traffic grows",
            "Review code, write tests and improve how the team ships",
        ],
    ),
    "fullstack": Family(
        roles=["Full-Stack Engineer", "Software Engineer, Product", "Senior Full-Stack Engineer"],
        covered=["react", "typescript", "python", "postgresql", "rest apis", "docker", "ci/cd"],
        missing=["next.js", "graphql", "jest", "tailwind"],
        duties=[
            "Build features end to end, from the database to the screen",
            "Work with design and product to ship small changes often",
            "Own the quality of what you ship, including tests and monitoring",
        ],
    ),
    "data": Family(
        roles=["Data Engineer", "Analytics Engineer", "Senior Data Engineer"],
        covered=["python", "sql", "postgresql", "celery", "docker", "aws"],
        missing=["airflow", "dbt", "snowflake", "spark", "kafka"],
        duties=[
            "Build and maintain the pipelines that feed our reporting",
            "Model data so analysts can answer questions without asking engineers",
            "Monitor data quality and fix what breaks overnight",
        ],
    ),
    "platform": Family(
        roles=["Platform Engineer", "Site Reliability Engineer", "DevOps Engineer"],
        covered=["docker", "aws", "ci/cd", "github actions", "linux", "python"],
        missing=["kubernetes", "terraform", "datadog", "prometheus"],
        duties=[
            "Run the infrastructure that every product team builds on",
            "Automate deployments and make rollbacks boring",
            "Be the person who knows why it is slow, and fix it",
        ],
    ),
}

# --- notes ---------------------------------------------------------------------------------------

NOTES = {
    Stage.SAVED: ["Still deciding whether to apply", "Bookmarked: want to tailor the resume first"],
    Stage.APPLIED: [
        "Followed up with the recruiter by email",
        "A contact there says the team is still reviewing applications",
    ],
    Stage.SCREENING: [
        "Recruiter call went well, waiting to hear back",
        "Sent the salary expectations they asked for",
    ],
    Stage.INTERVIEWING: [
        "Round 1: system design with two engineers",
        "Round 2: pair-programming exercise",
        "Round 3: conversation with the hiring manager",
    ],
    Stage.OFFER: ["Verbal offer received, reviewing the details", "Asked for a few days to decide"],
}
