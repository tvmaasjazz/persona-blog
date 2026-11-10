import type { ReactNode } from 'react'

type SectionCardProps = {
  title: string
  children: ReactNode
}

export function SectionCard({ title, children }: SectionCardProps) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <h2 className="text-xl font-extrabold">{title}</h2>
      {children}
    </section>
  )
}
