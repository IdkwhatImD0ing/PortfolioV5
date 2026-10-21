# Pass ref as a Prop Instead of forwardRef

**Category:** React 19 Patterns  
**Impact:** MEDIUM (reduces boilerplate and improves readability)

## Rule

In React 19, `ref` is a regular prop for function components. `forwardRef` is deprecated and will be removed in a future version.

## Incorrect: using forwardRef (deprecated)

```tsx
import { forwardRef } from 'react'

const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ label, ...props }, ref) {
    return (
      <label>
        {label}
        <input ref={ref} {...props} />
      </label>
    )
  }
)
```

## Correct: ref as a regular prop

```tsx
function Input({ label, ref, ...props }: InputProps & { ref?: React.Ref<HTMLInputElement> }) {
  return (
    <label>
      {label}
      <input ref={ref} {...props} />
    </label>
  )
}
```

## Migration

Use the React 19 codemod:

```bash
npx codemod@latest react/19/replace-reactdom-render
```

## Reference

- [https://react.dev/blog/2024/12/05/react-19#ref-as-a-prop](https://react.dev/blog/2024/12/05/react-19#ref-as-a-prop)
