export function Card({ title, children, className = "", right }: {
  title?: React.ReactNode; children: React.ReactNode; className?: string; right?: React.ReactNode;
}) {
  return (
    <section className={`rounded-md border border-line bg-panel p-4 md:p-5 ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="font-serif text-[16px] font-bold leading-snug">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}
