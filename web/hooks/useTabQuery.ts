import { useRouter } from "next/router";

/**
 * The selected tab lives in the URL (?tab=...), so every tab can be linked to and survives a reload.
 * Unknown values fall back to the first tab.
 */
export function useTabQuery<T extends string>(tabIds: readonly T[]): [T, (tab: T) => void] {
  const router = useRouter();
  const requested = typeof router.query.tab === "string" ? router.query.tab : "";
  const active = (tabIds as readonly string[]).includes(requested) ? (requested as T) : tabIds[0];

  const setTab = (tab: T) => {
    router.replace({ pathname: router.pathname, query: { ...router.query, tab } }, undefined, { shallow: true, scroll: false });
  };

  return [active, setTab];
}
