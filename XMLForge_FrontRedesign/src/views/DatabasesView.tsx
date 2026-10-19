import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { Badge, Button, Dropdown, EmptyState, IconButton, Input, MenuItem, Select, useToast } from "../components/ui";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore } from "../store";
import { CreateDatabaseModal, EditDatabaseModal, ShareModal, ConfirmModal } from "../components/modals";
import { xmlService } from "../api/xml";
import type { Database } from "../api/databases";

export function DatabasesView() {
  const { dbs, dbsLoading, dbsError, go, setActiveDb, dropDatabase, canManageDb, fetchDatabases, favDbs, toggleFavDb } = useStore();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "personal" | "common">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [edit, setEdit] = useState<Database | null>(null);
  const [share, setShare] = useState<Database | null>(null);
  const [drop, setDrop] = useState<Database | null>(null);

  const rows = useMemo(
    () =>
      dbs
        .filter((d) => (scope === "all" ? true : d.scope.toLowerCase() === scope))
        .filter((d) => d.name.toLowerCase().includes(q.trim().toLowerCase())),
    [dbs, scope, q],
  );

  if (dbsLoading) {
    return (
      <div className="mx-auto w-full max-w-[1400px] px-6 py-10">
        <div className="flex items-center gap-2 text-[13px] text-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
          Chargement des bases...
        </div>
      </div>
    );
  }

  if (dbsError) {
    return (
      <div className="mx-auto w-full max-w-[1400px] px-6 py-10">
        <div className="rounded-lg border border-danger/30 bg-danger-soft p-4">
          <p className="text-[13px] font-medium text-danger">Impossible de charger les bases.</p>
          <p className="mt-1 text-[12px] text-muted">{dbsError}</p>
          <Button size="sm" className="mt-3" onClick={() => fetchDatabases()}>
            Réessayer
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="anim-fade">
      <PageHeader
        icon="database"
        accent
        title="Bases de données"
        subtitle={
          <>
            <span>{dbs.length} bases locales</span>
            <span className="text-dim">·</span>
            <span>{dbs.reduce((a, d) => a + (d.tables_count || 0), 0)} tables</span>
            <span className="text-dim">·</span>
            <span>Stockage XML natif</span>
          </>
        }
        actions={
          <>
            <Button icon="upload" onClick={() => go({ v: "import" })}>
              Importer XML
            </Button>
            <Button variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
              Nouvelle base
            </Button>
          </>
        }
      />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-64">
            <Input icon="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer les bases..." />
          </div>
          <Select value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}>
            <option value="all">Toutes</option>
            <option value="personal">Personnelles</option>
            <option value="common">Communes</option>
          </Select>
          <div className="flex-1" />
          <span className="text-[11.5px] text-dim">
            {rows.length} résultat{rows.length > 1 ? "s" : ""}
          </span>
        </div>

        <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
          <div className="grid grid-cols-[1.6fr_90px_120px_170px_60px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
            <span>Nom</span>
            <span className="text-right">Tables</span>
            <span>Propriétaire</span>
            <span>Mise à jour</span>
            <span />
          </div>
          {rows.length === 0 && (
            <EmptyState
              icon="database"
              title={q ? "Aucune base ne correspond" : "Aucune base"}
              description={q ? `Aucun résultat pour "${q}".` : "Créez une base pour commencer à travailler avec le moteur XML."}
              action={
                q ? (
                  <Button size="sm" onClick={() => setQ("")}>
                    Effacer filtre
                  </Button>
                ) : (
                  <Button size="sm" variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
                    Nouvelle base
                  </Button>
                )
              }
            />
          )}
          {rows.map((d) => {
            return (
              <div
                key={d.id}
                onClick={() => {
                  setActiveDb(String(d.id));
                  go({ v: "db", db: String(d.id), tab: "tables" });
                }}
                className="grid cursor-pointer grid-cols-[1.6fr_90px_120px_170px_60px] items-center gap-3 border-b border-line-soft px-4 py-2.5 transition-colors last:border-0 hover:bg-panel"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <span
                    className={
                      d.scope === "COMMON"
                        ? "flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-violet/30 bg-violet-soft text-violet"
                        : "flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-accent"
                    }
                  >
                    <Icon name={d.scope === "COMMON" ? "layers" : "database"} size={13} />
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-[13px] font-medium text-fg">{d.name}</span>
                      {d.scope === "COMMON" ? (
                        <Badge tone="violet">COMMON</Badge>
                      ) : (
                        <Badge tone="neutral">PERSONAL</Badge>
                      )}
                      {d.status === 'ARCHIVED' && <Badge tone="neutral">ARCHIVÉ</Badge>}
                    </span>
                    <span className="mt-0.5 block truncate text-[11.5px] text-dim">{d.description || "Aucune description"}</span>
                  </span>
                </div>
                <span className="text-right font-mono text-[12px] text-fg/90">{d.tables_count || 0}</span>
                <span className="truncate text-[12px] text-muted">{d.owner_name || d.creator_name || "—"}</span>
                <span className="font-mono text-[11.5px] text-dim">{d.updated_at ? new Date(d.updated_at).toLocaleDateString() : "—"}</span>
                <div className="flex justify-end gap-0.5" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => toggleFavDb(String(d.id))} className={`text-[14px] ${favDbs.includes(String(d.id)) ? "text-accent" : "text-dim"}`}>
                    {favDbs.includes(String(d.id)) ? "★" : "☆"}
                  </button>
                  {canManageDb(d) && (
                    <IconButton icon="pencil" label="Modifier la base" onClick={() => setEdit(d)} />
                  )}
                  <IconButton
                    icon="share"
                    label="Partage"
                    onClick={() => setShare(d)}
                  />
                  <Dropdown
                    align="right"
                    width="w-52"
                    trigger={({ toggle }) => <IconButton icon="more" label="Plus" onClick={toggle} />}
                  >
                    {(close) => (
                      <>
                        {canManageDb(d) && (
                          <MenuItem
                            icon="pencil"
                            onClick={() => {
                              close();
                              setEdit(d);
                            }}
                          >
                            Modifier la base
                          </MenuItem>
                        )}
                        <MenuItem
                          icon="terminal"
                          onClick={() => {
                            close();
                            setActiveDb(String(d.id));
                            go({ v: "db", db: String(d.id), tab: "sql" });
                          }}
                        >
                          Console SQL
                        </MenuItem>
                        <MenuItem
                          icon="code"
                          onClick={() => {
                            close();
                            setActiveDb(String(d.id));
                            go({ v: "db", db: String(d.id), tab: "xml" });
                          }}
                        >
                          Voir XML
                        </MenuItem>
                        <MenuItem
                          icon="download"
                          onClick={async () => {
                            close();
                            try {
                              await xmlService.exportDatabaseXml(d.id);
                              toast({ kind: "success", title: "Export XML", detail: `${d.name}.xml` });
                            } catch (e: any) {
                              toast({ kind: "error", title: "Erreur export", detail: e.message });
                            }
                          }}
                        >
                          Exporter XML
                        </MenuItem>
                        <MenuItem icon="trash" danger onClick={() => { close(); setDrop(d); }}>
                          Supprimer
                        </MenuItem>
                      </>
                    )}
                  </Dropdown>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <CreateDatabaseModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <EditDatabaseModal open={!!edit} onClose={() => setEdit(null)} dbId={edit ? String(edit.id) : ""} />
      <ShareModal open={!!share} onClose={() => setShare(null)} dbId={share ? String(share.id) : ""} />
      <ConfirmModal
        open={!!drop}
        onClose={() => setDrop(null)}
        title="Supprimer la base"
        description={`Supprimer ${drop?.name} et son document XML du stockage ?`}
        confirmLabel="Supprimer"
        danger
        onConfirm={() => drop && dropDatabase(String(drop.id))}
      />
    </div>
  );
}
