# Use useActionState for Form Handling

**Category:** React 19 Patterns  
**Impact:** HIGH (eliminates manual form state management)

## Rule

Use `useActionState` to manage form state including pending status and error handling. Works with Server Actions and client-side form handlers. Use `useFormStatus` for submit button state.

## Incorrect: manual form state management

```tsx
function LoginForm() {
  const [error, setError] = useState<string | null>(null)
  const [isPending, setIsPending] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsPending(true)
    setError(null)
    try {
      await login(new FormData(e.currentTarget as HTMLFormElement))
    } catch (err) {
      setError(err.message)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" required />
      {error && <p className="text-red-500">{error}</p>}
      <button disabled={isPending}>
        {isPending ? 'Logging in...' : 'Log in'}
      </button>
    </form>
  )
}
```

## Correct: useActionState with Server Action

```tsx
'use client'
import { useActionState } from 'react'
import { login } from './actions'

function LoginForm() {
  const [state, formAction, isPending] = useActionState(login, { error: null })

  return (
    <form action={formAction}>
      <input name="email" type="email" required />
      {state.error && <p className="text-red-500">{state.error}</p>}
      <button disabled={isPending}>
        {isPending ? 'Logging in...' : 'Log in'}
      </button>
    </form>
  )
}
```

## useFormStatus for submit buttons

```tsx
import { useFormStatus } from 'react-dom'

function SubmitButton() {
  const { pending } = useFormStatus()
  return (
    <button disabled={pending}>
      {pending ? 'Submitting...' : 'Submit'}
    </button>
  )
}
```

## Benefits

- Progressive enhancement: forms work before JavaScript loads
- Automatic pending state management
- Built-in error handling through return values
- Works with Server Actions for zero-client-JS mutations

## Reference

- [https://react.dev/reference/react/useActionState](https://react.dev/reference/react/useActionState)
