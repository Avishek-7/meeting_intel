import type { ReactNode } from "react";

interface HeaderProps {
  title: string;
  subtitle?: string;
  rightContent?: ReactNode;
}

export default function Header({ title, subtitle, rightContent }: HeaderProps) {
  return (
    <header className="mi-header">
      <div className="mi-header-left">
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {rightContent ? <div className="mi-header-right">{rightContent}</div> : null}
    </header>
  );
}