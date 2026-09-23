import { PenLine } from 'lucide-react'

import { Button } from '@/components/ui/button'

function App() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <section className="flex w-full max-w-sm flex-col items-center gap-6 rounded-2xl border bg-card p-8 text-center">
        <PenLine className="size-10 text-primary-text" aria-hidden />
        <div className="flex flex-col gap-2">
          <h1 className="text-xl font-extrabold">Persona Blog</h1>
          <p className="text-muted-foreground">Personas that write, with you in the loop.</p>
        </div>
        <div className="flex w-full flex-col gap-3">
          <Button className="w-full">Get started</Button>
          <Button variant="secondary" className="w-full">
            Sign in
          </Button>
        </div>
      </section>
    </main>
  )
}

export default App
