import { useState } from "react";
import { Icon, type IconName } from "../components/Icon";
import { Badge, Button, Panel, SectionHeader, StatusDot } from "../components/ui";
import { cn } from "../utils/cn";
import { useStore } from "../store";
import { CreateDatabaseModal } from "../components/modals";
import { historyService } from "../api/history";

const ACT_ICON: Record<string, IconName> = {
  create: "plus",
  edit: "pencil",
  import: "upload",
  export: "download",
  sql: "terminal",
  lock: "lock",
  user: "users",
};

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Bonjour";
  if (h < 18) return "Bon après-midi";
  return "Bonsoir";
}

export function Overview() {
  const { dbs, go, session, setActiveDb, serverHealth, tcpStatus, favDbs, favTables, toggleFavDb, toggleFavTable } = useStore();
  const [createOpen, setCreateOpen] = useState(false);
  const [activity, setActivity] = useState<any[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);

  const loadActivity = async () => {
    setLoadingActivity(true);
    try {
      const data = await historyService.list(8, 0);
      setActivity(data);
    } catch {
      setActivity([]);
    } finally {
      setLoadingActivity(false);
    }
  };

  // Charger activité au montage
  useState(() => {
    loadActivity();
  });

  const totalTables = dbs.reduce((a, d) => a + (d.tables_count || 0), 0);

  return (
    <div className="anim-fade mx-auto w-full max-w-[1400px] px-6 py-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-fg">
            {greeting()}, {session.user?.full_name || session.user?.email || "Utilisateur"}
          </h1>
          <p className="mt-1 text-[13px] text-muted">
            {dbs.length} bases locales · {totalTables} tables · moteur XML{" "}
            <span className="text-ok">opérationnel</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button icon="upload" onClick={() => go({ v: "import" })}>
            Importer XML
          </Button>
          <Button variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
            Nouvelle base
          </Button>
        </div>
      </div>

      {/* Favoris */}
      {(favDbs.length > 0 || favTables.length > 0) && (
        <section className="mt-6">
          <SectionHeader title="Favoris" description="Bases et tables épinglées (localStorage)" />
          <div className="mt-2 flex flex-wrap gap-2">
            {favDbs.map(id => {
              const db = dbs.find(d => String(d.id) === id);
              if (!db) return null;
              return (
                <button key={id} onClick={() => { setActiveDb(id); go({ v: "db", db: id, tab: "tables" }); }} className="flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent-soft px-2.5 py-1 text-[12px] text-accent">
                  <span>★</span> {db.name}
                </button>
              );
            })}
            {favTables.map(name => (
              <span key={name} className="flex items-center gap-1 rounded-md border border-line bg-surface px-2 py-1 text-[11px] text-muted">
                ★ {name}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Databases */}
      <section className="mt-7">
        <SectionHeader
          title="Vos bases locales"
          description="Documents XML gérés par le moteur natif"
          actions={
            <Button size="sm" variant="ghost" iconRight="arrowRight" onClick={() => go({ v: "databases" })}>
              Voir tout
            </Button>
          }
        />
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {dbs.slice(0, 6).map((d) => {
            return (
              <button
                key={d.id}
                onClick={() => {
                  setActiveDb(String(d.id));
                  go({ v: "db", db: String(d.id), tab: "tables" });
                }}
                className="group relative overflow-hidden rounded-lg border border-line bg-surface p-4 text-left transition-colors hover:border-[#363641] hover:bg-panel"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border",
                        d.scope === "COMMON"
                          ? "border-violet/30 bg-violet-soft text-violet"
                          : "border-line bg-raised text-accent",
                      )}
                    >
                      <Icon name={d.scope === "COMMON" ? "layers" : "database"} size={14} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[13.5px] font-medium text-fg">{d.name}</p>
                      <p className="truncate text-[11.5px] text-dim">
                        {d.scope === "COMMON" ? "Base commune" : "Base personnelle"} · {d.owner_name || d.creator_name}
                      </p>
                    </div>
                  </div>
                  <Icon
                    name="chevronRight"
                    size={14}
                    className="mt-1 shrink-0 text-dim opacity-0 transition-opacity group-hover:opacity-100"
                  />
                </div>

                <div className="mt-3.5 flex items-center gap-4 text-[11.5px]">
                  <span className="flex items-center gap-1.5 text-muted">
                    <Icon name="table" size={12} className="text-dim" />
                    <span className="font-mono text-fg/90">{d.tables_count || 0}</span> tables
                  </span>
                  <span className="flex items-center gap-1.5 text-muted">
                    <Icon name="clock" size={12} className="text-dim" />
                    <span className="font-mono text-fg/90">v{d.document_version}</span>
                  </span>
                  <span className="flex items-center gap-1.5 text-muted">
                    <Icon name="hdd" size={12} className="text-dim" />
                    <span className="font-mono text-fg/90">{d.status}</span>
                  </span>
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-line-soft pt-2.5">
                  <span className="flex items-center gap-1.5 text-[11px] text-dim">
                    <Icon name="clock" size={11} />
                    {d.updated_at ? new Date(d.updated_at).toLocaleDateString() : "—"}
                  </span>
                  <span className="flex items-center gap-1.5">
                    {d.scope === "COMMON" && <Badge tone="violet">COMMON</Badge>}
                    {d.scope === "PERSONAL" && <Badge tone="neutral">PERSONAL</Badge>}
                  </span>
                </div>
              </button>
            );
          })}
          <button
            onClick={() => setCreateOpen(true)}
            className="flex min-h-[132px] flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-line bg-transparent text-[12.5px] text-dim transition-colors hover:border-accent/40 hover:bg-surface hover:text-muted"
          >
            <Icon name="plus" size={16} />
            Nouvelle base
          </button>
        </div>
      </section>

      {/* Activity + server */}
      <div className="mt-8 grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <Panel padding={false}>
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <SectionHeader title="Activité récente" />
            <Button size="xs" variant="ghost" onClick={() => { loadActivity(); go({ v: "admin", tab: "history" }); }}>
              Historique complet
            </Button>
          </div>
          <ul className="divide-y divide-line-soft">
            {loadingActivity ? (
              <li className="px-4 py-6 text-center text-[12px] text-dim">Chargement...</li>
            ) : activity.length === 0 ? (
              <li className="px-4 py-6 text-center text-[12px] text-dim">Aucune activité récente.</li>
            ) : (
              activity.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-panel/60">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-accent">
                    <Icon name={(ACT_ICON as any)[a.action_type] || "clock"} size={12} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="text-[12.5px] text-fg">{a.action_type} {a.element_type}</span>
                    {a.element_name && <span className="ml-1.5 font-mono text-[11.5px] text-accent">{a.element_name}</span>}
                  </span>
                  <span className="w-24 shrink-0 text-right text-[11px] text-dim">{a.created_at ? new Date(a.created_at).toLocaleDateString() : a.at}</span>
                </li>
              ))
            )}
          </ul>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <div className="flex items-center justify-between">
              <SectionHeader title="État du serveur" />
              <Button size="xs" variant="ghost" iconRight="arrowRight" onClick={() => go({ v: "server" })}>
                Diagnostics
              </Button>
            </div>
            <ul className="mt-3 space-y-2">
              {[
                { label: "REST API", value: serverHealth ? `${serverHealth.service} ${serverHealth.version}` : "localhost:5000", tone: "ok" as const, icon: "wifi" as const },
                { label: "Moteur XML", value: `${dbs.length} bases`, tone: "ok" as const, icon: "cpu" as const },
                { label: "TCP", value: tcpStatus ? `${tcpStatus.host || '0.0.0.0'}:${tcpStatus.port || 3307} ${tcpStatus.running ? 'actif' : 'arrêté'}` : ":3307", tone: "ok" as const, icon: "server" as const },
                { label: "Stockage", value: "XML natif", tone: "ok" as const, icon: "hdd" as const },
              ].map((s) => (
                <li key={s.label} className="flex items-center gap-2.5 rounded-md border border-line-soft bg-panel px-2.5 py-1.5">
                  <Icon name={s.icon} size={13} className="text-dim" />
                  <span className="flex-1 text-[12.5px] text-fg">{s.label}</span>
                  <span className="font-mono text-[11px] text-muted">{s.value}</span>
                  <StatusDot tone={s.tone} />
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-line pt-2.5 text-[11px] text-dim">
              Stockage XML-only · {dbs.length} bases
            </div>
          </Panel>

          <Panel>
            <SectionHeader title="Outils rapides" description="Accès direct aux outils" />
            <div className="mt-3 grid grid-cols-2 gap-2">
              {([
                { label: "Console SQL", icon: "terminal" as const, nav: { v: "sql" } as const },
                { label: "Relations", icon: "relations" as const, nav: { v: "relations" } as const },
                { label: "Éditeur XML", icon: "code" as const, nav: { v: "xml" } as const },
                { label: "Import / Export", icon: "download" as const, nav: { v: "import" } as const },
              ]).map((t) => (
                <button
                  key={t.label}
                  onClick={() => go(t.nav as never)}
                  className="flex items-center gap-2 rounded-md border border-line bg-panel px-2.5 py-2 text-left text-[12.5px] text-muted transition-colors hover:border-[#363641] hover:text-fg"
                >
                  <Icon name={t.icon} size={13} className="text-dim" />
                  {t.label}
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </div>

      <CreateDatabaseModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
