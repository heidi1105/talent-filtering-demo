export function SortIcon({ direction }: { direction: 'asc' | 'desc' | null }) {
  if (!direction) return <span className="text-[10px] text-dim">⇅</span>
  return <span className="text-[10px] text-accent">{direction === 'asc' ? '↑' : '↓'}</span>
}
