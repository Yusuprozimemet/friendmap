"""Per-user state: saved people, contact status, private notes.

Everything here is about the *viewer*, never about the people on the map —
they never signed up, and nothing a viewer records is visible to anyone else.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.auth import require_user
from app.db import get_session
from app.models import (
    INTEREST_VOCAB,
    AlertSent,
    SavedSearch,
    User,
    UserPerson,
    UserProfile,
)
from app.schemas import (
    PersonStateIn,
    PersonStateOut,
    SavedSearchIn,
    SavedSearchOut,
    SavedSearchPatch,
    UserProfileIn,
    UserProfileOut,
)
from app.search import SearchParams
from app.search import run as run_search

router = APIRouter(prefix="/api/me", tags=["me"])

STATUSES = {"contacted", "hidden"}
CADENCES = {"daily", "weekly", "off"}


def _out(row: UserPerson) -> PersonStateOut:
    return PersonStateOut(
        person_key=row.person_key,
        saved=row.saved,
        status=row.status,
        note=row.note,
        updated_at=row.updated_at,
    )


@router.get("/people", response_model=list[PersonStateOut])
def list_people(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[PersonStateOut]:
    """State only — the profiles themselves come from /api/profiles."""
    rows = session.scalars(
        select(UserPerson).where(UserPerson.user_id == user.id)
    ).all()
    return [_out(r) for r in rows]


@router.put("/people/{person_key}", response_model=PersonStateOut)
def set_person_state(
    payload: PersonStateIn,
    person_key: str = Path(min_length=8, max_length=24, pattern="^[0-9a-f]+$"),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> PersonStateOut:
    """Partial upsert: fields left unset keep their current value."""
    if payload.status is not None and payload.status not in STATUSES:
        raise HTTPException(422, f"status must be one of {sorted(STATUSES)} or null")

    now = datetime.now(timezone.utc)
    row = session.get(UserPerson, (user.id, person_key))
    if row is None:
        row = UserPerson(
            user_id=user.id, person_key=person_key, created_at=now, updated_at=now
        )
        session.add(row)

    if payload.saved is not None:
        row.saved = payload.saved
    # status is nullable and clearing it is meaningful, so it needs an
    # explicit sentinel rather than "None means untouched".
    if payload.set_status:
        row.status = payload.status
    if payload.note is not None:
        row.note = payload.note.strip()[:2000]
    row.updated_at = now

    session.commit()
    return _out(row)


@router.delete("/people/{person_key}")
def clear_person_state(
    person_key: str = Path(min_length=8, max_length=24, pattern="^[0-9a-f]+$"),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(UserPerson, (user.id, person_key))
    if row is not None:
        session.delete(row)
        session.commit()
    return {"cleared": True}


# --- self-description, used only for match ranking -----------------------


@router.get("/profile", response_model=UserProfileOut)
def get_my_profile(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserProfileOut:
    row = session.get(UserProfile, user.id)
    if row is None:
        return UserProfileOut(
            age=None, city=None, province=None, interests=[], age_min=None, age_max=None
        )
    return UserProfileOut(
        age=row.age,
        city=row.city,
        province=row.province,
        interests=list(row.interests or []),
        age_min=row.age_min,
        age_max=row.age_max,
    )


@router.put("/profile", response_model=UserProfileOut)
def put_my_profile(
    payload: UserProfileIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserProfileOut:
    if payload.age is not None and not 13 <= payload.age <= 120:
        raise HTTPException(422, "age must be between 13 and 120")
    lo, hi = payload.age_min, payload.age_max
    if lo is not None and hi is not None and lo > hi:
        raise HTTPException(422, "age_min cannot be above age_max")

    # Only vocabulary interests, so a typo can never match nobody forever.
    interests = sorted({i for i in payload.interests if i in INTEREST_VOCAB})

    now = datetime.now(timezone.utc)
    row = session.get(UserProfile, user.id)
    if row is None:
        row = UserProfile(user_id=user.id, updated_at=now)
        session.add(row)
    row.age = payload.age
    row.city = (payload.city or "").strip() or None
    row.province = (payload.province or "").strip() or None
    row.interests = interests
    row.age_min = lo
    row.age_max = hi
    row.updated_at = now
    session.commit()

    return UserProfileOut(
        age=row.age, city=row.city, province=row.province,
        interests=interests, age_min=row.age_min, age_max=row.age_max,
    )


# --- saved searches ------------------------------------------------------


def _search_out(row: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        id=row.id,
        name=row.name,
        filters=row.filters or {},
        cadence=row.cadence,
        last_run_at=row.last_run_at,
        last_match_at=row.last_match_at,
    )


@router.get("/searches", response_model=list[SavedSearchOut])
def list_searches(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[SavedSearchOut]:
    rows = session.scalars(
        select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.id)
    ).all()
    return [_search_out(r) for r in rows]


@router.post("/searches", response_model=SavedSearchOut)
def create_search(
    payload: SavedSearchIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SavedSearchOut:
    count = session.scalar(
        select(func.count(SavedSearch.id)).where(SavedSearch.user_id == user.id)
    )
    if count >= config.MAX_SAVED_SEARCHES:
        raise HTTPException(
            409,
            f"You can keep {config.MAX_SAVED_SEARCHES} saved searches — "
            "delete one to add another.",
        )
    if payload.cadence not in CADENCES:
        raise HTTPException(422, f"cadence must be one of {sorted(CADENCES)}")

    name = payload.name.strip()[:80] or "Saved search"
    # Store only keys the search engine understands, so a hand-crafted body
    # can't smuggle anything into the nightly job.
    filters = SearchParams.from_dict(payload.filters).to_dict()

    now = datetime.now(timezone.utc)
    row = SavedSearch(
        user_id=user.id, name=name, filters=filters,
        cadence=payload.cadence, created_at=now,
    )
    session.add(row)
    session.flush()  # need the id before baselining

    # Baseline: everyone who matches *right now* counts as already seen. The
    # button promises "new matches", and the people already on the board are
    # visible on the screen the user just saved the search from — mailing all
    # 500-odd of them back would be a dump of the back catalogue, not an alert.
    params = SearchParams.from_dict(filters)
    params.state = None
    params.include_hidden = False
    for person in run_search(session, params, user_id=user.id):
        if person.person_key:
            session.add(
                AlertSent(
                    saved_search_id=row.id,
                    person_key=person.person_key,
                    sent_at=now,
                )
            )

    session.commit()
    return _search_out(row)


@router.patch("/searches/{search_id}", response_model=SavedSearchOut)
def update_search(
    search_id: int,
    payload: SavedSearchPatch,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SavedSearchOut:
    row = session.get(SavedSearch, search_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "No such saved search")
    if payload.cadence is not None:
        if payload.cadence not in CADENCES:
            raise HTTPException(422, f"cadence must be one of {sorted(CADENCES)}")
        row.cadence = payload.cadence
    if payload.name is not None:
        row.name = payload.name.strip()[:80] or row.name
    session.commit()
    return _search_out(row)


@router.delete("/searches/{search_id}")
def delete_search(
    search_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(SavedSearch, search_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "No such saved search")
    session.delete(row)
    session.commit()
    return {"deleted": True}


@router.get("/export")
def export_my_data(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    """Everything this account holds, as JSON. GDPR Art. 20 (portability).

    Deliberately the raw rows rather than a rendered view: the point is that
    the data leaves in a form another tool can read, not that it looks nice.

    Note what is *not* here — the people on the map. Their entries are not this
    user's personal data, and a saved list is exported as the opaque
    `person_key` plus whatever note the user wrote themselves. Exporting other
    people's profiles because someone bookmarked them would turn a portability
    request into a data dump about third parties.
    """
    people = session.scalars(
        select(UserPerson).where(UserPerson.user_id == user.id)
    ).all()
    searches = session.scalars(
        select(SavedSearch).where(SavedSearch.user_id == user.id)
    ).all()
    profile = session.get(UserProfile, user.id)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": (
                user.last_login_at.isoformat() if user.last_login_at else None
            ),
        },
        "my_profile": (
            None if profile is None else {
                "age": profile.age,
                "city": profile.city,
                "province": profile.province,
                "interests": profile.interests,
                "age_min": profile.age_min,
                "age_max": profile.age_max,
                "updated_at": profile.updated_at.isoformat(),
            }
        ),
        "saved_people": [
            {
                "person_key": p.person_key,
                "saved": p.saved,
                "status": p.status,
                "note": p.note,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in people
        ],
        "saved_searches": [
            {
                "name": s.name,
                "filters": s.filters,
                "cadence": s.cadence,
                "created_at": s.created_at.isoformat(),
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            }
            for s in searches
        ],
    }
