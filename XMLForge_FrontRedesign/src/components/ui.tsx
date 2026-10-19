import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { cn } from "../utils/cn";
import { Icon, type IconName } from "./Icon";

/* ---------------------------------------------------------- Overlay layers */

type OverlayApi = {
  closePopovers: () => void;
  subscribePopovers: (fn: () => void) => () => void;
  beginModal: (onEscape: () => void) => void;
  endModal: () => void;
};

const OverlayCtx = createContext<OverlayApi>({
  closePopovers: () => {},
  subscribePopovers: () => () => {},
  beginModal: () => {},
  endModal: () => {},
});

export const useOverlay = () => useContext(OverlayCtx);

export function OverlayProvider({ children }: { children: ReactNode }) {
  const popovers = useRef(new Set<() => void>());
  const escapes = useRef<(() => void)[]>([]);
  const modalCount = useRef(0);

  const api = useMemo<OverlayApi>(
    () => ({
      closePopovers: () => popovers.current.forEach((fn) => fn()),
      subscribePopovers: (fn) => {
        popovers.current.add(fn);
        return () => popovers.current.delete(fn);
      },
      beginModal: (onEscape) => {
        popovers.current.forEach((fn) => fn());
        modalCount.current += 1;
        escapes.current.push(onEscape);
        document.body.classList.add("xf-lock-scroll");
      },
      endModal: () => {
        modalCount.current = Math.max(0, modalCount.current - 1);
        escapes.current.pop();
        if (modalCount.current === 0) document.body.classList.remove("xf-lock-scroll");
      },
    }),
    [],
  );

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const top = escapes.current[escapes.current.length - 1];
      if (!top) return;
      e.preventDefault();
      e.stopPropagation();
      top();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  return <OverlayCtx.Provider value={api}>{children}</OverlayCtx.Provider>;
}

const FOCUSABLE = "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

/* ------------------------------------------------------------------ Button */

type Variant = "primary" | "default" | "ghost" | "danger" | "success";
type Size = "xs" | "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-[#08131e] hover:bg-[#82b6ee] border-transparent font-medium",
  default: "bg-raised text-fg border-line hover:bg-[#2a2a33] hover:border-[#363641]",
  ghost: "bg-transparent text-muted border-transparent hover:bg-raised hover:text-fg",
  danger: "bg-danger-soft text-danger border-[#4a2323] hover:bg-[#3a1c1c]",
  success: "bg-ok-soft text-ok border-[#1e4032] hover:bg-[#173527]",
};

const SIZES: Record<Size, string> = {
  xs: "h-6 px-2 text-[11px] gap-1.5 rounded-md",
  sm: "h-7.5 px-2.5 text-[12.5px] gap-1.5 rounded-md",
  md: "h-9 px-3.5 text-[13px] gap-2 rounded-lg",
};

export function Button({
  variant = "default",
  size = "sm",
  icon,
  iconRight,
  loading,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center border transition-colors duration-150 select-none whitespace-nowrap",
        "disabled:opacity-45 disabled:pointer-events-none",
        SIZES[size],
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <span className="h-3 w-3 animate-spin rounded-full border-[1.5px] border-current border-t-transparent" />
      ) : icon ? (
        <Icon name={icon} size={size === "md" ? 16 : 14} />
      ) : null}
      {children}
      {iconRight && !loading ? <Icon name={iconRight} size={size === "md" ? 16 : 14} /> : null}
    </button>
  );
}

export function IconButton({
  icon,
  label,
  size = 14,
  className,
  active,
  tone = "default",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: IconName;
  label: string;
  size?: number;
  active?: boolean;
  tone?: "default" | "danger";
}) {
  return (
    <button
      title={label}
      aria-label={label}
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-md border border-transparent transition-colors",
        tone === "danger"
          ? "text-muted hover:bg-danger-soft hover:text-danger"
          : "text-muted hover:bg-raised hover:text-fg",
        active && "bg-raised text-fg border-line",
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}

/* ------------------------------------------------------------------- Badge */

export type Tone = "neutral" | "ok" | "warn" | "danger" | "accent" | "xml" | "violet";

const TONES: Record<Tone, string> = {
  neutral: "bg-raised text-muted border-line",
  ok: "bg-ok-soft text-ok border-[#1e4032]",
  warn: "bg-warn-soft text-warn border-[#40301a]",
  danger: "bg-danger-soft text-danger border-[#43242a]",
  accent: "bg-accent-soft text-accent border-[#22405c]",
  xml: "bg-xml-soft text-xml border-[#40311a]",
  violet: "bg-violet-soft text-violet border-[#2f2a45]",
};

export function Badge({
  tone = "neutral",
  children,
  className,
  icon,
  mono,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  icon?: IconName;
  mono?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[10.5px] leading-[15px] font-medium tracking-wide",
        mono && "font-mono",
        TONES[tone],
        className,
      )}
    >
      {icon && <Icon name={icon} size={10} strokeWidth={1.8} />}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------- Modal */

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  icon,
  children,
  footer,
  width = "max-w-lg",
  level = "default",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: IconName;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
  /** default = layer 4/5 · critical = layer 6 (confirmations above an open modal) */
  level?: "default" | "critical";
}) {
  const overlay = useOverlay();
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement as HTMLElement | null;
    overlay.beginModal(onClose);
    const root = dialogRef.current;
    const nodes = root ? Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
    const preferred = root?.querySelector<HTMLElement>("[data-autofocus]") ?? nodes[0];
    const t = window.setTimeout(() => preferred?.focus(), 20);

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !root) return;
      const list = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => !el.hasAttribute("disabled") && el.tabIndex !== -1,
      );
      if (list.length === 0) {
        e.preventDefault();
        return;
      }
      const first = list[0]!;
      const last = list[list.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      overlay.endModal();
      lastFocus.current?.focus?.();
    };
  }, [open, onClose, overlay]);

  if (!open) return null;

  const nested = level === "critical";

  return createPortal(
    <div
      className={cn(
        "fixed inset-0 flex items-start justify-center overflow-y-auto p-4 pt-[8vh]",
        nested ? "z-layer-modal-nested" : "z-layer-modal-overlay",
      )}
    >
      <div
        className="anim-fade absolute inset-0 bg-black/65 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "anim-pop relative w-full rounded-xl border border-line bg-panel shadow-[0_24px_70px_-15px_rgba(0,0,0,0.85)]",
          nested ? "z-layer-modal-nested" : "z-layer-modal",
          width,
        )}
      >
        <div className="flex items-start gap-3 border-b border-line px-5 py-3.5">
          {icon && (
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-accent">
              <Icon name={icon} size={15} />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-[14px] font-semibold tracking-tight text-fg">
              {title}
            </h2>
            {subtitle && <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{subtitle}</p>}
          </div>
          <IconButton icon="x" label="Close" onClick={onClose} />
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/* ------------------------------------------------------------------- Toast */

type ToastKind = "success" | "error" | "warn" | "info";
type ToastItem = { id: number; kind: ToastKind; title: string; detail?: string };

const ToastCtx = createContext<(t: Omit<ToastItem, "id">) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

const TOAST_ICON: Record<ToastKind, IconName> = {
  success: "checkCircle",
  error: "xCircle",
  warn: "alert",
  info: "info",
};
const TOAST_COLOR: Record<ToastKind, string> = {
  success: "text-ok",
  error: "text-danger",
  warn: "text-warn",
  info: "text-accent",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(1);

  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = idRef.current++;
    setItems((s) => [...s, { ...t, id }]);
    setTimeout(() => setItems((s) => s.filter((i) => i.id !== id)), 4200);
  }, []);

  return (
    <ToastCtx.Provider value={push}>
      {children}
      {createPortal(
      <div className="pointer-events-none fixed bottom-4 right-4 z-layer-toast flex w-[340px] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className="anim-up pointer-events-auto flex items-start gap-2.5 rounded-lg border border-line bg-panel/95 px-3 py-2.5 shadow-[0_10px_30px_-8px_rgba(0,0,0,0.9)] backdrop-blur"
          >
            <Icon name={TOAST_ICON[t.kind]} size={15} className={cn("mt-px shrink-0", TOAST_COLOR[t.kind])} />
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-medium text-fg">{t.title}</p>
              {t.detail && <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">{t.detail}</p>}
            </div>
            <button
              className="text-dim transition-colors hover:text-fg"
              onClick={() => setItems((s) => s.filter((i) => i.id !== t.id))}
              aria-label="Dismiss"
            >
              <Icon name="x" size={12} />
            </button>
          </div>
        ))}
      </div>,
      document.body,
      )}
    </ToastCtx.Provider>
  );
}

/* -------------------------------------------------------------------- Tabs */

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  size = "md",
}: {
  tabs: { id: T; label: string; icon?: IconName; count?: number }[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="flex items-center gap-0.5 border-b border-line">
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={cn(
              "relative -mb-px inline-flex items-center gap-1.5 border-b-2 px-3 transition-colors",
              size === "sm" ? "h-8 text-[12px]" : "h-9.5 text-[12.5px]",
              active
                ? "border-accent text-fg"
                : "border-transparent text-muted hover:border-line hover:text-fg/80",
            )}
          >
            {t.icon && <Icon name={t.icon} size={13} />}
            {t.label}
            {t.count !== undefined && (
              <span
                className={cn(
                  "ml-0.5 rounded px-1 font-mono text-[10px]",
                  active ? "bg-accent-soft text-accent" : "bg-raised text-dim",
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- Dropdown */

export function Dropdown({
  trigger,
  children,
  align = "left",
  width = "w-56",
}: {
  trigger: (o: { open: boolean; toggle: () => void }) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  width?: string;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const overlay = useOverlay();

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => overlay.subscribePopovers(close), [overlay, close]);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const r = triggerRef.current?.getBoundingClientRect();
      const menu = menuRef.current;
      if (!r) return;
      const w = menu?.offsetWidth ?? 224;
      const h = menu?.offsetHeight ?? 0;
      let left = align === "right" ? r.right - w : r.left;
      left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
      let top = r.bottom + 6;
      if (top + h > window.innerHeight - 8 && r.top - h - 6 > 8) top = r.top - h - 6;
      setPos({ top, left });
    };
    place();
    const raf = requestAnimationFrame(place);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, align]);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", h);
    document.addEventListener("keydown", k);
    return () => {
      document.removeEventListener("mousedown", h);
      document.removeEventListener("keydown", k);
    };
  }, [open]);

  return (
    <div ref={triggerRef} className="relative">
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open &&
        createPortal(
          <div
            ref={menuRef}
            className={cn(
              "anim-pop z-layer-dropdown overflow-hidden rounded-lg border border-line bg-panel p-1 shadow-[0_18px_45px_-12px_rgba(0,0,0,0.9)]",
              width,
            )}
            style={{ position: "fixed", top: pos.top, left: pos.left }}
          >
            {children(close)}
          </div>,
          document.body,
        )}
    </div>
  );
}

export function MenuItem({
  icon,
  children,
  onClick,
  danger,
  trailing,
  disabled,
}: {
  icon?: IconName;
  children: ReactNode;
  onClick?: () => void;
  danger?: boolean;
  trailing?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[12.5px] transition-colors disabled:opacity-40",
        danger ? "text-danger hover:bg-danger-soft" : "text-fg/85 hover:bg-raised hover:text-fg",
      )}
    >
      {icon && <Icon name={icon} size={14} className="shrink-0 opacity-80" />}
      <span className="flex-1 truncate">{children}</span>
      {trailing && <span className="text-[11px] text-dim">{trailing}</span>}
    </button>
  );
}

export function MenuLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.09em] text-dim",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function MenuSep() {
  return <div className="my-1 h-px bg-line" />;
}

/* ------------------------------------------------------------------- Inputs */

export function Input({
  className,
  icon,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { icon?: IconName }) {
  return (
    <div className="relative flex items-center">
      {icon && <Icon name={icon} size={13} className="pointer-events-none absolute left-2.5 text-dim" />}
      <input
        className={cn(
          "h-7.5 w-full rounded-md border border-line bg-surface px-2.5 text-[12.5px] text-fg placeholder:text-dim",
          "transition-colors focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/25",
          icon && "pl-7.5",
          className,
        )}
        {...rest}
      />
    </div>
  );
}

export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-md border border-line bg-surface px-2.5 py-2 text-[12.5px] text-fg placeholder:text-dim",
        "transition-colors focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/25",
        className,
      )}
      {...rest}
    />
  );
}

export function Select({
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative flex items-center">
      <select
        className={cn(
          "h-7.5 appearance-none rounded-md border border-line bg-surface pl-2.5 pr-7 text-[12.5px] text-fg",
          "transition-colors focus:border-accent/60 focus:outline-none focus:ring-1 focus:ring-accent/25",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <Icon name="chevronDown" size={12} className="pointer-events-none absolute right-2 text-dim" />
    </div>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  description?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between gap-4 text-left"
    >
      <span className="min-w-0">
        {label && <span className="block text-[13px] text-fg">{label}</span>}
        {description && <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted">{description}</span>}
      </span>
      <span
        className={cn(
          "relative h-4.5 w-8 shrink-0 rounded-full border transition-colors",
          checked ? "border-accent/50 bg-accent/80" : "border-line bg-raised",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-3 w-3 rounded-full transition-all",
            checked ? "left-4 bg-[#08131e]" : "left-0.5 bg-dim",
          )}
        />
      </span>
    </button>
  );
}

export function Checkbox({
  checked,
  onChange,
  partial,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  partial?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 text-[12.5px] text-muted hover:text-fg"
      aria-label={label}
    >
      <span
        className={cn(
          "flex h-3.5 w-3.5 items-center justify-center rounded-[3px] border transition-colors",
          checked || partial ? "border-accent bg-accent text-[#08131e]" : "border-[#3a3a45] bg-surface",
        )}
      >
        {partial && !checked ? (
          <span className="h-0.5 w-2 bg-current" />
        ) : checked ? (
          <Icon name="check" size={10} strokeWidth={2.4} />
        ) : null}
      </span>
      {label}
    </button>
  );
}

export function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-medium text-muted">
        {label}
        {required && <span className="text-danger">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-relaxed text-dim">{hint}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------- States */

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 py-16 text-center">
      <span className="h-4 w-4 animate-spin rounded-full border-[1.6px] border-accent border-t-transparent" />
      <p className="text-[12.5px] text-muted">{label}</p>
    </div>
  );
}

export function EmptyState({
  icon = "table",
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-dim">
        <Icon name={icon} size={16} />
      </span>
      <p className="mt-1 text-[13px] font-medium text-fg">{title}</p>
      {description && <p className="max-w-sm text-[12px] leading-relaxed text-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Unable to load data",
  description,
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#43242a] bg-danger-soft text-danger">
        <Icon name="alert" size={16} />
      </span>
      <p className="mt-1 text-[13px] font-medium text-fg">{title}</p>
      {description && <p className="max-w-md text-[12px] leading-relaxed text-muted">{description}</p>}
      {onRetry && (
        <Button className="mt-2" icon="refresh" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Layout */

export function Panel({
  children,
  className,
  padding = true,
}: {
  children: ReactNode;
  className?: string;
  padding?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-line bg-surface",
        padding && "p-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-end justify-between gap-4", className)}>
      <div>
        <h2 className="text-[13px] font-semibold tracking-tight text-fg">{title}</h2>
        {description && <p className="mt-0.5 text-[12px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Key({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-line bg-raised px-1.5 py-px font-mono text-[10.5px] text-dim">
      {children}
    </kbd>
  );
}

export function StatusDot({ tone = "ok", pulse }: { tone?: Tone; pulse?: boolean }) {
  const c: Record<Tone, string> = {
    ok: "bg-ok",
    warn: "bg-warn",
    danger: "bg-danger",
    accent: "bg-accent",
    neutral: "bg-dim",
    xml: "bg-xml",
    violet: "bg-violet",
  };
  return (
    <span className="relative inline-flex h-1.5 w-1.5">
      {pulse && <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", c[tone])} />}
      <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", c[tone])} />
    </span>
  );
}

export function Code({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cn("font-mono text-[11.5px] text-accent", className)}>{children}</code>;
}

export function useDisclosure(initial = false) {
  const [open, setOpen] = useState(initial);
  const onOpen = useCallback(() => setOpen(true), []);
  const onClose = useCallback(() => setOpen(false), []);
  return useMemo(() => ({ open, onOpen, onClose, setOpen }), [open, onOpen, onClose]);
}
