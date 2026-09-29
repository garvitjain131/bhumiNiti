/** A same-site path to return to after signing in; anything else (external or protocol-relative URLs) becomes "/". */
export function safeNext(value: unknown): string {
  const v = Array.isArray(value) ? value[0] : value;
  return typeof v === "string" && v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/login") && !v.startsWith("/register")
    ? v : "/";
}

/** The sign-in (or sign-up) URL that brings the user back to `path` afterwards. */
export function authHref(page: "/login" | "/register", path?: string): string {
  const next = safeNext(path);
  return next === "/" ? page : `${page}?next=${encodeURIComponent(next)}`;
}
