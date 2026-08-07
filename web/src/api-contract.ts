/**
 * Compile-time proof that the hand-written response types still match the API.
 *
 * `types.ts` mirrors the server's Pydantic models by hand, which is nice to read
 * but nothing checked that the two agreed. Rename a field in `schemas.py` and
 * TypeScript kept compiling against the old name — the one place a change could
 * pass both CI jobs and still break the app at runtime.
 *
 * `api-types.ts` is generated from the committed `api-schema.json`, which is in
 * turn generated from the FastAPI app. The assertions below fail the typecheck
 * if the property *names* drift apart.
 *
 * Names, not value types, on purpose. The client deliberately narrows some
 * fields the schema leaves wide — `gender` is `string` in OpenAPI but a union
 * here, because the server constrains it to a closed vocabulary that OpenAPI
 * does not express. Asserting full structural equality would flag those
 * narrowings as errors and the file would end up disabled. Names catch the
 * failure that actually breaks things: a field renamed, removed, or added
 * server-side without the client noticing.
 *
 * This file has no runtime output. It exists to be typechecked.
 */
import type { components } from "./api-types";
import type {
  AuthUser,
  InterestCount,
  LabelCount,
  MyProfile,
  Person,
  PersonState,
  ProfileList,
  SavedSearch,
  Stats,
  WritingTips,
} from "./types";

type Schemas = components["schemas"];

/** Compiles only when the two key sets are identical. */
type SameKeys<A, B> = [keyof A] extends [keyof B]
  ? [keyof B] extends [keyof A]
    ? true
    : { missingFromFirst: Exclude<keyof B, keyof A> }
  : { missingFromSecond: Exclude<keyof A, keyof B> };

/**
 * Each line below reads: "the client type and the server model declare the same
 * fields". A drift makes the assigned `true` fail against an object type whose
 * key names the offending field — so the compiler error says what moved.
 */
const _person: SameKeys<Person, Schemas["PersonOut"]> = true;
const _profileList: SameKeys<ProfileList, Schemas["ProfileListOut"]> = true;
const _stats: SameKeys<Stats, Schemas["StatsOut"]> = true;
const _personState: SameKeys<PersonState, Schemas["PersonStateOut"]> = true;
const _savedSearch: SameKeys<SavedSearch, Schemas["SavedSearchOut"]> = true;
const _myProfile: SameKeys<MyProfile, Schemas["UserProfileOut"]> = true;
const _writingTips: SameKeys<WritingTips, Schemas["WritingTipsOut"]> = true;
const _interestCount: SameKeys<InterestCount, Schemas["InterestCount"]> = true;
const _labelCount: SameKeys<LabelCount, Schemas["LabelCount"]> = true;
const _authUser: SameKeys<AuthUser, Schemas["UserOut"]> = true;

/**
 * The username must never reach the client. It is excluded from the response
 * model server-side; this asserts it is absent from the published schema too,
 * so a future `exclude=True` removal is caught here rather than by someone
 * noticing usernames in a network tab.
 */
const _noAuthorLeak: "author" extends keyof Schemas["PersonOut"] ? never : true = true;

// Referenced so the compiler does not report them as unused, and so this module
// has an export and can be part of the build.
export const CONTRACT_VERIFIED = [
  _person,
  _profileList,
  _stats,
  _personState,
  _savedSearch,
  _myProfile,
  _writingTips,
  _interestCount,
  _labelCount,
  _authUser,
  _noAuthorLeak,
].every(Boolean);