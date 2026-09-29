import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useRef, useState } from "react";
import { ROLE_LABELS, useAuth } from "@/lib/auth/AuthProvider";
import { authHref } from "@/lib/auth/redirect";
import { STRINGS } from "@/lib/i18n/strings";
import { Icon } from "./Icon";

/** Top-bar account control: a sign-in link for the public, a menu with role and sign-out for signed-in users. */
export function UserMenu() {
  const { user, logout, language } = useAuth();
  const { asPath } = useRouter();
  const t = STRINGS[language];
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (user.role === "public") {
    return (
      <Link href={authHref("/login", asPath)} className="flex items-center gap-1.5 rounded-md border border-line bg-field px-2.5 py-1 text-sm text-ink no-underline hover:bg-subtle">
        <Icon name="user" className="h-4 w-4" /> <span className="hidden sm:inline">{t.signIn}</span>
      </Link>
    );
  }
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="menu"
        className="flex items-center gap-1.5 rounded-md border border-line bg-field px-2.5 py-1 text-sm hover:bg-subtle">
        <Icon name="user" className="h-4 w-4" />
        <span className="hidden max-w-[10rem] truncate sm:inline">{user.name}</span>
        <Icon name="chevronDown" className="h-3.5 w-3.5 text-muted" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-md border border-line bg-panel p-3 text-sm shadow-lg">
          <div className="font-semibold">{user.name}</div>
          <div className="truncate text-xs text-muted">{user.email}</div>
          <div className="mt-2 flex flex-wrap gap-1 text-xs">
            <span className="rounded-[3px] bg-accent-soft px-1.5 py-0.5 text-accent">{ROLE_LABELS[user.role] ?? user.role}</span>
            {user.institution && <span className="rounded-[3px] bg-subtle px-1.5 py-0.5">{user.institution}</span>}
          </div>
          <div className="my-2 border-t border-line" />
          <button type="button" role="menuitem" onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-subtle">
            <Icon name="logout" className="h-4 w-4" /> {t.signOut}
          </button>
        </div>
      )}
    </div>
  );
}
