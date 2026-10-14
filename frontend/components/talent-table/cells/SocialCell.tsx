import { humanizeFollowers, followerTooltip } from '@/lib/talentDisplay'

interface SocialCellProps {
  handle: string | null
  followers: number | null
  capturedAt?: string | null
  href?: string
}

// One cell for a platform's handle + follower count, stacked — e.g.
// "@imhyoseop" over "(14.3M)". Hovering shows the exact count and last-captured date.
export function SocialCell({ handle, followers, capturedAt = null, href }: SocialCellProps) {
  if (!handle) return <>—</>

  return (
    <div title={followers !== null ? followerTooltip(followers, capturedAt) : undefined}>
      <div>
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-accent no-underline font-mono text-xs hover:opacity-75 transition-opacity duration-150"
          >
            @{handle}
          </a>
        ) : (
          <span className="text-text font-mono text-xs">@{handle}</span>
        )}
      </div>
      {followers !== null && (
        <div className="text-dim text-[11px] font-mono leading-tight">
          ({humanizeFollowers(followers)})
        </div>
      )}
    </div>
  )
}
