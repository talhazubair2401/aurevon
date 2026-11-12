"use client";

import { useState } from "react";
import styles from "./HomeSections.module.css";

/**
 * WCAG 2.2.2: the hero video and the brand band move on their own for longer than five seconds, so shoppers can
 * pause them. Pausing marks the page; the video and every looping hero animation read that mark.
 */
export function MotionToggle({ pause, play }: { pause: string; play: string }) {
  const [paused, setPaused] = useState(false);
  const toggle = () => {
    const next = !paused;
    setPaused(next);
    document.documentElement.toggleAttribute("data-motion-paused", next);
    document.dispatchEvent(new Event("aurevon:motion"));
  };
  return (
    <button type="button" className={styles.motionToggle} aria-pressed={paused} onClick={toggle}>
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        {paused ? <path d="M5 3l8 5-8 5z" /> : <path d="M4 3h3v10H4zM9 3h3v10H9z" />}
      </svg>
      <span className={styles.srOnly}>{paused ? play : pause}</span>
    </button>
  );
}
