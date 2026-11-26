import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Check, ChevronDown } from 'lucide-react'
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

export default function StatusMenu({ value, disabled, onSelect }: StatusMenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])
  const menuId = useId()
  const showMenu = open && !disabled

  useEffect(() => {
    if (!showMenu) return
    function handlePointer(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', handlePointer)
    const index = statusOptions.findIndex((option) => option.value === value)
    itemRefs.current[index >= 0 ? index : 0]?.focus()
    return () => document.removeEventListener('pointerdown', handlePointer)
  }, [showMenu, value])

  function close() {
    setOpen(false)
    buttonRef.current?.focus()
  }

  function choose(status: ApplicationStatus) {
    close()
    onSelect(status)
  }

  function handleMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const items = itemRefs.current.filter((item): item is HTMLButtonElement => item !== null)
    const current = items.indexOf(document.activeElement as HTMLButtonElement)
    if (event.key === 'Escape') {
      event.preventDefault()
      close()
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      items[(current + 1) % items.length]?.focus()
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      items[(current - 1 + items.length) % items.length]?.focus()
    } else if (event.key === 'Home') {
      event.preventDefault()
      items[0]?.focus()
    } else if (event.key === 'End') {
      event.preventDefault()
      items[items.length - 1]?.focus()
    } else if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={showMenu}
        aria-controls={showMenu ? menuId : undefined}
        className="inline-flex h-9 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-accent-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50"
      >
        Change status
        <ChevronDown
          size={14}
          aria-hidden="true"
          className={`transition-transform duration-150 ${showMenu ? 'rotate-180' : ''}`}
        />
      </button>

      {showMenu && (
        <div
          id={menuId}
          role="menu"
          aria-label="Change status"
          onKeyDown={handleMenuKeyDown}
          className="absolute right-0 top-full z-20 mt-1.5 w-52 rounded-xl border border-line bg-surface p-1.5 shadow-card"
        >
          {statusOptions.map((option, index) => {
            const current = option.value === value
            return (
              <button
                key={option.value}
                ref={(node) => {
                  itemRefs.current[index] = node
                }}
                type="button"
                role="menuitemradio"
                aria-checked={current}
                onClick={() => choose(option.value)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-ink hover:bg-sunken focus-visible:bg-sunken"
              >
                <span
                  aria-hidden="true"
                  className={`h-1.5 w-1.5 shrink-0 rounded-full bg-current ${dotTones[applicationStatusTone(option.value)]}`}
                />
                <span className="flex-1">{option.label}</span>
                {current && <Check size={14} aria-hidden="true" className="text-accent-ink" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
