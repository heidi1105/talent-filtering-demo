// Same pill styling as BrandPills (low-confidence/red tier), reused here to
// flag that a talent has manual remarks. Shown under the name; hovering
// reveals the remarks text via the native title tooltip — same interaction
// BrandPills uses for its own pills.
const PILL = 'inline-block text-[11px] px-[7px] py-0.5 rounded-[20px] border mr-0.5 mb-0.5 whitespace-nowrap'
const RED  = 'bg-brand-low-fill border-brand-low-line text-danger'

interface RemarksLabelProps {
  remarks: string | null | undefined
}

export function RemarksLabel({ remarks }: RemarksLabelProps) {
  if (!remarks) return null
  return (
    <span title={remarks} className={`${PILL} ${RED} mt-[2px]`}>
      Remarks
    </span>
  )
}
