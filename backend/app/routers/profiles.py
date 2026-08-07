from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import query as q
from app import ranking
from app.auth import current_user
from app.db import get_session
from app.models import Profile, User, UserProfile
from app.schemas import PersonOut, ProfileListOut
from app.search import SearchParams
from app.search import run as run_search

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("", response_model=ProfileListOut)
def list_profiles(
    session: Session = Depends(get_session),
    period: int | None = Query(30, description="Days back; omit or 0 for all time"),
    age_min: int = Query(18, ge=0, le=120),
    age_max: int = Query(70, ge=0, le=120),
    genders: str | None = Query(None, description="Comma list: M,F,NB,couple,unknown"),
    interests: str | None = Query(None, description="Comma list of interest slugs"),
    interest_mode: str = Query("any", pattern="^(any|all)$"),
    langs: str | None = Query(None, description="Comma list: nl,en"),
    provinces: str | None = Query(None, description="Comma list of province names"),
    sources: str | None = Query(None, description="Comma list of subreddits, no 'r/'"),
    search: str | None = None,
    state: str | None = Query(
        None, description="saved | contacted | hidden | none. Signed in only."
    ),
    sort: str = Query("newest", pattern="^(newest|match)$"),
    include_hidden: bool = False,
    include_events: bool = False,
    user: User | None = Depends(current_user),
) -> ProfileListOut:
    params = SearchParams(
        period=period,
        age_min=age_min,
        age_max=age_max,
        genders=genders,
        interests=interests,
        interest_mode=interest_mode,
        langs=langs,
        provinces=provinces,
        sources=sources,
        search=search,
        state=state,
        include_hidden=include_hidden,
        include_events=include_events,
        sort=sort,
    )
    people = run_search(session, params, user_id=user.id if user else None)

    # Ranking is a sort and never a filter — the count is identical either way.
    if sort == "match" and user is not None:
        profile = session.get(UserProfile, user.id)
        if profile is not None:
            people = ranking.sort_people(profile, people)

    # Everyone now carries map coordinates, so nothing is left in the tray.
    placed = sum(1 for p in people if p.x is not None)

    return ProfileListOut(
        total=len(people),
        placed=placed,
        unplaced=len(people) - placed,
        people=people,
    )


@router.get("/{post_id}", response_model=PersonOut)
def get_profile(post_id: str, session: Session = Depends(get_session)) -> PersonOut:
    profile = session.scalars(
        q.base_query().where(Profile.post_id == post_id)
    ).unique().one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Not found")
    return q.to_person(profile, q.now_utc(), q.repeat_counts(session))
