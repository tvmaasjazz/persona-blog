import { useId, useState } from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDebouncedCallback } from '@/lib/use-debounced-callback'

const SEARCH_DEBOUNCE_MS = 300
// The backend's SearchStr limit
const SEARCH_MAX_LENGTH = 200

type ListSearchBoxProps = {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function ListSearchBox({ label, value, onChange, placeholder }: ListSearchBoxProps) {
  const inputId = useId()
  const [draft, setDraft] = useState(value)
  const [previousValue, setPreviousValue] = useState(value)
  const notifyChange = useDebouncedCallback(onChange, SEARCH_DEBOUNCE_MS)

  // Follow the value when it changes from outside, such as a cleared URL
  if (value !== previousValue) {
    setPreviousValue(value)
    setDraft(value)
  }

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={inputId}>{label}</Label>
      <Input
        id={inputId}
        type="search"
        maxLength={SEARCH_MAX_LENGTH}
        value={draft}
        placeholder={placeholder}
        onChange={(event) => {
          setDraft(event.target.value)
          notifyChange(event.target.value)
        }}
      />
    </div>
  )
}
