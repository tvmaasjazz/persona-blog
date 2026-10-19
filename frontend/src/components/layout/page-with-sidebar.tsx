import type { ReactNode } from 'react'

type PageWithSidebarProps = {
  header: ReactNode
  sidebar: ReactNode
  children: ReactNode
}

// A page with its own right sidebar: pinned and sticky from lg, between header and content below.
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
