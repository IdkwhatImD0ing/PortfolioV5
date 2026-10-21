# Use the use() Hook for Promises and Context

**Category:** React 19 Patterns  
**Impact:** HIGH (simplifies async data consumption in components)

## Rule

Use the `use()` hook to read Promises and Context. Unlike other hooks, `use()` can be called inside loops and conditionals. When used with Promises, it integrates with Suspense and Error Boundaries.

## Incorrect: useEffect + useState for async data

```tsx
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const [user, setUser] = useState<User | null>(null)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    userPromise.then(setUser).catch(setError)
  }, [userPromise])

  if (error) return <ErrorDisplay error={error} />
  if (!user) return <Skeleton />
  return <div>{user.name}</div>
}
```

## Correct: use() with Suspense

```tsx
import { use } from 'react'

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise)
  return <div>{user.name}</div>
}

function Page() {
  const userPromise = fetchUser()
  return (
    <ErrorBoundary fallback={<ErrorDisplay />}>
      <Suspense fallback={<Skeleton />}>
        <UserProfile userPromise={userPromise} />
      </Suspense>
    </ErrorBoundary>
  )
}
```

## Conditional context reading

```tsx
function StatusIndicator({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) {
    const adminData = use(AdminContext)
    return <AdminBadge data={adminData} />
  }
  return <UserBadge />
}
```

**Important:** Only pass Promises created outside of the component. Promises created during render cause the component to re-suspend on every render.

## Reference

- [https://react.dev/reference/react/use](https://react.dev/reference/react/use)
