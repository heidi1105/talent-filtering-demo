export interface AgeRange {
  min: string
  max: string
}

export interface FollowerRange {
  min: number
  max: number
}

// "Flagged" = has remarks. Surfaced in column settings, not the filter bar.
export type FlagFilter = 'all' | 'flagged' | 'unflagged'
