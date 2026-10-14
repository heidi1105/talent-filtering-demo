// Grey/muted tag pill — used for every array-valued column except Brands
// (blue pills stay reserved for brand tags per the design system).
export function TagPills({ values }: { values: string[] | null | undefined }) {
  return (values || []).length > 0
    ? (values || []).map((v) => (
        <span
          key={v}
          className="inline-block text-[11px] px-[7px] py-0.5 rounded-[20px] bg-surface2 border border-border2 text-muted mr-0.5 mb-0.5 whitespace-nowrap"
        >
          {v}
        </span>
      ))
    : '—'
}
