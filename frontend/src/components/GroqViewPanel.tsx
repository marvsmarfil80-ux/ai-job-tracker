import type { ProfileRedactions } from '../types'

type GroqViewPanelProps = {
  view: string
  redactions: ProfileRedactions
  warnings: string[]
}

export default function GroqViewPanel({ view, redactions, warnings }: GroqViewPanelProps) {
  return (
    <div className="rounded-card border border-line bg-surface p-6 shadow-card">
      <h2 className="text-lg font-semibold text-ink">What Groq sees</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Only this sanitized text is sent to Groq.
      </p>
      <div className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-sunken p-3 text-sm text-ink">
        {view}
      </div>
      <div className="mt-4 grid max-w-md grid-cols-3 gap-2 text-sm">
        <div className="rounded-lg bg-sunken p-2">
          <p className="text-xs text-ink-muted">Emails</p>
          <p className="mt-1 font-semibold text-ink">{redactions.emails}</p>
        </div>
        <div className="rounded-lg bg-sunken p-2">
          <p className="text-xs text-ink-muted">Phones</p>
          <p className="mt-1 font-semibold text-ink">{redactions.phones}</p>
        </div>
        <div className="rounded-lg bg-sunken p-2">
          <p className="text-xs text-ink-muted">Lines</p>
          <p className="mt-1 font-semibold text-ink">{redactions.lines}</p>
        </div>
      </div>
      {warnings.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-4 text-sm text-ink-muted">
          {warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
