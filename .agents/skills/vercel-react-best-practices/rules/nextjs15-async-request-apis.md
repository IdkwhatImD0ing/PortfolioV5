# Await Async Request APIs

**Category:** Next.js 15 Patterns  
**Impact:** CRITICAL (breaking change in Next.js 15)

## Rule

In Next.js 15, `cookies()`, `headers()`, `params`, and `searchParams` are asynchronous. Code that accesses them synchronously will break.

## Incorrect: synchronous access (Next.js 14 pattern)

```tsx
import { cookies, headers } from 'next/headers'

export default function Page({ params, searchParams }: PageProps) {
  const { slug } = params
  const { q } = searchParams
  const cookieStore = cookies()
  const theme = cookieStore.get('theme')

  return <div>{slug} - {q} - {theme?.value}</div>
}
```

## Correct: await async APIs

```tsx
import { cookies, headers } from 'next/headers'

interface PageProps {
  params: Promise<{ slug: string }>
  searchParams: Promise<{ q?: string }>
}

export default async function Page({ params, searchParams }: PageProps) {
  const { slug } = await params
  const { q } = await searchParams
  const cookieStore = await cookies()
  const theme = cookieStore.get('theme')

  return <div>{slug} - {q} - {theme?.value}</div>
}
```

## In client components

```tsx
'use client'
import { use } from 'react'

export default function ClientPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = use(searchParams)
  return <div>Query: {q}</div>
}
```

## Migration

```bash
npx @next/codemod@canary next-async-request-api .
```

## Reference

- [https://nextjs.org/docs/app/building-your-application/upgrading/version-15](https://nextjs.org/docs/app/building-your-application/upgrading/version-15)
