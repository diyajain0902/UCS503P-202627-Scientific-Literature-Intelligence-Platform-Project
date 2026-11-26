import { useEffect, useRef, type RefObject } from 'react'

// Escape closes only the top-most open layer (modal over drawer over popover).
const layers: RefObject<() => void>[] = []

function onKeyDown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || layers.length === 0) return
  event.preventDefault()
  layers[layers.length - 1].current()
}

/** Calls onEscape when Escape is pressed while `active` and this is the top-most active layer. */
export function useEscape(active: boolean, onEscape: () => void) {
  const handler = useRef(onEscape)
  useEffect(() => {
    handler.current = onEscape
  })
  useEffect(() => {
    if (!active) return
    if (layers.length === 0) window.addEventListener('keydown', onKeyDown)
    layers.push(handler)
    return () => {
      layers.splice(layers.indexOf(handler), 1)
      if (layers.length === 0) window.removeEventListener('keydown', onKeyDown)
    }
  }, [active])
}

/** Closes a popover on a pointer press outside `ref`. */
export function useOutsideClick(ref: RefObject<HTMLElement | null>, active: boolean, onOutside: () => void) {
  const handler = useRef(onOutside)
  useEffect(() => {
    handler.current = onOutside
  })
  useEffect(() => {
    if (!active) return
    const listener = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) handler.current()
    }
    document.addEventListener('mousedown', listener)
    return () => document.removeEventListener('mousedown', listener)
  }, [ref, active])
}
