import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Check } from 'lucide-react'

export type ChoiceOption = {
  value: string
  label: string
  dotClass?: string
}

type ChoiceMenuProps = {
  options: ChoiceOption[]
  value: string
  disabled?: boolean
  menuLabel: string
  triggerLabel?: string
  triggerClassName: string
  triggerContent: (open: boolean) => ReactNode
  align?: 'left' | 'right'
  onSelect: (value: string) => void
}

export default function ChoiceMenu({
  options,
  value,
  disabled = false,
  menuLabel,
  triggerLabel,
  triggerClassName,
  triggerContent,
  align = 'left',
  onSelect,
}: ChoiceMenuProps) {
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
    const index = options.findIndex((option) => option.value === value)
    itemRefs.current[index >= 0 ? index : 0]?.focus()
    return () => document.removeEventListener('pointerdown', handlePointer)
  }, [showMenu, value, options])

  function close() {
    setOpen(false)
    buttonRef.current?.focus()
  }

  function choose(next: string) {
    close()
    onSelect(next)
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
    <div ref={rootRef} className="relative shrink-0">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-label={triggerLabel}
        aria-haspopup="menu"
        aria-expanded={showMenu}
        aria-controls={showMenu ? menuId : undefined}
        className={triggerClassName}
      >
        {triggerContent(showMenu)}
      </button>

      {showMenu && (
        <div
          id={menuId}
          role="menu"
          aria-label={menuLabel}
          onKeyDown={handleMenuKeyDown}
          className={`absolute top-full z-20 mt-1.5 min-w-[13rem] rounded-xl border border-line bg-surface p-1.5 shadow-card ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          {options.map((option, index) => {
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
                className="flex w-full items-center gap-2.5 whitespace-nowrap rounded-lg px-2.5 py-2 text-left text-sm text-ink hover:bg-sunken focus-visible:bg-sunken"
              >
                {option.dotClass && (
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 shrink-0 rounded-full bg-current ${option.dotClass}`}
                  />
                )}
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
