from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import ViewerRole, World, WorldRule
from worldbuilder_core.schemas import WorldRuleCreate, WorldRuleRead, WorldRuleUpdate

router = APIRouter(tags=["world rules"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_visible(rule: WorldRule | None, role: ViewerRole) -> WorldRule:
    if rule is None or (role == ViewerRole.player and rule.is_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World rule not found")
    return rule


@router.post("/worlds/{world_id}/world-rules", response_model=WorldRuleRead, status_code=status.HTTP_201_CREATED)
def create_world_rule(world_id: str, payload: WorldRuleCreate, session: DbSession) -> WorldRule:
    ensure_world(session, world_id)
    rule = WorldRule(world_id=world_id, **payload.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.get("/worlds/{world_id}/world-rules", response_model=list[WorldRuleRead])
def list_world_rules(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    active_only: bool = True,
    tag: str | None = Query(default=None),
) -> list[WorldRule]:
    ensure_world(session, world_id)
    stmt: Select[tuple[WorldRule]] = select(WorldRule).where(WorldRule.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(WorldRule.is_secret.is_(False))
    if active_only:
        stmt = stmt.where(WorldRule.is_active.is_(True))

    rules = list(session.scalars(stmt.order_by(WorldRule.priority.desc(), WorldRule.created_at.asc())))
    if tag:
        rules = [rule for rule in rules if tag in rule.tags]
    return rules


@router.get("/world-rules/{rule_id}", response_model=WorldRuleRead)
def get_world_rule(rule_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> WorldRule:
    return ensure_visible(session.get(WorldRule, rule_id), role)


@router.patch("/world-rules/{rule_id}", response_model=WorldRuleRead)
def update_world_rule(rule_id: str, payload: WorldRuleUpdate, session: DbSession) -> WorldRule:
    rule = session.get(WorldRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World rule not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)

    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/world-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_rule(rule_id: str, session: DbSession) -> None:
    rule = session.get(WorldRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World rule not found")
    session.delete(rule)
    session.commit()

