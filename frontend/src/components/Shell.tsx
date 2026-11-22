import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { navItems } from '../lib/nav'

export default function Shell() {
  const { pathname } = useLocation()
  const current = navItems.find(
    (item) => pathname === item.to || pathname.startsWith(`${item.to}/`),
  )

  return (
    <div className="flex h-full bg-page text-ink">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[72px] shrink-0 items-center border-b border-line bg-chrome px-[42px]">
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-2 text-sm">
              <li className="text-ink-muted">Workspace</li>
              {current && (
                <>
                  <li aria-hidden="true" className="text-ink-subtle">
                    /
                  </li>
                  <li aria-current="page" className="font-semibold text-ink">
                    {current.label}
                  </li>
                </>
              )}
            </ol>
          </nav>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1500px] px-[42px] pb-12 pt-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
