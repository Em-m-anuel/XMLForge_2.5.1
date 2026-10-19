import { useState } from "react";
import { Icon, type IconName } from "../Icon";
import { cn } from "../../utils/cn";
import { Badge } from "../ui";
import { useStore } from "../../store";

function Group({
  label,
  children,
  collapsed,
  defaultOpen = true,
  action,
}: {
  label: string;
  children: React.ReactNode;
  collapsed: boolean;
  defaultOpen?: boolean;
  action?: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (collapsed) {
    return (
      <div className="border-t border-line-soft py-2">
        <div className="flex flex-col items-center gap-1">{children}</div>
      </div>
    );
  }
  return (
    <div className="px-2 py-2">
      <div className="group flex items-center justify-between px-2 pb-1 pt-1.5">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-dim transition-colors hover:text-muted"
        >
          <Icon
            name="chevronDown"
            size={10}
            strokeWidth={2}
            className={cn("transition-transform duration-150", !open && "-rotate-90")}
          />
          {label}
        </button>
        {action && <span className="opacity-0 transition-opacity group-hover:opacity-100">{action}</span>}
      </div>
      {open && <div className="mt-0.5 flex flex-col gap-px">{children}</div>}
    </div>
  );
}

function Item({
  icon,
  label,
  active,
  onClick,
  collapsed,
  trailing,
  depth = 0,
  dot,
}: {
  icon?: IconName;
  label: string;
  active?: boolean;
  onClick?: () => void;
  collapsed: boolean;
  trailing?: string;
  depth?: number;
  dot?: "personal" | "common";
}) {
  const el = (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={cn(
        "group relative flex h-7 w-full items-center gap-2 rounded-md text-[12.5px] transition-colors",
        collapsed ? "justify-center px-0" : "px-2",
        depth === 1 && !collapsed && "pl-7",
        active ? "bg-raised text-fg" : "text-muted hover:bg-surface hover:text-fg",
      )}
    >
      {active && !collapsed && <span className="absolute left-0 top-1.5 h-4 w-[2px] rounded-r bg-accent" />}
      {icon && <Icon name={icon} size={14} className={cn("shrink-0", active ? "text-accent" : "text-dim group-hover:text-muted")} />}
      {!collapsed && (
        <>
          {dot && (
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                dot === "common" ? "bg-violet" : "bg-accent",
              )}
            />
          )}
          <span className="flex-1 truncate text-left">{label}</span>
          {trailing && <span className="font-mono text-[10.5px] text-dim">{trailing}</span>}
        </>
      )}
    </button>
  );
  return collapsed ? <div className="flex justify-center">{el}</div> : el;
}

export function Sidebar() {
  const { nav, go, dbs, sidebar, toggleSidebar, activeDb, setActiveDb, isAdmin } = useStore();
  const c = sidebar;

  const personal = dbs.filter((d) => (d.scope || "").toLowerCase() === "personal");
  const common = dbs.filter((d) => (d.scope || "").toLowerCase() === "common");

  const openDb = (id: string, tab: "tables" | "sql" | "relations" | "xml" | "share") => {
    setActiveDb(id);
    go({ v: "db", db: id, tab });
  };

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-200",
        c ? "w-[54px]" : "w-[228px]",
      )}
    >
      <div className={cn("flex h-12 items-center border-b border-line", c ? "justify-center px-0" : "px-3")}>
        <button
          onClick={toggleSidebar}
          className="flex items-center gap-2 text-left"
          title={c ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-[6px] border border-[#2f3b48] bg-[#101820] text-accent">
            <Icon name="braces" size={13} strokeWidth={1.8} />
          </span>
          {!c && (
            <span className="text-[13.5px] font-semibold tracking-tight text-fg">
              XML<span className="text-muted">Forge</span>
            </span>
          )}
        </button>
        {!c && (
          <span className="ml-auto rounded border border-line bg-raised px-1.5 py-px font-mono text-[9.5px] text-dim">
            v2.0
          </span>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto no-scrollbar pb-4">
        <Group label="Workspace" collapsed={c}>
          <Item
            icon="grid"
            label="Aperçu"
            collapsed={c}
            active={nav.v === "overview"}
            onClick={() => go({ v: "overview" })}
          />
          <Item
            icon="database"
            label="Bases de données"
            collapsed={c}
            active={nav.v === "databases"}
            onClick={() => go({ v: "databases" })}
            trailing={String(dbs.length)}
          />
        </Group>

        <div className="border-t border-line-soft" />
        <Group label="Bases de données" collapsed={c}>
          {!c && (
            <div className="px-2 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-dim">
              Personnelles
            </div>
          )}
          {personal.map((d) => (
            <Item
              key={d.id}
              label={d.name}
              active={(nav.v === "db" && nav.db === String(d.id)) || (nav.v === "table" && nav.db === String(d.id)) || (String(activeDb) === String(d.id) && ["sql", "relations", "xml", "import"].includes(nav.v))}
              collapsed={c}
              dot="personal"
              onClick={() => openDb(String(d.id), "tables")}
              trailing={String(d.tables_count || 0)}
            />
          ))}
          {!c && (
            <div className="mt-2 px-2 pb-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-dim">
              Communes
            </div>
          )}
          {common.map((d) => (
            <Item
              key={d.id}
              label={d.name}
              active={(nav.v === "db" && nav.db === String(d.id)) || (nav.v === "table" && nav.db === String(d.id))}
              collapsed={c}
              dot="common"
              onClick={() => openDb(String(d.id), "tables")}
              trailing={String(d.tables_count || 0)}
            />
          ))}
        </Group>

        <div className="border-t border-line-soft" />
        <Group label="Outils" collapsed={c}>
          <Item
            icon="terminal"
            label="Console SQL"
            collapsed={c}
            active={nav.v === "sql"}
            onClick={() => go({ v: "sql" })}
          />
          <Item
            icon="relations"
            label="Relations"
            collapsed={c}
            active={nav.v === "relations"}
            onClick={() => go({ v: "relations" })}
          />
          <Item icon="code" label="XML" collapsed={c} active={nav.v === "xml"} onClick={() => go({ v: "xml" })} />
          <Item
            icon="download"
            label="Import / Export"
            collapsed={c}
            active={nav.v === "import"}
            onClick={() => go({ v: "import" })}
          />
        </Group>

        {isAdmin && (
          <>
            <div className="border-t border-line-soft" />
            <Group label="Administration" collapsed={c}>
              <Item
                icon="users"
                label="Utilisateurs"
                collapsed={c}
                active={nav.v === "admin" && nav.tab === "users"}
                onClick={() => go({ v: "admin", tab: "users" })}
              />
              <Item
                icon="history"
                label="Audit"
                collapsed={c}
                active={nav.v === "admin" && nav.tab === "audit"}
                onClick={() => go({ v: "admin", tab: "audit" })}
              />
              <Item
                icon="clock"
                label="Historique"
                collapsed={c}
                active={nav.v === "admin" && nav.tab === "history"}
                onClick={() => go({ v: "admin", tab: "history" })}
              />
            </Group>
          </>
        )}

        <div className="border-t border-line-soft" />
        <Group label="Système" collapsed={c}>
          <Item
            icon="server"
            label="Serveur"
            collapsed={c}
            active={nav.v === "server"}
            onClick={() => go({ v: "server" })}
          />
          <Item icon="logs" label="Journaux" collapsed={c} active={nav.v === "logs"} onClick={() => go({ v: "logs" })} />
          <Item
            icon="settings"
            label="Paramètres"
            collapsed={c}
            active={nav.v === "settings"}
            onClick={() => go({ v: "settings" })}
          />
        </Group>
      </nav>

      {!c && (
        <div className="border-t border-line p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-dim">Moteur local</span>
            <Badge tone="ok" icon="cpu">
              Opérationnel
            </Badge>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted">
            <Icon name="hdd" size={12} className="text-dim" />
            Stockage XML natif
          </div>
        </div>
      )}
    </aside>
  );
}
