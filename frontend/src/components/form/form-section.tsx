import type { ReactNode } from 'react'

type FormSectionProps = {
  title: string
  children: ReactNode
}

export function FormSection({ title, children }: FormSectionProps) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="text-lg font-bold">{title}</h2>
      {children}
    </section>
  )
}
