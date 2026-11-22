import { CircleAlert, Info } from 'lucide-react'

type ActionNoticesProps = {
  busy: boolean
  running: boolean
  runMessage: string | null
  runNotice: string | null
  scoreRunning: boolean
  scoreError: string | null
}

type NoticeItem = {
  key: string
  tone: 'info' | 'err'
  text: string
}

const toneClasses: Record<NoticeItem['tone'], string> = {
  info: 'bg-info-soft text-info-ink',
  err: 'bg-err-soft text-err-ink',
}

export default function ActionNotices({
  busy,
  running,
  runMessage,
  runNotice,
  scoreRunning,
  scoreError,
}: ActionNoticesProps) {
  const items: NoticeItem[] = []

  if (busy || running) {
    items.push({ key: 'busy', tone: 'info', text: 'A step is running. Please wait.' })
  }
  if (runMessage !== null) {
    items.push({ key: 'run-message', tone: 'err', text: runMessage })
  }
  if (runNotice !== null) {
    items.push({ key: 'run-notice', tone: 'info', text: runNotice })
  }
  if (scoreRunning) {
    items.push({ key: 'score-running', tone: 'info', text: 'Scoring can take up to a minute.' })
  }
  if (scoreError !== null) {
    items.push({ key: 'score-error', tone: 'err', text: scoreError })
  }

  if (items.length === 0) return null

  return (
    <div className="mb-6 space-y-3">
      {items.map((item) => (
        <div
          key={item.key}
          role={item.tone === 'err' ? 'alert' : 'status'}
          className={`flex items-start gap-3 rounded-card px-4 py-3 text-sm ${toneClasses[item.tone]}`}
        >
          {item.tone === 'err' ? (
            <CircleAlert size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
          ) : (
            <Info size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
          )}
          <p>{item.text}</p>
        </div>
      ))}
    </div>
  )
}
