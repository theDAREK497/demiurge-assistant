from worldbuilder_core.models import Entity
from worldbuilder_core.services.retrieval import _entity_query_score, _entity_type_query_bonus, _query_terms


def test_query_terms_remove_question_filler_and_keep_names() -> None:
    assert _query_terms("Кто такой Виктор Тимофеев?") == ["виктор", "тимофеев"]


def test_entity_query_score_prefers_full_name_over_partial_mentions() -> None:
    terms = _query_terms("Кто такой Виктор Тимофеев?")
    subject = Entity(
        world_id="world-1",
        type="character",
        name="Научный руководитель",
        description="Виктор Тимофеев руководил проектом Семя.",
    )
    relative = Entity(
        world_id="world-1",
        type="character",
        name="Александр",
        summary="Сын Виктора.",
    )

    assert _entity_query_score(subject, terms) > _entity_query_score(relative, terms)


def test_entity_type_query_bonus_understands_who_questions() -> None:
    character = Entity(world_id="world-1", type="character", name="Виктор")
    location = Entity(world_id="world-1", type="location", name="Лаборатория")

    assert _entity_type_query_bonus(character, "Кто такой Виктор?") == 100
    assert _entity_type_query_bonus(location, "Кто такой Виктор?") == 0
