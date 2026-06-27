import { useEffect, useRef, useState } from "react";

/** Returns true for ~350ms whenever `value` changes — used to flash a
 * brief glitch animation on panel rows when their data updates. */
export function useGlitchOnChange(value) {
  const [glitching, setGlitching] = useState(false);
  const prev = useRef(value);

  useEffect(() => {
    if (prev.current === value) return;
    prev.current = value;
    setGlitching(true);
    const timer = setTimeout(() => setGlitching(false), 350);
    return () => clearTimeout(timer);
  }, [value]);

  return glitching;
}
