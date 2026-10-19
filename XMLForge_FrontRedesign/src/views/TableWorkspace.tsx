import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Dropdown,
  EmptyState,
  MenuItem,
  MenuSep,
  Panel,
  SectionHeader,
  Switch,
  Tabs,
  useToast,
} from "../components/ui";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore, type TableTab } from "../store";
import { ConfirmModal, CreateTableModal, UnlockTableModal } from "../components/modals";
import { DataTab } from "./table/DataTab";
import { StructureTab } from "./table/StructureTab";
import { RelationDiagram } from "./RelationDiagram";
import { SqlConsole } from "./SqlConsole";
import { XmlPanel } from "./XmlPanel";
import { xmlService } from "../api/xml";
import { permissionService } from "../api/permissions";

export function TableWorkspace({
  dbId,
  table: tableParam,
  tab,
}: {
  dbId: string;
  table: string;
  tab: TableTab;
}) {
  const { dbs, tables, tablesError, columns, columnsError, rows, rowsTotal, rowsError, go, dropTable, duplicateTable, truncateTable, setProtected, fetchTables, fetchColumns, fetchRows, fetchXml, xmlDoc, xmlLoading, xmlError, applyXml } = useStore();
  const toast = useToast();
  const db = dbs.find((d) => String(d.id) === dbId);
  const table = tables.find((t) => String(t.id) === tableParam || t.name === tableParam);
  const [unlockOpen, setUnlockOpen] = useState(false);
  const [dropOpen, setDropOpen] = useState(false);
  const [truncateOpen, setTruncateOpen] = useState(false);
  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [perms, setPerms] = useState<any[]>([]);
  const [permsLoading, setPermsLoading] = useState(false);

  useEffect(() => {
    if (table?.id) {
      fetchColumns(table.id);
      fetchRows(table.id, { limit: 25, offset: 0 });
      fetchXml(table.id);
    }
  }, [table?.id, fetchColumns, fetchRows, fetchXml]);

  useEffect(() => {
    if (tab === 'permissions' && table?.id) {
      setPermsLoading(true);
      permissionService.listTable(String(table.id)).then(setPerms).catch(() => setPerms([])).finally(() => setPermsLoading(false));
    }
  }, [tab, table?.id]);

  if (tablesError) {
    return (
      <div className="px-6 py-10">
        <div className="rounded-lg border border-danger/30 bg-danger-soft p-6 text-center">
          <p className="text-[14px] font-medium text-danger">Impossible de charger les tables.</p>
          <p className="mt-1 text-[12px] text-muted">{tablesError}</p>
          <div className="mt-4 flex justify-center gap-2">
            <Button size="sm" onClick={() => go({ v: "db", db: dbId, tab: "tables" })}>Retour aux tables</Button>
            <Button size="sm" variant="primary" onClick={() => fetchTables(dbId)}>Actualiser</Button>
          </div>
        </div>
      </div>
    );
  }

  if (!db || !table) {
    return (
      <div className="px-6 py-10">
        <EmptyState
          icon="table"
          title="Table introuvable"
          description="Cette table n'existe plus dans le document XML de la base ou vous n'avez pas les permissions."
          action={
            <Button size="sm" onClick={() => go({ v: "db", db: dbId, tab: "tables" })}>
              Retour à la base
            </Button>
          }
        />
      </div>
    );
  }

  if (columnsError || rowsError || xmlError) {
    const errMsg = columnsError || rowsError || xmlError;
    return (
      <div className="px-6 py-10">
        <div className="rounded-lg border border-danger/30 bg-danger-soft p-6">
          <p className="text-[14px] font-medium text-danger">Impossible d'afficher cette table</p>
          <p className="mt-1 text-[12px] text-muted">La table n'a pas pu être chargée : {errMsg}</p>
          <div className="mt-4 flex gap-2">
            <Button size="sm" onClick={() => { if (table?.id) { fetchColumns(table.id); fetchRows(table.id, { limit: 25, offset: 0 }); fetchXml(table.id); } }}>Réessayer</Button>
            <Button size="sm" variant="ghost" onClick={() => go({ v: "db", db: dbId, tab: "tables" })}>Retour aux tables</Button>
          </div>
        </div>
      </div>
    );
  }

  const fkCount = columns.filter((c) => c.foreign_key).length;

  return (
    <div className="anim-fade">
      <PageHeader
        icon="table"
        accent
        title={table.name}
        badges={
          <>
            {table.is_protected ? (
              <Badge tone="warn" icon="lock">
                Protégée
              </Badge>
            ) : (
              <Badge tone="ok" icon="unlock">
                Modifiable
              </Badge>
            )}
            {fkCount > 0 && (
              <Badge tone="accent" icon="link">
                {fkCount} FK
              </Badge>
            )}
            {table.status === 'ARCHIVED' && <Badge tone="neutral">Archivée</Badge>}
          </>
        }
        subtitle={
          <>
            <button onClick={() => go({ v: "db", db: dbId, tab: "tables" })} className="text-accent transition-colors hover:underline">
              {db.name}
            </button>
            <span className="text-dim">/</span>
            <span className="font-mono">{table.name}</span>
            {table.description && (
              <>
                <span className="text-dim">·</span>
                <span>{table.description}</span>
              </>
            )}
          </>
        }
        meta={[
          { label: "Colonnes", value: columns.length || table.columns_count, icon: "columns" },
          { label: "Lignes", value: rowsTotal.toLocaleString(), icon: "rows" },
          { label: "Moteur", value: "XMLForge", icon: "cpu" },
          { label: "Mise à jour", value: table.updated_at ? new Date(table.updated_at).toLocaleDateString() : "—", icon: "clock" },
        ]}
        actions={
          <>
            <Button
              icon="plus"
              variant="primary"
              onClick={() => {
                if (table.is_protected) {
                  toast({ kind: "error", title: "Table protégée", detail: "Déverrouillez la table pour insérer des lignes" });
                  return;
                }
                go({ v: "table", db: dbId, table: String(table.id), tab: "data" });
                setTimeout(() => window.dispatchEvent(new CustomEvent("xf-new-row")), 60);
              }}
            >
              Ajouter ligne
            </Button>
            <Button icon="columns" onClick={() => go({ v: "table", db: dbId, table: String(table.id), tab: "structure" })}>
              Ajouter colonne
            </Button>
            <Button icon="upload" onClick={() => go({ v: "import" })}>
              Importer
            </Button>
            <Button icon="download" onClick={async () => {
              try {
                await xmlService.exportTableXml(table.id);
                toast({ kind: "success", title: "Export XML", detail: `${table.name}.xml` });
              } catch (e: any) {
                toast({ kind: "error", title: "Erreur export", detail: e.message });
              }
            }}>
              Exporter
            </Button>
            <Dropdown
              align="right"
              width="w-56"
              trigger={({ toggle }) => (
                <Button icon="more" onClick={toggle} aria-label="Plus" />
              )}
            >
              {(close) => (
                <>
                  <MenuItem
                    icon={table.is_protected ? "unlock" : "lock"}
                    onClick={() => {
                      close();
                      if (table.is_protected) setUnlockOpen(true);
                      else setProtected(dbId, table.id, true);
                    }}
                  >
                    {table.is_protected ? "Déverrouiller" : "Protéger"}
                  </MenuItem>
                  <MenuItem
                    icon="copy"
                    onClick={() => {
                      close();
                      setDuplicateName(`${table.name}_copie`);
                      setDuplicateOpen(true);
                    }}
                  >
                    Dupliquer structure
                  </MenuItem>
                  <MenuItem
                    icon="trash"
                    onClick={() => {
                      close();
                      setTruncateOpen(true);
                    }}
                  >
                    Vider la table (TRUNCATE)
                  </MenuItem>
                  <MenuSep />
                  <MenuItem
                    icon="trash"
                    danger
                    onClick={() => {
                      close();
                      setDropOpen(true);
                    }}
                  >
                    Supprimer table
                  </MenuItem>
                </>
              )}
            </Dropdown>
          </>
        }
        tabs={
          <Tabs
            tabs={[
              { id: "data" as const, label: "Données", icon: "rows", count: rowsTotal },
              { id: "structure" as const, label: "Structure", icon: "columns", count: columns.length || table.columns_count },
              { id: "relations" as const, label: "Relations", icon: "relations", count: fkCount },
              { id: "sql" as const, label: "SQL", icon: "terminal" },
              { id: "xml" as const, label: "XML", icon: "code" },
              { id: "permissions" as const, label: "Permissions", icon: "shield" },
            ]}
            value={tab}
            onChange={(t) => go({ v: "table", db: dbId, table: String(table.id), tab: t })}
          />
        }
      />

      {table.is_protected && (
        <div className="flex flex-wrap items-center gap-3 border-b border-warn/25 bg-warn-soft/40 px-6 py-2">
          <Icon name="lock" size={13} className="text-warn" />
          <span className="text-[12px] text-warn">
            <span className="font-medium">{table.name}</span> est protégée — lecture disponible, écriture nécessite déverrouillage.
          </span>
          <div className="flex-1" />
          <Button size="xs" variant="default" icon="unlock" onClick={() => setUnlockOpen(true)}>
            Déverrouiller
          </Button>
        </div>
      )}

      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        {tab === "data" && (
          <ErrorBoundary name="DataTab">
            <DataTab dbId={dbId} tableId={table.id} />
          </ErrorBoundary>
        )}
        {tab === "structure" && (
          <ErrorBoundary name="StructureTab">
            <StructureTab dbId={dbId} tableId={table.id} />
          </ErrorBoundary>
        )}
        {tab === "relations" && (
          <ErrorBoundary name="RelationDiagram">
            <RelationDiagram dbId={dbId} focusTableId={table.id} />
          </ErrorBoundary>
        )}
        {tab === "sql" && (
          <ErrorBoundary name="SqlConsole">
            <SqlConsole dbId={dbId} initialQuery={`SELECT *\nFROM ${table.name}\nLIMIT 25;`} height="h-40" />
          </ErrorBoundary>
        )}
        {tab === "xml" && (
          <ErrorBoundary name="XmlPanel">
            <XmlPanel
              doc={xmlDoc}
              title={`${table.name}.xml`}
              subtitle={`Extrait de ${db.name}.xml · ${rowsTotal} lignes`}
              height={440}
              loading={xmlLoading}
              onLoad={() => fetchXml(table.id)}
              onApply={(xml) => applyXml(table.id, xml)}
            />
          </ErrorBoundary>
        )}
        {tab === "permissions" && (
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Panel padding={false}>
              <div className="border-b border-line px-4 py-2.5">
                <SectionHeader title="Permissions table" description="Héritées de la base, ajustables par table" />
              </div>
              <div className="overflow-hidden">
                <div className="grid grid-cols-[1fr_110px_70px_70px_80px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
                  <span>Utilisateur</span>
                  <span>Rôle</span>
                  <span className="text-center">View</span>
                  <span className="text-center">Edit</span>
                  <span className="text-center">Manage</span>
                </div>
                {permsLoading ? (
                  <div className="px-4 py-6 text-center text-[12px] text-dim">Chargement...</div>
                ) : perms.length === 0 ? (
                  <div className="px-4 py-6 text-center text-[12px] text-dim">Aucune permission spécifique. Héritage base.</div>
                ) : (
                  perms.map((m) => (
                    <div key={m.id} className="grid grid-cols-[1fr_110px_70px_70px_80px] items-center gap-3 border-b border-line-soft px-4 py-2.5 last:border-0">
                      <span className="flex items-center gap-2.5 text-[12.5px] text-fg">
                        <span className="flex h-6 w-6 items-center justify-center rounded-md border border-line bg-raised text-[9.5px] text-muted">
                          {(m.user_email || `U${m.user_id}`).slice(0, 2).toUpperCase()}
                        </span>
                        {m.user_email || `User #${m.user_id}`}
                      </span>
                      <Badge tone={m.can_admin ? "accent" : m.can_write ? "ok" : "neutral"}>
                        {m.can_admin ? "Manage" : m.can_write ? "Edit" : "View"}
                      </Badge>
                      <span className="flex justify-center">
                        <Icon name="check" size={13} className="text-ok" />
                      </span>
                      <span className="flex justify-center">
                        {m.can_write ? <Icon name="check" size={13} className="text-ok" /> : <Icon name="minus" size={13} className="text-dim" />}
                      </span>
                      <span className="flex justify-center">
                        {m.can_admin ? <Icon name="check" size={13} className="text-ok" /> : <Icon name="minus" size={13} className="text-dim" />}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            <div className="flex flex-col gap-4">
              <Panel>
                <SectionHeader title="Protection" description="Verrouillage en écriture" />
                <div className="mt-3 border-t border-line pt-3">
                  <Switch
                    checked={!!table.is_protected}
                    onChange={(v) => {
                      if (v) setProtected(dbId, table.id, true);
                      else setUnlockOpen(true);
                    }}
                    label="Protégée"
                    description="INSERT / UPDATE / DELETE refusés jusqu'au déverrouillage."
                  />
                </div>
              </Panel>
            </div>
          </div>
        )}
      </div>

      <UnlockTableModal open={unlockOpen} onClose={() => setUnlockOpen(false)} dbId={dbId} tableId={table.id} />
      <ConfirmModal
        open={dropOpen}
        onClose={() => setDropOpen(false)}
        title="Supprimer table"
        description={`Supprimer ${table.name} (${rowsTotal} lignes) du document XML ?`}
        confirmLabel="Supprimer"
        danger
        onConfirm={() => {
          dropTable(dbId, table.id);
          go({ v: "db", db: dbId, tab: "tables" });
        }}
      />
      <ConfirmModal
        open={truncateOpen}
        onClose={() => setTruncateOpen(false)}
        title="Vider la table"
        description={`Vider définitivement toutes les lignes de ${table.name} ? Cette action est irréversible.`}
        confirmLabel="Vider"
        danger
        onConfirm={() => truncateTable(dbId, table.id)}
      />
      <ConfirmModal
        open={duplicateOpen}
        onClose={() => setDuplicateOpen(false)}
        title="Dupliquer structure"
        description={`Dupliquer la structure de ${table.name} vers ${duplicateName} ? Aucune donnée ne sera copiée.`}
        confirmLabel="Dupliquer"
        onConfirm={() => {
          if (duplicateName.trim()) {
            duplicateTable(dbId, table.id, duplicateName.trim());
          }
        }}
      />
      {duplicateOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-surface p-4">
            <h3 className="text-[14px] font-medium text-fg">Dupliquer {table.name}</h3>
            <p className="mt-1 text-[12px] text-muted">Nouveau nom de table (structure uniquement)</p>
            <input
              autoFocus
              value={duplicateName}
              onChange={(e) => setDuplicateName(e.target.value)}
              placeholder={`${table.name}_copie`}
              className="mt-3 w-full rounded-md border border-line bg-raised px-3 py-1.5 font-mono text-[12px] text-fg"
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setDuplicateOpen(false)}>Annuler</Button>
              <Button variant="primary" size="sm" disabled={!duplicateName.trim()} onClick={() => { duplicateTable(dbId, table.id, duplicateName.trim()); setDuplicateOpen(false); }}>
                Dupliquer
              </Button>
            </div>
          </div>
        </div>
      )}
      <CreateTableModal open={createOpen} onClose={() => setCreateOpen(false)} dbId={dbId} />
    </div>
  );
}
