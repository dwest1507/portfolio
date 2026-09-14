// jest-dom matcher types for Vitest.
//
// `@testing-library/jest-dom` ships a Vitest augmentation (`.../vitest`), but it
// still declares `interface Assertion<T = any>` — the Vitest 4 shape. Vitest 5
// inlined its `expect` package and widened that to
// `Assertion<R extends void | Promise<void>, T>`, so the shipped augmentation no
// longer merges and every `expect(el).toBeInTheDocument()` fails to type check.
//
// Vitest 5's own extension point is `Matchers`, which both `Assertion` and
// `AsymmetricMatchersContaining` extend, so augmenting it once covers both.
// The type parameter list must match Vitest's declaration exactly for the
// interfaces to merge. Drop this file once jest-dom ships Vitest 5 types.
import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers'

declare module 'vitest' {
  // The empty body is the point: it merges jest-dom's matchers into Vitest's.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Matchers<
    R extends void | Promise<void> = void | Promise<void>,
    T = unknown,
  > extends TestingLibraryMatchers<T, R> {}
}
