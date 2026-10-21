# Understand New Caching Defaults

**Category:** Next.js 15 Patterns  
**Impact:** HIGH (behavior change affects data freshness)

## Rule

In Next.js 15, `fetch` requests, GET Route Handlers, and client router cache are **no longer cached by default**. Explicitly opt in to caching when needed.

## Next.js 14 defaults (old)

```typescript
// Cached by default
fetch('https://api.example.com/data')

// GET Route Handlers — cached by default
export async function GET() {
  return Response.json({ data: 'cached' })
}
```

## Next.js 15 defaults (new)

```typescript
// NOT cached — opt in explicitly
fetch('https://api.example.com/data', { cache: 'force-cache' })

// Or use time-based revalidation
fetch('https://api.example.com/data', { next: { revalidate: 3600 } })
```

## Route Handlers — opt in

```typescript
export const dynamic = 'force-static'
export async function GET() {
  return Response.json({ data: 'cached at build time' })
}
```

## Client router cache

```typescript
// Restore previous behavior via next.config.ts
const nextConfig = {
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
}
```

## When to cache explicitly

- API responses that rarely change (config, feature flags)
- Expensive database queries
- Static content (blog posts, documentation)
- Third-party API calls with rate limits

## When fresh defaults are better

- User-specific data (profiles, dashboards)
- Real-time data (notifications, live feeds)
- Frequently changing data (prices, inventory)

## Reference

- [https://nextjs.org/blog/next-15#caching-updates](https://nextjs.org/blog/next-15#caching-updates)
