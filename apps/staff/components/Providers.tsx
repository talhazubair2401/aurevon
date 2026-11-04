"use client";

import type { ReactNode } from "react";
import { SessionProvider } from "../lib/session";
import { StepUpProvider } from "./StepUp";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <StepUpProvider>{children}</StepUpProvider>
    </SessionProvider>
  );
}
