"use client";

import { type ReactNode, useEffect, useRef } from "react";
import styles from "./HomeSections.module.css";

/**
 * Editorial reveal: a section drifts up and fades in once, when 15% of it is on screen. The server renders it
 * visible, so nothing is hidden without JavaScript; sections already on screen at load are left alone, and
 * reduced motion turns it off.
 */
export function Reveal({
  className,
  children,
}: {
  className?: string | undefined;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const box = el.getBoundingClientRect();
    if (box.top < window.innerHeight) return; // already in view: don't hide it
    el.dataset.reveal = "waiting";
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        el.dataset.reveal = "shown";
        observer.disconnect();
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className={[styles.reveal, className ?? ""].filter(Boolean).join(" ")}>
      {children}
    </div>
  );
}
