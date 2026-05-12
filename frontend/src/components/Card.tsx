import { useState, type ReactNode } from "react";

interface CardProps {
  storageKey: string;
  className?: string;
  children: ReactNode;
  defaultCollapsed?: boolean;
}

export function Card({ storageKey, className = "", children, defaultCollapsed = false }: CardProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(`card.${storageKey}`);
      if (stored === "1") return true;
      if (stored === "0") return false;
    } catch {
      /* noop */
    }
    return defaultCollapsed;
  });

  const toggle = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(`card.${storageKey}`, next ? "1" : "0");
      } catch {
        /* noop */
      }
      return next;
    });
  };

  return (
    <div className={`card ${className} ${collapsed ? "collapsed" : ""}`}>
      <button
        type="button"
        className="card-toggle"
        onClick={toggle}
        title={collapsed ? "Expandir" : "Minimizar"}
        aria-label={collapsed ? "Expandir" : "Minimizar"}
      >
        {collapsed ? "+" : "−"}
      </button>
      <div className="card-inner">{children}</div>
    </div>
  );
}
