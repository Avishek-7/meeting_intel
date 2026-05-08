import type { ReactNode } from "react";

interface BackgroundProps {
  children: ReactNode;
}

export default function Background({ children }: BackgroundProps) {
  return (
    <div className="mi-background">
      <div className="mi-aurora mi-aurora-left" aria-hidden="true" />
      <div className="mi-aurora mi-aurora-right" aria-hidden="true" />
      <div className="mi-grid" aria-hidden="true" />
      {children}
    </div>
  );
}
