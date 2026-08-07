"""Schema.

The split between `posts` (raw scrape) and `profiles` (LLM-derived) is
deliberate: extraction can be re-run with a better prompt without re-scraping,
and a bad extraction never destroys the source text.

There is no `people` table — grouping by author is done at query time so it
can't drift out of sync with the posts it summarizes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Fixed vocabularies. Kept as plain tuples (not DB enums) so adding a value
# doesn't need a migration; validation happens in the extractor.
GENDERS = ("M", "F", "NB", "couple", "unknown")
PRECISIONS = ("city", "province", "country", "none")
POST_TYPES = ("profile", "event", "meta")
#: Closed vocabulary — the extractor may only choose from this list, so a tag
#: always means the same thing and filters never miss a synonym.
#:
#: The last five were added after measuring what people actually write about
#: that had no word here: anime 7.7% of posts, nightlife 4.4%, food 2.4%,
#: cars 2.4%, languages 2.2%.
#:
#: Deliberately NOT here, despite being common in the text: loneliness and
#: mental health (9.2%), LGBTQ (3.3%), parenting (4.6%), student (5.1%),
#: expat (4.6%). The first two are special-category data under GDPR Art. 9 —
#: inferring someone's health or sexuality from a public post and storing it
#: as a queryable tag is a different act from noting they like coffee, and
#: these people never signed up for any of it. The last three aren't
#: interests at all but life stages; if they're ever wanted they belong in
#: their own field, not smuggled in here.
INTEREST_VOCAB = (
    "creative", "gaming", "crafts", "sports", "outdoors", "music", "books",
    "coffee", "travel", "photography", "cooking", "tech", "fitness", "art",
    "film", "pets", "hiking", "boardgames",
    "anime", "nightlife", "food", "cars", "languages",
)


class Base(DeclarativeBase):
    pass


profile_interests = Table(
    "profile_interests",
    Base.metadata,
    Column("profile_id", ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("interest_id", ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True),
)


class Place(Base):
    """Gazetteer row. Static reference data, seeded once from ingest/places.py."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # city | province
    province: Mapped[str | None] = mapped_column(String(40))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("name", "kind", name="uq_place_name_kind"),)


class Post(Base):
    """Raw scraped post. Append-only apart from last_seen_at / deleted_at."""

    __tablename__ = "posts"

    reddit_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    subreddit: Mapped[str] = mapped_column(String(60), index=True)
    author: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set when the permalink starts 404ing; the API filters these out rather
    # than hard-deleting, so a transient 404 can be undone.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    profile: Mapped[Profile | None] = relationship(
        back_populates="post", uselist=False, cascade="all, delete-orphan"
    )


class Profile(Base):
    """LLM-extracted structured view of one post."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[str] = mapped_column(
        ForeignKey("posts.reddit_id", ondelete="CASCADE"), unique=True, index=True
    )

    age: Mapped[int | None] = mapped_column(Integer, index=True)
    gender: Mapped[str] = mapped_column(String(10), default="unknown", index=True)

    location_raw: Mapped[str | None] = mapped_column(String(120))
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    geo_precision: Mapped[str] = mapped_column(String(10), default="none", index=True)

    post_type: Mapped[str] = mapped_column(String(10), default="profile", index=True)
    lang: Mapped[str] = mapped_column(String(2), default="en", index=True)
    looking_for: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    post: Mapped[Post] = relationship(back_populates="profile")
    place: Mapped[Place | None] = relationship()
    interests: Mapped[list[Interest]] = relationship(
        secondary=profile_interests, back_populates="profiles", lazy="selectin"
    )


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    profiles: Mapped[list[Profile]] = relationship(
        secondary=profile_interests, back_populates="interests"
    )


class User(Base):
    """A signed-in account.

    Identity comes from Google, so there is no password to store or leak. The
    profile fields are a cache of what Google returned at last sign-in — the
    `google_sub` is the only value that's stable and safe to key on, since
    people change their email address.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    picture: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserPerson(Base):
    """What a signed-in user has marked about a person on the map.

    Keyed by `person_key` (see app/identity.py), not by post id, so the row
    stays attached when someone posts again.

    `saved`, `status` and `note` are independent: noting someone you haven't
    saved is normal, and so is saving someone you haven't contacted.
    """

    __tablename__ = "user_people"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    person_key: Mapped[str] = mapped_column(String(24), primary_key=True)

    saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # null | contacted | hidden. "hidden" is a personal view filter and has no
    # effect on anyone else — it is not a block.
    status: Mapped[str | None] = mapped_column(String(16), index=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserProfile(Base):
    """What a signed-in user says about themselves, for match ranking.

    Freely given by the viewer about the viewer — it does not expand what is
    known about the people on the map, who never signed up for any of this.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    age: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(80))
    province: Mapped[str | None] = mapped_column(String(40))
    # Plain JSON list rather than a join table: it's a short, fixed vocabulary
    # and is only ever read as a whole.
    interests: Mapped[list] = mapped_column(JSON, default=list)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SavedSearch(Base):
    """A filter set the user wants to be told about when someone new matches."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    # The same shape as the query string, so the alert job runs exactly the
    # search the user built rather than a second interpretation of it.
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    cadence: Mapped[str] = mapped_column(String(16), default="weekly")  # daily|weekly|off
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertSent(Base):
    """One row per person already mentioned, so nobody is announced twice."""

    __tablename__ = "alerts_sent"

    saved_search_id: Mapped[int] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )
    person_key: Mapped[str] = mapped_column(String(24), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
