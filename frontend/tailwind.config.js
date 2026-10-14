/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}',
    './hooks/**/*.{js,jsx,ts,tsx}',
    './lib/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:           'var(--bg)',
        surface:      'var(--surface)',
        surface2:     'var(--surface2)',
        border:       'var(--border)',
        border2:      'var(--border2)',
        text:         'var(--text)',
        muted:        'var(--text-muted)',
        dim:          'var(--text-dim)',
        accent:       'var(--accent)',
        accent2:      'var(--accent2)',
        'accent-dim': 'var(--accent-dim)',
        selected:     'var(--selected)',
        warn:         'var(--warn)',
        danger:       'var(--danger)',
        // Brand pill fills/outlines, keyed by confidence tier. Separate tokens
        // rather than opacity modifiers (bg-warn/10): the palette is delivered
        // as `var(--x)` colour strings, which Tailwind can't recompose into
        // rgb(… / <alpha-value>), so the modifier would silently no-op.
        'brand-high-fill':   'var(--brand-high-fill)',
        'brand-high-line':   'var(--brand-high-line)',
        'brand-medium-fill': 'var(--brand-medium-fill)',
        'brand-medium-line': 'var(--brand-medium-line)',
        'brand-low-fill':    'var(--brand-low-fill)',
        'brand-low-line':    'var(--brand-low-line)',
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
      },
      fontFamily: {
        sans: ['var(--font-dm-sans)', 'sans-serif'],
        mono: ['var(--font-dm-mono)', 'monospace'],
      },
    },
  },
  plugins: [],
}
