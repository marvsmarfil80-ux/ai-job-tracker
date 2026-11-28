import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from './Sidebar'
import { navItems } from '../lib/nav'

export default function Shell() {
  const { pathname } = useLocation()
  const current = navItems.find(
    (item) => pathname === item.to || pathname.startsWith(`${item.to}/`),
  )
  const [openAt, setOpenAt] = useState<string | null>(null)
  const open = openAt === pathname
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  function closeMenu() {
    setOpenAt(null)
    menuButtonRef.current?.focus()
  }

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpenAt(null)
        menuButtonRef.current?.focus()
        return
      }
      if (event.key !== 'Tab' || !drawerRef.current) return
      const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])',
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  return (
    <div className="flex h-full bg-page text-ink">
      <div className="hidden lg:flex">
        <Sidebar />
      </div>
      <div id="mobile-menu" className={open ? 'fixed inset-0 z-40 flex lg:hidden' : 'hidden'}>
        <div aria-hidden="true" className="absolute inset-0 bg-black/50" onClick={closeMenu} />
        <div
          ref={drawerRef}
          role="dialog"
          aria-modal="true"
          aria-label="Main menu"
          className="relative flex h-full"
        >
          <Sidebar onNavigate={() => setOpenAt(null)} />
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Close menu"
            onClick={closeMenu}
            className="absolute right-2 top-2 inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-muted transition-colors duration-150 hover:bg-sunken hover:text-ink"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line bg-chrome px-4 sm:px-6 lg:h-[72px] lg:px-[42px]">
          <button
            ref={menuButtonRef}
            type="button"
            aria-label="Open menu"
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpenAt(pathname)}
            className="-ml-2 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors duration-150 hover:bg-sunken hover:text-ink lg:hidden"
          >
            <Menu size={20} aria-hidden="true" />
          </button>
          <nav aria-label="Breadcrumb" className="min-w-0">
            <ol className="flex min-w-0 items-center gap-2 text-sm">
              <li className="hidden text-ink-muted sm:block">Workspace</li>
              {current && (
                <>
                  <li aria-hidden="true" className="hidden text-ink-subtle sm:block">
                    /
                  </li>
                  <li aria-current="page" className="truncate font-semibold text-ink">
                    {current.label}
                  </li>
                </>
              )}
            </ol>
          </nav>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="max-w-[1500px] px-4 pb-12 pt-6 sm:px-6 lg:px-[42px] lg:pt-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
