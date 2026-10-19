import { useState } from "react";
import { Icon } from "../Icon";
import { cn } from "../../utils/cn";
import { Badge, Dropdown, Key, MenuItem, MenuLabel, MenuSep, StatusDot, useToast } from "../ui";
import { ShutdownModal } from "../ShutdownModal";
import { useStore } from "../../store";
import { Breadcrumbs } from "./Breadcrumbs";

export function TopBar() {
  const { dbs, activeDb, setActiveDb, go, nav, setPalette, session, logout, toggleSidebar, tables, isAdmin } = useStore();
  const toast = useToast();
  const [shutdownOpen, setShutdownOpen] = useState(false);
  const db = dbs.find((d) => String(d.id) === activeDb);

  const mode =
    nav.v === "table"
      ? nav.tab
      : nav.v === "db"
        ? nav.tab
        : nav.v === "sql"
          ? "sql"
          : nav.v === "xml"
            ? "xml"
            : nav.v === "relations"
              ? "relations"
              : null;

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-surface/70 px-3 backdrop-blur">
      <button
        onClick={toggleSidebar}
        title="Toggle sidebar"
        className="flex h-7 w-7 items-center justify-center rounded-md text-dim transition-colors hover:bg-raised hover:text-fg"
      >
        <Icon name="panelLeft" size={15} />
      </button>

      <Breadcrumbs />

      <Dropdown
        width="w-64"
        trigger={({ toggle, open }) => (
          <button
            data-testid="db-selector"
            onClick={toggle}
            className={cn(
              "flex h-7 items-center gap-1.5 rounded-md border border-line bg-raised px-2 text-[12px] transition-colors hover:border-[#363641]",
              open && "border-accent/50",
            )}
          >
            <StatusDot tone={db?.scope === "COMMON" ? "violet" : "accent"} />
            <span className="font-medium text-fg">{db?.name ?? "Aucune base"}</span>
            <Icon name="chevronDown" size={11} className="text-dim" />
          </button>
        )}
      >
        {(close) => (
          <>
            <MenuLabel>Personnelles</MenuLabel>
            {dbs
              .filter((d) => d.scope === "PERSONAL")
              .map((d) => (
                <MenuItem
                  key={d.id}
                  icon="database"
                  onClick={() => {
                    setActiveDb(String(d.id));
                    go({ v: "db", db: String(d.id), tab: "tables" });
                    close();
                  }}
                  trailing={`${d.tables_count || 0} tables`}
                >
                  {d.name}
                </MenuItem>
              ))}
            <MenuLabel>Communes</MenuLabel>
            {dbs
              .filter((d) => d.scope === "COMMON")
              .map((d) => (
                <MenuItem
                  key={d.id}
                  icon="layers"
                  onClick={() => {
                    setActiveDb(String(d.id));
                    go({ v: "db", db: String(d.id), tab: "tables" });
                    close();
                  }}
                  trailing={`${d.tables_count || 0} tables`}
                >
                  {d.name}
                </MenuItem>
              ))}
            <MenuSep />
            <MenuItem
              icon="plus"
              onClick={() => {
                close();
                go({ v: "databases" });
              }}
            >
              Nouvelle base...
            </MenuItem>
          </>
        )}
      </Dropdown>

      {mode && (
        <Badge tone="neutral" mono className="hidden lg:inline-flex">
          mode: {mode}
        </Badge>
      )}

      <div className="flex-1" />

      <button
        data-testid="command-palette-trigger"
        onClick={() => setPalette(true)}
        className="group flex h-7 w-[220px] items-center gap-2 rounded-md border border-line bg-surface px-2.5 text-[12px] text-dim transition-colors hover:border-[#363641] hover:text-muted xl:w-[280px]"
      >
        <Icon name="search" size={13} />
        <span className="flex-1 text-left">Rechercher...</span>
        <Key>⌘K</Key>
      </button>

      <div className="mx-1 hidden h-5 w-px bg-line md:block" />

      <div className="hidden items-center gap-1.5 rounded-md border border-line bg-raised px-2 py-1 md:flex">
        <StatusDot tone="ok" pulse />
        <span className="text-[11.5px] text-muted">Local</span>
        <span className="font-mono text-[10.5px] text-dim">:5000</span>
      </div>

      <Dropdown
        align="right"
        width="w-56"
        trigger={({ toggle }) => (
          <button
            data-testid="user-menu-trigger"
            onClick={toggle}
            className="flex h-7 items-center gap-2 rounded-md border border-transparent pl-1 pr-1.5 transition-colors hover:border-line hover:bg-raised"
          >
            <span className="flex h-5.5 w-5.5 items-center justify-center rounded-[5px] border border-[#2f3b48] bg-[#101820] text-[10px] font-semibold text-accent">
              {session.user?.initials || "??"}
            </span>
            <span className="hidden text-[12px] text-fg lg:inline\">{session.user?.full_name || session.user?.email}</span>
            <Icon name="chevronDown" size={11} className="text-dim" />
          </button>
        )}
      >
        {(close) => (
          <>
            <div className="px-2.5 py-2">
              <p className="text-[12.5px] font-medium text-fg\">{session.user?.full_name || "Utilisateur"}</p>
              <p className="text-[11.5px] text-dim\">{session.user?.email}</p>
              <div className="mt-1.5">
                <Badge tone={session.user?.is_admin ? "violet" : "neutral"} icon="shield">
                  {session.user?.is_admin ? "Admin" : session.user?.role || "User"}
                </Badge>
              </div>
            </div>
            <MenuSep />
            <MenuItem icon="settings" onClick={() => { close(); go({ v: "settings" }); }}>
              Paramètres
            </MenuItem>
            <MenuItem icon="server" onClick={() => { close(); go({ v: "server" }); }}>
              Serveur
            </MenuItem>
            <MenuSep />
            <MenuItem icon="logout" danger onClick={() => { close(); logout(); }}>
              Déconnexion
            </MenuItem>
            {isAdmin && (
              <>
                <MenuSep />
                <MenuItem icon="power" onClick={() => { close(); setShutdownOpen(true); }}>
                  Fermer XMLForge
                </MenuItem>
              </>
            )}
          </>
        )}
      </Dropdown>
      <ShutdownModal open={shutdownOpen} onClose={() => setShutdownOpen(false)} />
    </header>
  );
}
