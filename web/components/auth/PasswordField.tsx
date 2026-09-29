import { useState } from "react";
import { Icon } from "@/components/layout/Icon";
import { inputClass } from "@/components/ui";

/** Password input with a show / hide toggle. */
export function PasswordField({ id, value, onChange, autoComplete, minLength, describedBy }: {
  id: string; value: string; onChange: (v: string) => void; autoComplete: string; minLength?: number; describedBy?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={visible ? "text" : "password"} required minLength={minLength} autoComplete={autoComplete}
        value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={describedBy}
        className={`${inputClass} py-2 pr-10`} />
      <button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted hover:bg-subtle hover:text-ink">
        <Icon name={visible ? "eyeOff" : "eye"} className="h-4 w-4" />
      </button>
    </div>
  );
}
