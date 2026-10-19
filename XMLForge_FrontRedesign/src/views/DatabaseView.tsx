import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  EmptyState,
  IconButton,
  Input,
  Panel,
  SectionHeader,
  Tabs,
  useToast,
} from "../components/ui";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore } from "../store";
import { CreateTableModal, EditDatabaseModal, ShareModal, UnlockTableModal, ConfirmModal } from "../components/modals";
import { SqlConsole } from "./SqlConsole";
import { RelationDiagram } from "./RelationDiagram";
import { XmlPanel } from "./XmlPanel";
import { xmlService } from "../api/xml";
import { permissionService } from "../api/permissions";

function PermissionsView({ dbId }: { dbId: string }) {
  const { dbs } = useStore();
  const db = dbs.find(d => String(d.id) === dbId);
  const toast = useToast();
  const [perms, setPerms] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<'VIEW' | 'EDIT' | 'MANAGE'>('VIEW');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await permissionService.listDatabase(dbId);
      setPerms(data);
    } catch (e: any) {
      if (e.status === 403) {
        setError("Accès refusé — permission admin requise pour voir les permissions.");
      } else {
        setError(e.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [dbId]);

  const grant = async () => {
    if (!email.trim()) return;
    const rights = role === 'MANAGE' ? { can_read: true, can_write: true, can_ddl: true, can_admin: true }
      : role === 'EDIT' ? { can_read: true, can_write: true, can_ddl: true, can_admin: false }
      : { can_read: true, can_write: false, can_ddl: false, can_admin: false };
    try {
      await permissionService.grantDatabase(dbId, { email: email.trim(), ...rights });
      await load();
      setEmail("");
      toast({ kind: "success", title: "Permission accordée", detail: `${role} à ${email}` });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur partage", detail: e.message });
    }
  };

  const revoke = async (userId: number) => {
    if (!window.confirm("Retirer cette permission ?")) return;
    try {
      await permissionService.revokeDatabase(dbId, userId);
      setPerms(p => p.filter(x => x.user_id !== userId));
      toast({ kind: "success", title: "Permission retirée" });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur retrait", detail: e.message });
    }
  };

  if (!db) return <div className="p-4 text-[12px] text-dim">Base introuvable.</div>;

  if (db.scope === 'COMMON') {
    return (
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Panel>
          <SectionHeader title="Base commune" description="Permissions collectives" />
          <div className="mt-3 rounded-md border border-violet/30 bg-violet-soft/20 p-3 text-[12px] text-violet">
            Cette base est <span className="font-medium">COMMON</span> — visible par tous les utilisateurs actifs avec permission collective <span className="font-mono">{db.common_permission || 'VIEW'}</span>. Les droits d'écriture restent contrôlés par rôle. Modifiez via Modifier la base.
          </div>
          <div className="mt-4 space-y-2 text-[12px] text-muted">
            <p><span className="text-fg">VIEW</span> — lecture seule</p>
            <p><span className="text-fg">EDIT</span> — lecture + écriture + DDL</p>
            <p><span className="text-fg">MANAGE</span> — administration complète</p>
          </div>
        </Panel>
        <Panel>
          <SectionHeader title="Règles" />
          <p className="mt-2 text-[12px] text-muted">Les bases COMMON ne nécessitent pas de partage individuel VIEW. Tous les actifs y ont accès selon permission collective.</p>
        </Panel>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Panel padding={false}>
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <SectionHeader title="Permissions" description={`${perms.length} membre(s) · PERSONAL`} />
          <Button size="xs" icon="refresh" onClick={load} loading={loading}>Actualiser</Button>
        </div>

        {error ? (
          <div className="p-4">
            <div className="rounded-md border border-danger/30 bg-danger-soft p-3">
              <p className="text-[12px] font-medium text-danger">Impossible de charger les permissions</p>
              <p className="mt-1 text-[11.5px] text-muted">{error}</p>
              <Button size="xs" className="mt-2" onClick={load}>Réessayer</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="p-3">
              <div className="flex gap-2">
                <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@exemple.com" className="flex-1" />
                <select value={role} onChange={(e) => setRole(e.target.value as any)} className="h-7.5 rounded-md border border-line bg-surface px-2 text-[12px]">
                  <option value="VIEW">VIEW</option>
                  <option value="EDIT">EDIT</option>
                  <option value="MANAGE">MANAGE</option>
                </select>
                <Button size="sm" variant="primary" disabled={!email.trim()} onClick={grant}>Partager</Button>
              </div>
            </div>

            <div className="overflow-hidden border-t border-line">
              <div className="grid grid-cols-[1fr_100px_80px_60px] gap-2 border-b border-line bg-raised px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
                <span>Utilisateur</span>
                <span>Niveau</span>
                <span>Accès</span>
                <span />
              </div>
              {loading ? (
                <div className="px-3 py-6 text-center text-[12px] text-dim">Chargement...</div>
              ) : perms.length === 0 ? (
                <EmptyState icon="shield" title="Aucun partage" description="Cette base PERSONAL n'est partagée avec personne. Seul le propriétaire y a accès." />
              ) : (
                perms.map((p) => (
                  <div key={p.id} className="grid grid-cols-[1fr_100px_80px_60px] items-center gap-2 border-b border-line-soft px-3 py-2 last:border-0 hover:bg-panel">
                    <span className="truncate text-[12.5px] text-fg">{p.user_email || `User #${p.user_id}`}</span>
                    <Badge tone={p.can_admin ? "violet" : p.can_write ? "ok" : "neutral"}>{p.can_admin ? "MANAGE" : p.can_write ? "EDIT" : "VIEW"}</Badge>
                    <span className="text-[11px] text-dim">{p.can_read ? "R" : ""}{p.can_write ? "W" : ""}{p.can_ddl ? "D" : ""}{p.can_admin ? "A" : ""}</span>
                    <button onClick={() => revoke(p.user_id)} className="flex h-6 w-6 items-center justify-center rounded text-dim hover:text-danger">
                      <Icon name="trash" size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </Panel>

      <div className="flex flex-col gap-4">
        <Panel>
          <SectionHeader title="Niveaux d'accès" />
          <ul className="mt-3 space-y-2">
            {[
              { l: "VIEW", d: "Lecture seule des données et structure", t: "neutral" as const },
              { l: "EDIT", d: "VIEW + écriture lignes + DDL tables/colonnes", t: "ok" as const },
              { l: "MANAGE", d: "EDIT + gestion permissions et suppression", t: "violet" as const },
            ].map(x => (
              <li key={x.l} className="flex items-start gap-2 rounded-md border border-line-soft bg-panel px-3 py-2">
                <Badge tone={x.t}>{x.l}</Badge>
                <span className="text-[11.5px] text-muted">{x.d}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <SectionHeader title="Portée" />
          <div className="mt-2 text-[12px] text-muted space-y-1">
            <p><span className="text-fg">PERSONAL</span> — privée, owner unique, partage explicite par email</p>
            <p><span className="text-fg">COMMON</span> — commune, visible par tous les actifs, permission collective</p>
            <p className="text-dim">Changement PERSONAL↔COMMON autorisé avec permission admin (PUT /databases/{id} scope)</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function DatabaseView({ dbId, tab }: { dbId: string; tab: any }) {
  const { dbs, tables, tablesLoading, tablesError, go, dropTable, setProtected, canManageDb, fetchTables, fetchXml, xmlDoc, xmlLoading } = useStore();
  const toast = useToast();
  const db = dbs.find((d) => String(d.id) === dbId);
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [unlock, setUnlock] = useState<number | null>(null);
  const [drop, setDrop] = useState<number | null>(null);

  const filtered = useMemo(
    () => tables.filter((t) => t.name.toLowerCase().includes(q.trim().toLowerCase())),
    [tables, q],
  );

  if (!db) {
    return (
      <div className="px-6 py-10">
        <EmptyState icon="database" title="Base introuvable" description="La base demandée n'existe plus." />
      </div>
    );
  }

  const protectedCount = tables.filter((t) => t.is_protected).length;

  return (
    <div className="anim-fade">
      <PageHeader
        icon={db.scope === "COMMON" ? "layers" : "database"}
        accent
        title={db.name}
        badges={
          <>
            {db.scope === "COMMON" ? <Badge tone="violet">COMMON</Badge> : <Badge tone="neutral">PERSONAL</Badge>}
            {protectedCount > 0 && (
              <Badge tone="warn" icon="lock">
                {protectedCount} protégées
              </Badge>
            )}
            {db.status === 'ARCHIVED' && <Badge tone="neutral">ARCHIVÉ</Badge>}
          </>
        }
        subtitle={
          <>
            <span>{db.scope === "COMMON" ? "Base commune" : "Base personnelle"}</span>
            <span className="text-dim">·</span>
            <span>Propriétaire: {db.owner_name || db.creator_name}</span>
            {db.description && (
              <>
                <span className="text-dim">·</span>
                <span>{db.description}</span>
              </>
            )}
          </>
        }
        meta={[
          { label: "Tables", value: db.tables_count || tables.length, icon: "table" },
          { label: "Version", value: db.document_version, icon: "clock" },
          { label: "Statut", value: db.status, icon: "hdd" },
          { label: "Créée", value: db.created_at ? new Date(db.created_at).toLocaleDateString() : "—", icon: "clock" },
        ]}
        actions={
          <>
            {canManageDb(db) && (
              <Button icon="pencil" onClick={() => setEditOpen(true)}>
                Modifier
              </Button>
            )}
            <Button icon="share" onClick={() => setShareOpen(true)}>
              Partage
            </Button>
            <Button icon="download" onClick={async () => {
              try {
                await xmlService.exportDatabaseXml(db.id);
                toast({ kind: "success", title: "Export XML", detail: `${db.name}.xml` });
              } catch (e: any) {
                toast({ kind: "error", title: "Erreur export", detail: e.message });
              }
            }}>
              Exporter XML
            </Button>
            <Button variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
              Créer table
            </Button>
          </>
        }
        tabs={
          <Tabs
            tabs={[
              { id: "tables" as const, label: "Tables", icon: "table", count: tables.length },
              { id: "sql" as const, label: "SQL", icon: "terminal" },
              { id: "relations" as const, label: "Relations", icon: "relations" },
              { id: "xml" as const, label: "XML", icon: "code" },
              { id: "share" as const, label: "Permissions", icon: "share" },
            ]}
            value={tab}
            onChange={(t) => go({ v: "db", db: dbId, tab: t as any })}
          />
        }
      />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        {tab === "tables" && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-64">
                <Input icon="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer les tables..." />
              </div>
              <span className="text-[11.5px] text-dim">
                {filtered.length} table{filtered.length > 1 ? "s" : ""} · Version {db.document_version}
              </span>
              <div className="flex-1" />
              <Button size="sm" icon="refresh" onClick={() => fetchTables(dbId)}>
                Actualiser
              </Button>
              <Button size="sm" variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
                Créer table
              </Button>
            </div>

            {tablesLoading ? (
              <div className="mt-6 flex items-center gap-2 text-[13px] text-muted">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
                Chargement des tables...
              </div>
            ) : tablesError ? (
              <div className="mt-6 rounded-lg border border-danger/30 bg-danger-soft p-4">
                <p className="text-[13px] font-medium text-danger">Impossible de charger les tables.</p>
                <p className="mt-1 text-[12px] text-muted">{tablesError}</p>
                <Button size="sm" className="mt-3" onClick={() => fetchTables(dbId)}>
                  Réessayer
                </Button>
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon="table"
                title={q ? "Aucune table ne correspond" : "Aucune table"}
                description={q ? `Aucun résultat pour "${q}".` : "Créez une table pour structurer votre document XML."}
                action={
                  q ? (
                    <Button size="sm" onClick={() => setQ("")}>
                      Effacer filtre
                    </Button>
                  ) : (
                    <Button size="sm" variant="primary" icon="plus" onClick={() => setCreateOpen(true)}>
                      Créer table
                    </Button>
                  )
                }
              />
            ) : (
              <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
                <div className="grid grid-cols-[1.5fr_110px_110px_170px_100px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
                  <span>Table</span>
                  <span className="text-right">Colonnes</span>
                  <span>Protection</span>
                  <span>Mise à jour</span>
                  <span />
                </div>
                {filtered.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => go({ v: "table", db: dbId, table: String(t.id), tab: "data" })}
                    className="grid cursor-pointer grid-cols-[1.5fr_110px_110px_170px_100px] items-center gap-3 border-b border-line-soft px-4 py-2.5 transition-colors last:border-0 hover:bg-panel"
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-accent">
                        <Icon name="table" size={13} />
                      </span>
                      <span className="min-w-0">
                        <span className="flex items-center gap-2">
                          <span className="truncate font-mono text-[13px] text-fg">{t.name}</span>
                        </span>
                        {t.description && <span className="mt-0.5 block truncate text-[11.5px] text-dim">{t.description}</span>}
                      </span>
                    </div>
                    <span className="text-right font-mono text-[12px] text-muted">{t.columns_count || 0}</span>
                    <span>
                      {t.is_protected ? (
                        <Badge tone="warn" icon="lock">
                          Protégée
                        </Badge>
                      ) : (
                        <span className="text-[11.5px] text-dim">—</span>
                      )}
                    </span>
                    <span className="font-mono text-[11.5px] text-dim">{t.updated_at ? new Date(t.updated_at).toLocaleDateString() : "—"}</span>
                    <div className="flex justify-end gap-0.5" onClick={(e) => e.stopPropagation()}>
                      <IconButton
                        icon={t.is_protected ? "unlock" : "lock"}
                        label={t.is_protected ? "Déverrouiller" : "Protéger"}
                        onClick={() => (t.is_protected ? setUnlock(t.id) : setProtected(dbId, t.id, true))}
                      />
                      <Button size="xs" variant="ghost" onClick={() => go({ v: "table", db: dbId, table: String(t.id), tab: "data" })}>
                        Ouvrir
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "sql" && <SqlConsole dbId={dbId} />}

        {tab === "relations" && <RelationDiagram dbId={dbId} />}

        {tab === "xml" && (
          <XmlPanel
            doc={xmlDoc}
            title={`${db.name}.xml`}
            subtitle={`${tables.length} tables · Version ${db.document_version}`}
            height={520}
            onLoad={() => fetchXml(undefined, dbId)}
            loading={xmlLoading}
          />
        )}

        {tab === "share" && <PermissionsView dbId={dbId} />}
      </div>

      <CreateTableModal open={createOpen} onClose={() => setCreateOpen(false)} dbId={dbId} />
      <EditDatabaseModal open={editOpen} onClose={() => setEditOpen(false)} dbId={dbId} />
      <ShareModal open={shareOpen} onClose={() => setShareOpen(false)} dbId={dbId} />
      <UnlockTableModal open={!!unlock} onClose={() => setUnlock(null)} dbId={dbId} tableId={unlock || 0} />
      <ConfirmModal
        open={!!drop}
        onClose={() => setDrop(null)}
        title="Supprimer table"
        description={`Supprimer définitivement la table ${drop} ?`}
        confirmLabel="Supprimer"
        danger
        onConfirm={() => drop && dropTable(dbId, drop)}
      />
    </div>
  );
}
