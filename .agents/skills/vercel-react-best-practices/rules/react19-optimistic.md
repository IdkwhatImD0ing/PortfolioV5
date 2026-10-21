# Use useOptimistic for Instant Feedback

**Category:** React 19 Patterns  
**Impact:** MEDIUM-HIGH (eliminates perceived latency for mutations)

## Rule

Use `useOptimistic` to show an optimistic state while an async action is pending. The UI updates instantly and reverts if the action fails.

## Incorrect: wait for server response

```tsx
function LikeButton({ postId, liked, likeCount }: Props) {
  const [isLiked, setIsLiked] = useState(liked)
  const [count, setCount] = useState(likeCount)
  const [isPending, setIsPending] = useState(false)

  const handleLike = async () => {
    setIsPending(true)
    try {
      const result = await toggleLike(postId)
      setIsLiked(result.liked)
      setCount(result.count)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <button onClick={handleLike} disabled={isPending}>
      {isLiked ? '❤️' : '🤍'} {count}
    </button>
  )
}
```

## Correct: instant optimistic update

```tsx
import { useOptimistic } from 'react'

function LikeButton({ postId, liked, likeCount }: Props) {
  const [optimistic, setOptimistic] = useOptimistic(
    { liked, count: likeCount },
    (current, newLiked: boolean) => ({
      liked: newLiked,
      count: current.count + (newLiked ? 1 : -1)
    })
  )

  async function handleLike() {
    const newLiked = !optimistic.liked
    setOptimistic(newLiked)
    await toggleLike(postId)
  }

  return (
    <button onClick={handleLike}>
      {optimistic.liked ? '❤️' : '🤍'} {optimistic.count}
    </button>
  )
}
```

## Reference

- [https://react.dev/reference/react/useOptimistic](https://react.dev/reference/react/useOptimistic)
