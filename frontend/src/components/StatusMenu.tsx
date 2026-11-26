import { ChevronDown } from 'lucide-react'
import ChoiceMenu from './ChoiceMenu'
import type { ChoiceOption } from './ChoiceMenu'
import type { ApplicationStatus } from '../lib/applications'
import { applicationStatusTone, statusOptions } from '../lib/applications'

type StatusMenuProps = {
  value: ApplicationStatus
  disabled: boolean
  onSelect: (status: ApplicationStatus) => void
}

const dotTones: Record<string, string> = {
  ok: 'text-ok-ink',
  warn: 'text-warn-ink',
  err: 'text-err-ink',
  info: 'text-info-ink',
  idle: 'text-idle-ink',
}

const options: ChoiceOption[] = statusOptions.map((option) => ({
  value: option.value,
  label: option.label,
  dotClass: dotTones[applicationStatusTone(option.value)],
}))

export default function StatusMenu({ value, disabled, onSelect }: StatusMenuProps) {
  return (
    <ChoiceMenu
      options={options}
      value={value}
      disabled={disabled}
      menuLabel="Change status"
      align="right"
      triggerClassName="inline-flex h-9 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-accent-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50"
      triggerContent={(open) => (
        <>
          Change status
          <ChevronDown
            size={14}
            aria-hidden="true"
            className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
          />
        </>
      )}
      onSelect={(next) => onSelect(next as ApplicationStatus)}
    />
  )
}
