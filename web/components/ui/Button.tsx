const VARIANT_CLASS = {
  primary: "bg-accent-solid font-medium text-white hover:brightness-110",
  ghost: "border border-line bg-field text-ink hover:bg-subtle",
  danger: "bg-danger font-medium text-white hover:brightness-110",
};

export function Button({ children, variant = "primary", className = "", ...props }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof VARIANT_CLASS }) {
  return (
    <button {...props} className={`rounded-[4px] px-3.5 py-1.5 text-sm transition disabled:opacity-50 ${VARIANT_CLASS[variant]} ${className}`}>
      {children}
    </button>
  );
}
