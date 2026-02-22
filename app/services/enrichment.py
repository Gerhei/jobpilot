import re

from app.services.skills_map import SKILLS_MAP, normalize_skill

GRADE_RE = re.compile(
    r"\b(junior|джуниор|intern|интерн|middle|мидл|mid|"
    r"senior|сениор|lead|лид|principal)\b",
    re.IGNORECASE,
)
_GRADE_MAP = {
    "junior": "junior",
    "джуниор": "junior",
    "intern": "junior",
    "интерн": "junior",
    "middle": "middle",
    "мидл": "middle",
    "mid": "middle",
    "senior": "senior",
    "сениор": "senior",
    "lead": "lead",
    "лид": "lead",
    "principal": "lead",
}

WORK_FORMAT_RE = re.compile(
    r"\b(удалён\w*|remote|офис\w*|office|гибрид\w*|hybrid)\b",
    re.IGNORECASE,
)


def extract_skills(key_skills: list[dict], description: str | None) -> set[str]:
    """Извлекает навыки. Приоритет: key_skills → regex по description."""
    if key_skills:
        raw = [s["name"] for s in key_skills]
    else:
        raw = [
            key
            for key in SKILLS_MAP
            if re.search(rf"\b{re.escape(key)}\b", description or "", re.IGNORECASE)
        ]
    return {normalize_skill(s) for s in raw}


def calc_relevance_score(skills: set[str], reference: set[str]) -> float | None:
    """NULL если навыки не найдены, иначе доля пересечения с reference."""
    if not skills:
        return None  # нет данных, не 0.0
    if not reference:
        return 0.0
    return len(skills & reference) / len(reference)


def extract_grade(text: str | None) -> str | None:
    m = GRADE_RE.search(text or "")
    return _GRADE_MAP.get(m.group(1).lower()) if m else None


def extract_work_format(text: str | None) -> str | None:
    m = WORK_FORMAT_RE.search(text or "")
    if not m:
        return None
    w = m.group(1).lower()
    if re.match(r"(удал|remote)", w):
        return "remote"
    if re.match(r"(офис|office)", w):
        return "office"
    return "hybrid"
