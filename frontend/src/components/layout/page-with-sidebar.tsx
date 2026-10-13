import type { ReactNode } from 'react'

type PageWithSidebarProps = {
  header: ReactNode
  sidebar: ReactNode
  children: ReactNode
}

// A page with its own right sidebar. Its route sets hasSidebar (AppRouteHandle), so
// the main area spans the space right of the nav. From lg the sidebar is pinned to the
// right edge and sticky, and the header and content are centred in the space left of
// it. Below lg it sits between the header and the content.
export function PageWithSidebar({ header, sidebar, children }: PageWithSidebarProps) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-x-10">
      <div className="w-full lg:col-start-1 lg:mx-auto lg:max-w-[720px]">{header}</div>
      <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-start">
        {sidebar}
      </aside>
      <div className="w-full lg:col-start-1 lg:mx-auto lg:max-w-[720px]">{children}</div>
    </div>
  )
}
