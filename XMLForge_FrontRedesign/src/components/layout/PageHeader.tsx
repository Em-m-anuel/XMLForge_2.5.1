import type { ReactNode } from "react";
import { Icon, type IconName } from "../Icon";
import { cn } from "../../utils/cn";

export function PageHeader({
  icon,
  title,
  subtitle,
  badges,
  meta,
  actions,
  tabs,
  accent,
}: {
  icon?: IconName;
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  meta?: { label: string; value: ReactNode; icon?: IconName }[];
  actions?: ReactNode;
  tabs?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="border-b border-line bg-surface/40">
      <div className="flex flex-wrap items-start justify-between gap-4 px-6 pb-3.5 pt-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            {icon && (
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border",
                  accent
                    ? "border-accent/40 bg-accent-soft text-accent"
                    : "border-line bg-raised text-muted",
                )}
              >
                <Icon name={icon} size={15} />
              </span>
            )}
            <h1 className="truncate text-[19px] font-semibold tracking-tight text-fg">{title}</h1>
            {badges && <div className="flex items-center gap-1.5">{badges}</div>}
          </div>
          {subtitle && <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12.5px] text-muted">{subtitle}</div>}
          {meta && meta.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1.5">
              {meta.map((m) => (
                <div key={m.label} className="flex items-center gap-1.5 text-[11.5px]">
                  {m.icon && <Icon name={m.icon} size={12} className="text-dim" />}
                  <span className="text-dim">{m.label}</span>
                  <span className="font-mono text-fg/90">{m.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {tabs && <div className="px-6">{tabs}</div>}
    </div>
  );
}
