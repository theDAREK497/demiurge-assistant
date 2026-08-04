import re
from math import sqrt

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from worldbuilder_core.models import (
    DocumentChunkLink,
    Entity,
    KnowledgeChunk,
    KnowledgeDocument,
    RandomTable,
    RandomTableRow,
    Relationship,
    ViewerRole,
    World,
    WorldRule,
)
from worldbuilder_core.schemas import (
    EntityRead,
    KnowledgeChunkExcerpt,
    RandomTableRead,
    RandomTableRowRead,
    RelationshipRead,
    WorldContextRead,
    WorldRead,
    WorldRuleRead,
)


class RetrievalError(Exception):
    """Base error for retrieval operations."""


class RetrievalWorldNotFoundError(RetrievalError):
    pass


MAX_CONTEXT_CHARS = 32_000


def build_world_context(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole = ViewerRole.master,
    query: str | None = None,
    max_entities: int = 12,
    max_rules: int = 8,
    max_relationships: int = 24,
    max_random_tables: int = 12,
    max_document_chunks: int = 8,
    query_embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> WorldContextRead:
    world = session.get(World, world_id)
    if world is None:
        raise RetrievalWorldNotFoundError(f"World {world_id!r} not found")

    rules = _select_rules(session, world_id, role=role, max_rules=max_rules)
    entities = _select_entities(session, world_id, role=role, query=query, max_entities=max_entities)
    relationships = _select_relationships(
        session,
        world_id,
        role=role,
        entity_ids=[entity.id for entity in entities],
        max_relationships=max_relationships,
    )
    random_tables = _select_random_tables(session, world_id, role=role, max_random_tables=max_random_tables)
    random_table_reads = [_random_table_read(table, role=role) for table in random_tables]
    document_chunks = _select_document_chunks(
        session,
        world_id,
        role=role,
        query=query,
        query_embedding=query_embedding,
        embedding_model=embedding_model,
        max_chunks=max_document_chunks,
    )

    return WorldContextRead(
        world=WorldRead.model_validate(world),
        role=role,
        query=query,
        entities=[EntityRead.model_validate(entity) for entity in entities],
        relationships=[RelationshipRead.model_validate(relationship) for relationship in relationships],
        world_rules=[WorldRuleRead.model_validate(rule) for rule in rules],
        random_tables=random_table_reads,
        document_chunks=document_chunks,
        context_text=render_context_text(
            world,
            rules=rules,
            entities=entities,
            relationships=relationships,
            random_tables=random_table_reads,
            document_chunks=document_chunks,
        ),
    )


async def build_world_context_with_embeddings(
    session: Session,
    world_id: str,
    **kwargs,
) -> WorldContextRead:
    query = kwargs.get("query")
    if query:
        from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
        from worldbuilder_core.services.llm_settings import get_llm_runtime_settings

        runtime = get_llm_runtime_settings(session)
        if runtime.embedding_model:
            try:
                client = build_llm_client(runtime, default_model=runtime.embedding_model)
                _, vectors = await client.embeddings([query], model=runtime.embedding_model)
                kwargs["query_embedding"] = vectors[0]
                kwargs["embedding_model"] = runtime.embedding_model
            except LLMProviderError:
                pass
    return build_world_context(session, world_id, **kwargs)


def _select_rules(session: Session, world_id: str, *, role: ViewerRole, max_rules: int) -> list[WorldRule]:
    stmt: Select[tuple[WorldRule]] = (
        select(WorldRule)
        .where(WorldRule.world_id == world_id, WorldRule.is_active.is_(True))
        .order_by(WorldRule.priority.desc(), WorldRule.created_at.asc())
        .limit(max_rules)
    )
    if role == ViewerRole.player:
        stmt = stmt.where(WorldRule.is_secret.is_(False))
    return list(session.scalars(stmt))


def _select_entities(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    query: str | None,
    max_entities: int,
) -> list[Entity]:
    stmt: Select[tuple[Entity]] = select(Entity).where(Entity.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(Entity.is_secret.is_(False))
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(Entity.name.ilike(pattern), Entity.summary.ilike(pattern), Entity.description.ilike(pattern)))
    stmt = stmt.order_by(Entity.updated_at.desc(), Entity.name.asc()).limit(max_entities)
    return list(session.scalars(stmt))


def _select_relationships(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    entity_ids: list[str],
    max_relationships: int,
) -> list[Relationship]:
    if not entity_ids:
        return []

    stmt: Select[tuple[Relationship]] = (
        select(Relationship)
        .options(joinedload(Relationship.source_entity), joinedload(Relationship.target_entity))
        .where(
            Relationship.world_id == world_id,
            (Relationship.source_entity_id.in_(entity_ids)) | (Relationship.target_entity_id.in_(entity_ids)),
        )
        .order_by(Relationship.updated_at.desc(), Relationship.created_at.desc())
        .limit(max_relationships)
    )
    if role == ViewerRole.player:
        stmt = stmt.where(Relationship.is_secret.is_(False))

    relationships = list(session.scalars(stmt))
    if role == ViewerRole.player:
        relationships = [
            relationship
            for relationship in relationships
            if not relationship.source_entity.is_secret and not relationship.target_entity.is_secret
        ]
    return relationships


def _select_random_tables(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    max_random_tables: int,
) -> list[RandomTable]:
    stmt: Select[tuple[RandomTable]] = (
        select(RandomTable)
        .options(selectinload(RandomTable.rows))
        .where(RandomTable.world_id == world_id)
        .order_by(RandomTable.updated_at.desc(), RandomTable.name.asc())
        .limit(max_random_tables)
    )
    if role == ViewerRole.player:
        stmt = stmt.where(RandomTable.is_secret.is_(False))
    return list(session.scalars(stmt))


def _select_document_chunks(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    query: str | None,
    max_chunks: int = 8,
    query_embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> list[KnowledgeChunkExcerpt]:
    if max_chunks <= 0:
        return []
    terms = _search_terms(query)
    if not terms:
        return []
    lexical_filter = or_(*(KnowledgeChunk.content.ilike(f"%{term}%") for term in terms))
    vector_search = bool(query_embedding and embedding_model)
    match_filter = (
        or_(lexical_filter, KnowledgeChunk.embedding_model == embedding_model)
        if vector_search
        else lexical_filter
    )
    stmt = (
        select(KnowledgeChunk, DocumentChunkLink, KnowledgeDocument)
        .join(DocumentChunkLink, DocumentChunkLink.chunk_id == KnowledgeChunk.id)
        .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunkLink.document_id)
        .where(
            KnowledgeChunk.world_id == world_id,
            KnowledgeDocument.status == "ready",
            match_filter,
        )
    )
    is_postgresql_vector = (
        vector_search
        and session.bind is not None
        and session.bind.dialect.name == "postgresql"
    )
    if is_postgresql_vector:
        stmt = stmt.where(
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == embedding_model,
        ).order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding)).limit(80)
    else:
        stmt = stmt.order_by(
            KnowledgeDocument.updated_at.desc(),
            DocumentChunkLink.position.asc(),
        ).limit(5_000 if vector_search else 80)
    if role == ViewerRole.player:
        stmt = stmt.where(KnowledgeDocument.is_secret.is_(False))
    rows = session.execute(stmt).all()
    def score(row) -> float:
        chunk = row[0]
        lexical = float(sum(chunk.content.casefold().count(term) for term in terms))
        semantic = _cosine_similarity(query_embedding, chunk.embedding) if vector_search else 0.0
        return lexical + max(semantic, 0.0) * 5.0

    ranked = sorted(rows, key=lambda row: (-score(row), row[2].filename.casefold(), row[1].position))
    result: list[KnowledgeChunkExcerpt] = []
    seen_chunks: set[str] = set()
    for chunk, link, document in ranked:
        if chunk.id in seen_chunks:
            continue
        seen_chunks.add(chunk.id)
        result.append(
            KnowledgeChunkExcerpt(
                chunk_id=chunk.id,
                document_id=document.id,
                filename=document.filename,
                position=link.position,
                heading=link.heading,
                content=chunk.content,
            )
        )
        if len(result) >= max_chunks:
            break
    return result


def _cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _search_terms(query: str | None) -> list[str]:
    if not query:
        return []
    ignored = {"это", "как", "что", "для", "the", "and", "with", "from", "про", "или"}
    terms = []
    for term in re.findall(r"[\w-]{3,}", query.casefold()):
        if term not in ignored and term not in terms:
            terms.append(term)
    return terms[:8]


def _random_table_read(table: RandomTable, *, role: ViewerRole) -> RandomTableRead:
    payload = RandomTableRead.model_validate(table)
    payload.rows = [RandomTableRowRead.model_validate(row) for row in _visible_rows(table, role)]
    return payload


def _visible_rows(table: RandomTable, role: ViewerRole) -> list[RandomTableRow]:
    rows = sorted(table.rows, key=lambda row: (row.created_at, row.id))
    if role == ViewerRole.player:
        return [row for row in rows if not row.is_secret]
    return rows


def render_context_text(
    world: World,
    *,
    rules: list[WorldRule],
    entities: list[Entity],
    relationships: list[Relationship],
    random_tables: list[RandomTableRead],
    document_chunks: list[KnowledgeChunkExcerpt],
) -> str:
    lines = [f"World: {world.name}"]
    if world.description:
        lines.append(f"Description: {_compact_context_value(world.description, 1_000)}")

    if rules:
        lines.append("")
        lines.append("World rules:")
        for rule in rules:
            condition = _compact_context_value(rule.condition, 700)
            effect = _compact_context_value(rule.effect, 700)
            lines.append(f"- P{rule.priority}: if {condition} then {effect}")

    if entities:
        lines.append("")
        lines.append("Relevant entities:")
        for entity in entities:
            detail = entity.summary or entity.description or "No summary."
            lines.append(
                f"- {entity.type}: {entity.name} [{entity.id}] - "
                f"{_compact_context_value(detail, 1_000)}"
            )

    if relationships:
        lines.append("")
        lines.append("Relevant relationships:")
        for relationship in relationships:
            source = relationship.source_entity.name
            target = relationship.target_entity.name
            label = relationship.label or relationship.type
            lines.append(f"- {source} --{label}--> {target}")

    if random_tables:
        lines.append("")
        lines.append("Random tables:")
        for table in random_tables:
            detail = table.description or "No description."
            lines.append(f"- {table.name} [{table.id}] - {_compact_context_value(detail, 700)}")
            for row in table.rows[:8]:
                label = f"{row.label}: " if row.label else ""
                secret = " (secret)" if row.is_secret else ""
                result = _compact_context_value(row.result, 500)
                lines.append(f"  - {label}{result} [weight {row.weight}]{secret}")

    if document_chunks:
        lines.append("")
        lines.append("Relevant source excerpts:")
        for excerpt in document_chunks:
            heading = f" / {excerpt.heading}" if excerpt.heading else ""
            lines.append(f"- {excerpt.filename} #{excerpt.position + 1}{heading}:")
            lines.append(_compact_context_value(excerpt.content, 4_000))

    return _truncate_context("\n".join(lines), MAX_CONTEXT_CHARS)


def _compact_context_value(value: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _truncate_context(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    marker = "\n\n[Context truncated to fit the model budget.]"
    return f"{value[: limit - len(marker)].rstrip()}{marker}"
