"use client";

import { useEffect, useRef } from "react";
import styles from "./HomeSections.module.css";

/**
 * A silent background loop behind the hero. The garment photo is its poster, so the first paint is instant and
 * nothing changes for shoppers who asked for reduced motion (the video never plays for them). It plays only
 * while on screen and in a visible tab, to spare phones' batteries.
 */
export function HeroVideo({ src, poster }: { src: string; poster: string | undefined }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    let onScreen = true;
    const stopped = () => document.documentElement.hasAttribute("data-motion-paused");
    const sync = () => {
      if (reduce?.matches || !onScreen || document.hidden || stopped()) video.pause();
      else void video.play().catch(() => undefined); // autoplay refused: the poster stays
    };
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(([entry]) => {
            onScreen = Boolean(entry?.isIntersecting);
            sync();
          });
    observer?.observe(video);
    document.addEventListener("visibilitychange", sync);
    document.addEventListener("aurevon:motion", sync);
    reduce?.addEventListener?.("change", sync);
    sync();
    return () => {
      observer?.disconnect();
      document.removeEventListener("visibilitychange", sync);
      document.removeEventListener("aurevon:motion", sync);
      reduce?.removeEventListener?.("change", sync);
    };
  }, []);
  return (
    <video
      ref={ref}
      className={styles.heroVideo}
      src={src}
      poster={poster}
      muted
      loop
      playsInline
      preload="metadata"
      aria-hidden="true"
      tabIndex={-1}
    />
  );
}
