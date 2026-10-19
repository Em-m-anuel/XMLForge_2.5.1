import { Icon } from "../Icon";
import { useStore } from "../../store";

const LABELS: Record<string, string> = {
  tables: "Tables",
  sql: "SQL",
  relations: "Relations",
  xml: "XML",
  share: "Partage",
  data: "Données",
  structure: "Structure",
  permissions: "Permissions",
  users: "Utilisateurs",
  audit: "Audit",
  history: "Historique",
};

export function Breadcrumbs() {
  const { nav, dbs, activeDb, go, tables } = useStore();
  const db = dbs.find((d) => String(d.id) === (nav.v === "db" || nav.v === "table" ? nav.db : activeDb));
  const table = nav.v === "table" ? tables.find(t => String(t.id) === nav.table || t.name === nav.table) : null;

  const parts: { label: string; onClick?: () => void; last?: boolean }[] = [];

  if (nav.v === "overview") parts.push({ label: "Aperçu", last: true });
  else if (nav.v === "databases") parts.push({ label: "Bases de données", last: true });
  else if (nav.v === "db" || nav.v === "table") {
    parts.push({ label: "Bases de données", onClick: () => go({ v: "databases" }) });
    parts.push({
      label: db?.name ?? "—",
      onClick: () => db && go({ v: "db", db: String(db.id), tab: "tables" }),
    });
    if (nav.v === "db") parts.push({ label: LABELS[nav.tab] ?? nav.tab, last: true });
    else {
      parts.push({ label: table?.name || nav.table, onClick: () => go({ ...nav, tab: "data" }) });
      parts.push({ label: LABELS[nav.tab] ?? nav.tab, last: true });
    }
  } else if (nav.v === "admin") {
    parts.push({ label: "Administration" });
    parts.push({ label: LABELS[nav.tab] ?? nav.tab, last: true });
  } else if (nav.v === "server" || nav.v === "logs" || nav.v === "settings") {
    parts.push({ label: "Système" });
    parts.push({ label: nav.v === "server" ? "Serveur" : nav.v === "logs" ? "Journaux" : "Paramètres", last: true });
  } else {
    parts.push({ label: "Outils" });
    parts.push({
      label: nav.v === "sql" ? "Console SQL" : nav.v === "relations" ? "Relations" : nav.v === "xml" ? "XML" : "Import / Export",
      last: true,
    });
  }

  return (
    <nav aria-label="Fil d'Ariane" className="flex min-w-0 items-center gap-1 text-[12.5px]">
      {parts.map((p, i) => (
        <span key={i} className="flex min-w-0 items-center gap-1">
          {i > 0 && <Icon name="chevronRight" size={11} className="shrink-0 text-[#4a4a55]" />}
          {p.last ? (
            <span className="truncate font-medium text-fg">{p.label}</span>
          ) : (
            <button
              onClick={p.onClick}
              className="truncate text-muted transition-colors hover:text-fg disabled:cursor-default"
              disabled={!p.onClick}
            >
              {p.label}
            </button>
          )}
        </span>
      ))}
    </nav>
  );
}
