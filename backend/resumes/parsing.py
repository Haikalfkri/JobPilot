"""Deterministic fact extraction from resume text.

This is a baseline, not semantic understanding: every result is only a *suggestion*
that the user must confirm. An LLM can be layered on later without changing the data model.
"""
import re

from .models import FactCategory

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>()|]+|(?:linkedin\.com|github\.com)/[^\s<>()|]+", re.IGNORECASE
)
PHONE_RE = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{7,}\d(?![\w/])")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z.'\- ]{1,60}$")
BULLET_RE = re.compile(r"^[\-*\u2022\u25cf\u25aa\u25e6\u2013\u00b7]+\s*")
SKILL_SPLIT_RE = re.compile(r"[,;|\u2022\u00b7]")

SECTION_ALIASES = {
    FactCategory.SUMMARY: ["summary", "professional summary", "profile", "about", "about me",
                           "objective", "career objective"],
    FactCategory.EXPERIENCE: ["experience", "work experience", "professional experience",
                              "employment", "employment history", "work history"],
    FactCategory.EDUCATION: ["education", "academic background", "education and training"],
    FactCategory.SKILL: ["skills", "technical skills", "core skills", "key skills",
                         "skills and tools", "tech stack", "technologies"],
    FactCategory.PROJECT: ["projects", "personal projects", "selected projects", "side projects"],
    FactCategory.CERTIFICATION: ["certifications", "certificates", "licenses and certifications",
                                 "courses"],
    FactCategory.LANGUAGE: ["languages"],
}
HEADING_LOOKUP = {alias: cat for cat, aliases in SECTION_ALIASES.items() for alias in aliases}


def _heading_category(line: str):
    key = re.sub(r"\s+", " ", line.lower().replace("&", "and")).strip(" :-_")
    return HEADING_LOOKUP.get(key)


def _looks_like_phone(candidate: str) -> bool:
    groups = re.findall(r"\d+", candidate)
    if not 9 <= sum(len(g) for g in groups) <= 15:
        return False
    # "2018 - 2022 - 2024" is a run of years, not a phone number.
    return not all(len(g) == 4 and g[:2] in ("19", "20") for g in groups)


def _clean_bullet(line: str) -> str:
    return BULLET_RE.sub("", line).strip()


def _fact(category, content, *, key=None, structured=None, location=""):
    return {
        "category": category,
        "fact_key": key,
        "content": content,
        "structured_value": structured,
        "source_location": location,
    }


def parse_facts(text: str) -> list[dict]:
    lines = [(n, raw.strip()) for n, raw in enumerate(text.splitlines(), start=1)]
    lines = [(n, ln) for n, ln in lines if ln]
    facts = _contact_facts(lines)
    for category, items in _split_sections(lines):
        facts.extend(_section_facts(category, items))
    for position, fact in enumerate(facts):
        fact["position"] = position
    return facts


def _contact_facts(lines) -> list[dict]:
    facts = []
    header = lines[:15]

    for n, line in lines[:3]:
        if _heading_category(line):
            break
        words = line.split()
        if NAME_RE.match(line) and 2 <= len(words) <= 4:
            facts.append(_fact(FactCategory.PERSONAL, line, key="full_name", location=f"line {n}"))
            break

    for n, line in lines:
        match = EMAIL_RE.search(line)
        if match:
            facts.append(_fact(FactCategory.PERSONAL, match.group(), key="email", location=f"line {n}"))
            break

    phone_found = False
    for n, line in header:
        cleaned = EMAIL_RE.sub(" ", URL_RE.sub(" ", line))
        for match in PHONE_RE.finditer(cleaned):
            if _looks_like_phone(match.group()):
                facts.append(_fact(FactCategory.PERSONAL, match.group().strip(), key="phone",
                                   location=f"line {n}"))
                phone_found = True
                break
        if phone_found:
            break

    seen = set()
    for n, line in lines:
        for match in URL_RE.finditer(EMAIL_RE.sub(" ", line)):
            url = match.group().rstrip(".,;)")
            if url.lower() in seen:
                continue
            seen.add(url.lower())
            kind = "linkedin" if "linkedin.com" in url.lower() else (
                "github" if "github.com" in url.lower() else "website")
            facts.append(_fact(FactCategory.LINK, url, key=kind, location=f"line {n}"))
    return facts


def _split_sections(lines):
    sections, current = [], None
    for n, line in lines:
        category = _heading_category(line)
        if category:
            current = (category, [])
            sections.append(current)
        elif current is not None:
            current[1].append((n, line))
    return sections


def _section_facts(category, items) -> list[dict]:
    if not items:
        return []
    heading = category.label.lower()
    if category == FactCategory.SUMMARY:
        content = " ".join(_clean_bullet(line) for _, line in items)
        return [_fact(category, content, location=f"{heading} section, line {items[0][0]}")]
    if category == FactCategory.SKILL:
        return _skill_facts(items)
    facts = []
    for n, line in items:
        content = _clean_bullet(line)
        if len(content) >= 3:
            facts.append(_fact(category, content, location=f"{heading} section, line {n}"))
    return facts


def _skill_facts(items) -> list[dict]:
    facts, seen = [], set()
    for n, line in items:
        text = _clean_bullet(line)
        group = None
        if ":" in text:
            prefix, _, rest = text.partition(":")
            if len(prefix) <= 30 and rest.strip():
                group, text = prefix.strip(), rest
        for token in SKILL_SPLIT_RE.split(text):
            name = token.strip(" .")
            if not (1 <= len(name) <= 60) or name.lower() in seen:
                continue
            seen.add(name.lower())
            facts.append(_fact(FactCategory.SKILL, name, key="skill",
                               structured={"name": name, "category": group},
                               location=f"skills section, line {n}"))
    return facts