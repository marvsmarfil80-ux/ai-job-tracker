import type { ProfileRedactions } from '../types'

type GroqViewPanelProps = {
  view: string
  redactions: ProfileRedactions
  warnings: string[]
}

export default function GroqViewPanel({ view, redactions, warnings }: GroqViewPanelProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">What Groq sees</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Only this sanitized text is sent to Groq.
      </p>
      <div className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-neutral-50 p-3 text-sm text-neutral-700">
        {view}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
        <div className="rounded-md bg-neutral-50 p-2">
          <p className="text-xs text-neutral-500">Emails</p>
          <p className="mt-1 font-semibold text-neutral-900">{redactions.emails}</p>
        </div>
        <div className="rounded-md bg-neutral-50 p-2">
          <p className="text-xs text-neutral-500">Phones</p>
          <p className="mt-1 font-semibold text-neutral-900">{redactions.phones}</p>
        </div>
        <div className="rounded-md bg-neutral-50 p-2">
          <p className="text-xs text-neutral-500">Lines</p>
          <p className="mt-1 font-semibold text-neutral-900">{redactions.lines}</p>
        </div>
      </div>
      {warnings.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-4 text-sm text-neutral-600">
          {warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
