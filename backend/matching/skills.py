"""Skill alias dictionary and detection. Edit SKILL_ALIASES to teach JobPilot new skills.

Detection is deliberately conservative: only listed skills are recognized, and word boundaries
stop "Java" matching inside "JavaScript" or "SQL" inside "PostgreSQL".
"""
import re

SKILL_ALIASES: dict[str, list[str]] = {
    # languages
    "Python": ["python", "python3", "python 3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript"],
    "C#": ["c#", "c sharp", "csharp"],
    "C++": ["c++"],
    "Go": ["golang"],
    "Rust": ["rust"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "Kotlin": ["kotlin"],
    "SQL": ["sql", "t-sql", "pl/sql"],
    # backend frameworks
    "Django": ["django"],
    "Django REST Framework": ["django rest framework", "drf"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "ASP.NET Core": ["asp.net core", "asp.net", "aspnet core", "asp.net mvc"],
    ".NET": [".net", ".net core", "dotnet", "dot net"],
    "Entity Framework": ["entity framework", "ef core"],
    "Spring Boot": ["spring boot", "spring framework"],
    "Laravel": ["laravel"],
    "Ruby on Rails": ["ruby on rails", "rails"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Celery": ["celery"],
    # frontend
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Tailwind CSS": ["tailwind", "tailwind css"],
    # data
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQL Server": ["sql server", "mssql", "ms sql"],
    "SQLite": ["sqlite"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "RabbitMQ": ["rabbitmq"],
    "Kafka": ["kafka"],
    # devops and cloud
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "Google Cloud": ["gcp", "google cloud"],
    "Terraform": ["terraform"],
    "Linux": ["linux"],
    "Git": ["git"],
    "GitHub Actions": ["github actions"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    "Jenkins": ["jenkins"],
    "Nginx": ["nginx"],
    # practices and concepts
    "REST APIs": ["rest api", "rest apis", "restful", "restful api", "restful apis"],
    "GraphQL": ["graphql"],
    "Microservices": ["microservices", "microservice"],
    "OOP": ["oop", "object-oriented", "object oriented"],
    "Unit Testing": ["unit testing", "unit tests", "unit test", "tdd"],
    "Pytest": ["pytest"],
    "Agile": ["agile", "scrum"],
    "OAuth": ["oauth", "oauth2"],
    "JWT": ["jwt"],
}

# Having the first skill is taken as having the others (used for the CANDIDATE side only).
IMPLIES: dict[str, set[str]] = {
    "Django": {"Python"}, "Django REST Framework": {"Django", "Python", "REST APIs"}, "Flask": {"Python"},
    "FastAPI": {"Python"}, "Celery": {"Python"}, "Pytest": {"Python", "Unit Testing"},
    "ASP.NET Core": {".NET", "C#"}, "Entity Framework": {".NET", "C#"},
    "TypeScript": {"JavaScript"}, "Node.js": {"JavaScript"}, "React": {"JavaScript"},
    "Next.js": {"React", "JavaScript"}, "Vue.js": {"JavaScript"}, "Angular": {"TypeScript", "JavaScript"},
    "Spring Boot": {"Java"}, "Laravel": {"PHP"}, "Ruby on Rails": {"Ruby"},
    "PostgreSQL": {"SQL"}, "MySQL": {"SQL"}, "SQL Server": {"SQL"}, "SQLite": {"SQL"},
    "GitHub Actions": {"CI/CD", "Git"},
}

_BEFORE = r"(?<![A-Za-z0-9+#.])"
_AFTER = r"(?![A-Za-z0-9+#])"


def _pattern(alias: str) -> re.Pattern:
    body = re.escape(alias).replace(r"\ ", r"[\s-]+")
    return re.compile(_BEFORE + body + _AFTER, re.IGNORECASE)


_PATTERNS = [(canonical, [_pattern(a) for a in aliases]) for canonical, aliases in SKILL_ALIASES.items()]
_ALIAS_LOOKUP = {a.lower(): canonical for canonical, aliases in SKILL_ALIASES.items() for a in aliases}
_ALIAS_LOOKUP.update({c.lower(): c for c in SKILL_ALIASES})


def find_skills(text: str) -> list[str]:
    """Canonical skills mentioned in the text, in order of first appearance."""
    found: list[tuple[int, str]] = []
    for canonical, patterns in _PATTERNS:
        positions = [m.start() for p in patterns for m in [p.search(text)] if m]
        if positions:
            found.append((min(positions), canonical))
    return [canonical for _, canonical in sorted(found)]


def canonical_skill(name: str) -> str | None:
    return _ALIAS_LOOKUP.get(" ".join(name.lower().split()))


def expand_with_implied(skills: set[str]) -> set[str]:
    expanded = set(skills)
    changed = True
    while changed:
        changed = False
        for skill in list(expanded):
            for implied in IMPLIES.get(skill, ()):
                if implied not in expanded:
                    expanded.add(implied)
                    changed = True
    return expanded