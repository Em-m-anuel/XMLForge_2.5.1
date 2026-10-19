import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon, type IconName } from "../Icon";
import { cn } from "../../utils/cn";
import { useStore, type Nav } from "../../store";
import { Key, useOverlay } from "../ui";

type Item = { id: string; group: string; label: string; sub?: string; icon: IconName; nav?: Nav; hint?: string };

export function CommandPalette() {
  const { palette, setPalette, dbs, tables, activeDb, go, setActiveDb, isAdmin } = useStore();
  const overlay = useOverlay();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const items = useMemo<Item[]>(() => {
    const list: Item[] = [];
    dbs.forEach((d) => {
      list.push({
        id: `db-${d.id}`,
        group: "Bases de données",
        label: d.name,
        sub: `${d.scope === "COMMON" ? "Commune" : "Personnelle"} · ${d.tables_count || 0} tables · v${d.document_version}`,
        icon: "database",
        nav: { v: "db", db: String(d.id), tab: "tables" },
      });
    });
    // Tables de la base active (évite N+1)
    tables.forEach((t) =>
      list.push({
        id: `t-${t.id}`,
        group: `${dbs.find(db => String(db.id) === String(activeDb))?.name || "Base"} · Tables`,
        label: t.name,
        sub: `${t.columns_count || 0} colonnes${t.is_protected ? " · protégée" : ""} · ${t.status}`,
        icon: "table",
        nav: { v: "table", db: String(activeDb), table: String(t.id), tab: "data" },
      }),
    );
    list.push(
      { id: "ov", group: "Navigation", label: "Aperçu", icon: "grid", nav: { v: "overview" } },
      { id: "dbs", group: "Navigation", label: "Bases de données", icon: "layers", nav: { v: "databases" } },
      { id: "sql", group: "Outils", label: "Console SQL", sub: "Requêtes avec moteur XML natif", icon: "terminal", nav: { v: "sql" } },
      { id: "rel", group: "Outils", label: "Relations", sub: "Diagramme schéma", icon: "relations", nav: { v: "relations" } },
      { id: "xml", group: "Outils", label: "XML", sub: "Éditeur de documents", icon: "code", nav: { v: "xml" } },
      { id: "imp", group: "Outils", label: "Import / Export", sub: "XML, SQL, projet", icon: "download", nav: { v: "import" } },
      { id: "srv", group: "Système", label: "Serveur", sub: "REST · TCP · Moteur", icon: "server", nav: { v: "server" } },
      { id: "logs", group: "Système", label: "Journaux", icon: "logs", nav: { v: "logs" } },
      { id: "set", group: "Système", label: "Paramètres", icon: "settings", nav: { v: "settings" } },
    );
    if (isAdmin) {
      list.push(
        { id: "usr", group: "Administration", label: "Utilisateurs", icon: "users", nav: { v: "admin", tab: "users" } },
        { id: "aud", group: "Administration", label: "Audit", icon: "history", nav: { v: "admin", tab: "audit" } },
        { id: "hist", group: "Administration", label: "Historique", icon: "clock", nav: { v: "admin", tab: "history" } },
      );
    }
    return list;
  }, [dbs, tables, activeDb, isAdmin]);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items.slice(0, 40);
    return items
      .filter((i) => `${i.label} ${i.sub ?? ""} ${i.group}`.toLowerCase().includes(s))
      .slice(0, 40);
  }, [items, q]);

  useEffect(() => {
    if (palette) {
      overlay.closePopovers();
      setQ("");
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [palette, overlay]);

  useEffect(() => setSel(0), [q]);

  if (!palette) return null;

  const run = (i: Item) => {
    if (i.nav) {
      if ("db" in i.nav) setActiveDb(i.nav.db);
      go(i.nav);
    }
    setPalette(false);
  };

  let lastGroup = "";

  return createPortal(
    <div className="z-layer-palette fixed inset-0 flex items-start justify-center p-4 pt-[12vh]">
      <div className="anim-fade fixed inset-0 bg-black/70 backdrop-blur-[2px]" onClick={() => setPalette(false)} />
      <div className="anim-up relative w-full max-w-[560px] overflow-hidden rounded-xl border border-line bg-panel shadow-[0_30px_80px_-20px_rgba(0,0,0,0.9)]">
        <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
          <Icon name="search" size={15} className="text-dim" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setSel((s) => Math.min(s + 1, results.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSel((s) => Math.max(s - 1, 0));
              } else if (e.key === "Enter" && results[sel]) {
                e.preventDefault();
                run(results[sel]);
              } else if (e.key === "Escape") {
                setPalette(false);
              }
            }}
            placeholder="Rechercher bases, tables, outils..."
            className="flex-1 bg-transparent text-[13.5px] text-fg placeholder:text-dim focus:outline-none"
          />
          <Key>Esc</Key>
        </div>
        <div className="max-h-[46vh] overflow-y-auto p-1.5">
          {results.length === 0 && (
            <p className="px-3 py-8 text-center text-[12.5px] text-dim">Aucun résultat pour "{q}"</p>
          )}
          {results.map((i, idx) => {
            const header = i.group !== lastGroup ? ((lastGroup = i.group), true) : false;
            return (
              <div key={i.id}>
                {header && (
                  <div className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.09em] text-dim">
                    {i.group}
                  </div>
                )}
                <button
                  onMouseEnter={() => setSel(idx)}
                  onClick={() => run(i)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left transition-colors",
                    idx === sel ? "bg-raised" : "hover:bg-surface",
                  )}
                >
                  <Icon
                    name={i.icon}
                    size={14}
                    className={cn("shrink-0", idx === sel ? "text-accent" : "text-dim")}
                  />
                  <span className="flex-1 truncate text-[13px] text-fg">{i.label}</span>
                  {i.sub && <span className="truncate text-[11.5px] text-dim">{i.sub}</span>}
                  {idx === sel && <Icon name="arrowRight" size={12} className="shrink-0 text-dim" />}
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-between border-t border-line px-3.5 py-2 text-[11px] text-dim">
          <span className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Key>↑</Key>
              <Key>↓</Key> naviguer
            </span>
            <span className="flex items-center gap-1">
              <Key>↵</Key> ouvrir
            </span>
          </span>
          <span className="font-mono">{results.length} résultats</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
