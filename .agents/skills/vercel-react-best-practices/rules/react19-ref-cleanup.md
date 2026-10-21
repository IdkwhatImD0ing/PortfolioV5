# Use Ref Cleanup Functions

**Category:** React 19 Patterns  
**Impact:** MEDIUM (prevents memory leaks and stale refs)

## Rule

In React 19, ref callbacks can return a cleanup function that runs when the element is removed from the DOM. This co-locates setup and teardown with the DOM element.

## Incorrect: manual cleanup with useEffect

```tsx
function VideoPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) videoRef.current?.play()
        else videoRef.current?.pause()
      })
    })

    if (videoRef.current) observer.observe(videoRef.current)
    return () => observer.disconnect()
  }, [])

  return <video ref={videoRef} src={src} />
}
```

## Correct: cleanup in ref callback

```tsx
function VideoPlayer({ src }: { src: string }) {
  return (
    <video
      ref={(node) => {
        if (!node) return
        const observer = new IntersectionObserver(entries => {
          entries.forEach(entry => {
            if (entry.isIntersecting) node.play()
            else node.pause()
          })
        })
        observer.observe(node)
        return () => observer.disconnect()
      }}
      src={src}
    />
  )
}
```

## When to use

- Setting up observers (IntersectionObserver, ResizeObserver, MutationObserver)
- Adding event listeners directly to DOM elements
- Initializing third-party libraries on DOM nodes
- Any setup that requires corresponding teardown

## Reference

- [https://react.dev/blog/2024/12/05/react-19#ref-cleanup-functions](https://react.dev/blog/2024/12/05/react-19#ref-cleanup-functions)
