from app.services.enrichment import (
    calc_relevance_score,
    extract_grade,
    extract_skills,
    extract_work_format,
)


def test_extract_skills_from_key_skills():
    ks = [{"name": "Python"}, {"name": "FastAPI"}]
    result = extract_skills(ks, "")
    assert "python" in result and "fastapi" in result


def test_extract_skills_fallback_to_description():
    result = extract_skills([], "Ищем senior python developer с опытом postgres")
    assert "python" in result or "postgresql" in result


def test_extract_skills_empty_returns_empty_set():
    assert extract_skills([], "") == set()


def test_calc_score_normal():
    score = calc_relevance_score({"python", "fastapi"}, {"python", "fastapi", "redis"})
    assert abs(score - 2 / 3) < 1e-6


def test_calc_score_null_if_no_skills():
    assert calc_relevance_score(set(), {"python"}) is None


def test_calc_score_zero_if_no_match():
    score = calc_relevance_score({"java"}, {"python", "fastapi"})
    assert score == 0.0


def test_extract_grade_senior():
    assert extract_grade("Senior Python Developer") == "senior"


def test_extract_grade_junior_variants():
    assert extract_grade("Стажёр / Junior разработчик") == "junior"


def test_extract_grade_none():
    assert extract_grade("Python Developer") is None


def test_extract_work_format_remote():
    assert extract_work_format("Удалённая работа, любой город") == "remote"


def test_extract_work_format_office():
    assert extract_work_format("Работа в офисе Москва") == "office"


def test_extract_work_format_none():
    assert extract_work_format("Python Developer") is None
