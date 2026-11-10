import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// The library only unmounts rendered hooks by itself when afterEach is a global, and
// tests import theirs, so it's registered here
afterEach(() => {
  cleanup()
})
