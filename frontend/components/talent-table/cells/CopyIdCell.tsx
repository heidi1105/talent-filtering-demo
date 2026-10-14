'use client'

import { useState } from 'react'

// Click-to-copy cell for the ID column — stops row-select propagation and
// shows brief "Copied" feedback in place of the id.
export function CopyIdCell({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        navigator.clipboard.writeText(id)
        setCopied(true)
        setTimeout(() => setCopied(false), 1200)
      }}
      title="Click to copy ID"
      className="font-mono text-xs text-muted hover:text-accent transition-colors duration-150 cursor-pointer bg-transparent border-none p-0"
    >
      {copied ? 'Copied' : id}
    </button>
  )
}
