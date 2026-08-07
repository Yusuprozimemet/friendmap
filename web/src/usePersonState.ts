import { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchMyPeople, setPersonState } from "./api";
import type { PersonState, PersonStatePatch } from "./types";

export interface PersonStateApi {
  /** Current state for a person, or null when untouched. */
  get: (personKey: string) => PersonState | null;
  /** Applies a partial change. No-op when signed out. */
  set: (personKey: string, patch: PersonStatePatch) => void;
  savedCount: number;
  contactedCount: number;
  hiddenCount: number;
  signedIn: boolean;
}

/**
 * One fetch of the user's whole list, kept in a map. It's a few hundred rows
 * at most, and holding it locally is what lets every card render its own
 * state without a request per card.
 */
export function usePersonState(signedIn: boolean): PersonStateApi {
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["my-people"],
    queryFn: ({ signal }) => fetchMyPeople(signal),
    enabled: signedIn,
    staleTime: 60_000,
  });

  const byKey = useMemo(() => {
    const map = new Map<string, PersonState>();
    for (const row of data ?? []) map.set(row.person_key, row);
    return map;
  }, [data]);

  const mutation = useMutation({
    mutationFn: ({ key, patch }: { key: string; patch: PersonStatePatch }) =>
      setPersonState(key, patch),
    // Optimistic: a bookmark that lags behind the click feels broken.
    onMutate: async ({ key, patch }) => {
      await qc.cancelQueries({ queryKey: ["my-people"] });
      const previous = qc.getQueryData<PersonState[]>(["my-people"]) ?? [];
      const current = previous.find((r) => r.person_key === key);
      const next: PersonState = {
        person_key: key,
        saved: patch.saved ?? current?.saved ?? false,
        status: patch.set_status
          ? (patch.status ?? null)
          : (current?.status ?? null),
        note: patch.note ?? current?.note ?? "",
        updated_at: new Date().toISOString(),
      };
      qc.setQueryData<PersonState[]>(
        ["my-people"],
        [...previous.filter((r) => r.person_key !== key), next],
      );
      return { previous };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.previous) qc.setQueryData(["my-people"], ctx.previous);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["my-people"] });
      // Hiding someone changes who the map and list should show.
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });

  const get = useCallback(
    (personKey: string) => byKey.get(personKey) ?? null,
    [byKey],
  );

  const set = useCallback(
    (personKey: string, patch: PersonStatePatch) => {
      if (!signedIn || !personKey) return;
      mutation.mutate({ key: personKey, patch });
    },
    [signedIn, mutation],
  );

  const rows = data ?? [];
  return {
    get,
    set,
    savedCount: rows.filter((r) => r.saved).length,
    contactedCount: rows.filter((r) => r.status === "contacted").length,
    hiddenCount: rows.filter((r) => r.status === "hidden").length,
    signedIn,
  };
}
