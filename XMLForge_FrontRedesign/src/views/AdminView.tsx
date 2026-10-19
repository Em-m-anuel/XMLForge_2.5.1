import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Dropdown,
  EmptyState,
  IconButton,
  Input,
  MenuItem,
  Panel,
  SectionHeader,
  Select,
  StatusDot,
  Tabs,
  useToast,
} from "../components/ui";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore, type AdminTab } from "../store";
import { userService } from "../api/users";
import { auditService } from "../api/audit";
import { historyService } from "../api/history";

const ROLE_TONE = { admin: "violet", user: "neutral" } as const;

export function AdminView({ tab }: { tab: AdminTab }) {
  const { go, dbs, history, isAdmin } = useStore();
  const toast = useToast();
  const [users, setUsers] = useState<any[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [audit, setAudit] = useState<any[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadUsers = async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const data = await userService.list(q);
      setUsers(data);
    } catch (e: any) {
      if (e.status === 403) {
        setUsersError("Accès refusé — administrateur requis.");
      } else {
        setUsersError(e.message);
      }
    } finally {
      setUsersLoading(false);
    }
  };

  const loadAudit = async () => {
    setAuditLoading(true);
    try {
      const data = await auditService.list(100);
      setAudit(data);
    } catch {
      setAudit([]);
    } finally {
      setAuditLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await historyService.list(100, 0);
      setHistoryData(data);
    } catch {
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (tab === 'users') loadUsers();
    if (tab === 'audit') loadAudit();
    if (tab === 'history') loadHistory();
  }, [tab, q]);

  const filteredUsers = useMemo(
    () =>
      users.filter(
        (u) =>
          (roleFilter === "all" || (u.role || "").toLowerCase() === roleFilter) &&
          `${u.full_name || ""} ${u.email || ""}`.toLowerCase().includes(q.trim().toLowerCase()),
      ),
    [users, q, roleFilter],
  );

  if (!isAdmin) {
    return (
      <div className="mx-auto w-full max-w-[1400px] px-6 py-10">
        <div className="rounded-lg border border-danger/30 bg-danger-soft p-6 text-center">
          <Icon name="shield" size={24} className="mx-auto text-danger" />
          <h2 className="mt-3 text-[16px] font-semibold text-fg">Accès refusé</h2>
          <p className="mt-1 text-[13px] text-muted">Cette page nécessite le rôle administrateur.</p>
          <Button size="sm" className="mt-4" onClick={() => go({ v: "overview" })}>
            Retour accueil
          </Button>
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Utilisateurs", value: users.length, icon: "users" as const },
    { label: "Actifs", value: users.filter((u) => u.is_active).length, icon: "checkCircle" as const },
    { label: "Bases", value: dbs.length, icon: "database" as const },
    { label: "Audit", value: audit.length, icon: "history" as const },
  ];

  return (
    <div className="anim-fade">
      <PageHeader
        icon="shield"
        accent
        title="Administration"
        subtitle="Utilisateurs, permissions, audit et historique"
        meta={stats.map((s) => ({ label: s.label, value: s.value, icon: s.icon }))}
        tabs={
          <Tabs
            tabs={[
              { id: "users" as const, label: "Utilisateurs", icon: "users", count: users.length },
              { id: "audit" as const, label: "Audit", icon: "history", count: audit.length },
              { id: "history" as const, label: "Historique", icon: "clock", count: historyData.length || history.length },
            ]}
            value={tab}
            onChange={(t) => go({ v: "admin", tab: t })}
          />
        }
      />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        {tab === "users" && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-64">
                <Input icon="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher utilisateurs..." />
              </div>
              <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
                <option value="all">Tous rôles</option>
                <option value="admin">Admin</option>
                <option value="user">User</option>
              </Select>
              <div className="flex-1" />
              <Button size="sm" icon="refresh" onClick={loadUsers} loading={usersLoading}>
                Actualiser
              </Button>
              <span className="text-[11.5px] text-dim">{filteredUsers.length} utilisateur(s)</span>
            </div>

            {usersError ? (
              <div className="mt-3 rounded-lg border border-danger/30 bg-danger-soft p-4">
                <p className="text-[13px] font-medium text-danger">{usersError}</p>
                <Button size="sm" className="mt-3" onClick={loadUsers}>
                  Réessayer
                </Button>
              </div>
            ) : (
              <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
                <div className="grid grid-cols-[1.4fr_110px_110px_120px_60px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
                  <span>Utilisateur</span>
                  <span>Rôle</span>
                  <span>Statut</span>
                  <span>Dernière connexion</span>
                  <span />
                </div>
                {usersLoading ? (
                  <div className="px-4 py-10 text-center text-[12px] text-dim">Chargement...</div>
                ) : filteredUsers.length === 0 ? (
                  <EmptyState icon="users" title="Aucun utilisateur" description="Aucun résultat." />
                ) : (
                  filteredUsers.map((u) => (
                    <div
                      key={u.id}
                      className="grid grid-cols-[1.4fr_110px_110px_120px_60px] items-center gap-3 border-b border-line-soft px-4 py-2.5 last:border-0 hover:bg-panel"
                    >
                      <div className="flex min-w-0 items-center gap-2.5">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-[10px] font-semibold text-muted">
                          {(u.full_name || u.email || "??").slice(0, 2).toUpperCase()}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[12.5px] font-medium text-fg">{u.full_name || "—"}</span>
                          <span className="block truncate text-[11.5px] text-dim">{u.email}</span>
                        </span>
                      </div>
                      <Badge tone={(ROLE_TONE as any)[(u.role || "user").toLowerCase()] || "neutral"}>{u.role || "user"}</Badge>
                      <Badge tone={u.is_active ? "ok" : "neutral"}>{u.is_active ? "Actif" : "Inactif"}</Badge>
                      <span className="text-[11.5px] text-muted">{u.last_login ? new Date(u.last_login).toLocaleDateString() : "Jamais"}</span>
                      <Dropdown
                        align="right"
                        width="w-48"
                        trigger={({ toggle }) => <IconButton icon="more" label="Actions" onClick={toggle} />}
                      >
                        {(close) => (
                          <>
                            <MenuItem
                              icon={u.is_active ? "x" : "checkCircle"}
                              onClick={async () => {
                                close();
                                try {
                                  await userService.toggleActive(u.id);
                                  await loadUsers();
                                  toast({ kind: "success", title: "Statut modifié" });
                                } catch (e: any) {
                                  toast({ kind: "error", title: "Erreur", detail: e.message });
                                }
                              }}
                            >
                              {u.is_active ? "Désactiver" : "Activer"}
                            </MenuItem>
                            <MenuItem
                              icon="trash"
                              danger
                              onClick={async () => {
                                close();
                                if (!window.confirm(`Supprimer ${u.email} ?`)) return;
                                try {
                                  await userService.delete(u.id);
                                  await loadUsers();
                                  toast({ kind: "warn", title: "Utilisateur supprimé" });
                                } catch (e: any) {
                                  toast({ kind: "error", title: "Erreur", detail: e.message });
                                }
                              }}
                            >
                              Supprimer
                            </MenuItem>
                          </>
                        )}
                      </Dropdown>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}

        {tab === "audit" && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex-1" />
              <Button size="sm" icon="refresh" onClick={loadAudit} loading={auditLoading}>
                Actualiser
              </Button>
            </div>
            <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
              <div className="grid grid-cols-[160px_120px_150px_1fr_110px_90px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
                <span>Timestamp</span>
                <span>Utilisateur</span>
                <span>Action</span>
                <span>Cible</span>
                <span>IP</span>
                <span>Résultat</span>
              </div>
              {auditLoading ? (
                <div className="px-4 py-10 text-center text-[12px] text-dim">Chargement...</div>
              ) : audit.length === 0 ? (
                <EmptyState icon="history" title="Aucune entrée audit" />
              ) : (
                audit.map((a) => (
                  <div
                    key={a.id}
                    className="grid grid-cols-[160px_120px_150px_1fr_110px_90px] items-center gap-3 border-b border-line-soft px-4 py-2 last:border-0 hover:bg-panel"
                  >
                    <span className="font-mono text-[11.5px] text-dim">{a.timestamp ? new Date(a.timestamp).toLocaleString() : a.created_at}</span>
                    <span className="truncate text-[12px] text-fg">{a.user_name || `User #${a.user_id}`}</span>
                    <span className="font-mono text-[11.5px] text-accent">{a.action}</span>
                    <span className="truncate font-mono text-[11.5px] text-muted">{a.element_name || a.element_type}</span>
                    <span className="font-mono text-[11.5px] text-dim">{a.ip_address || "—"}</span>
                    <Badge tone="ok">ok</Badge>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === "history" && (
          <div className="overflow-hidden rounded-lg border border-line bg-surface">
            <div className="grid grid-cols-[160px_120px_1fr_80px] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
              <span>Date</span>
              <span>Utilisateur</span>
              <span>Action</span>
              <span>Type</span>
            </div>
            {historyLoading ? (
              <div className="px-4 py-10 text-center text-[12px] text-dim">Chargement...</div>
            ) : historyData.length === 0 ? (
              <EmptyState icon="clock" title="Aucun historique" />
            ) : (
              historyData.map((h) => (
                <div
                  key={h.id}
                  className="grid grid-cols-[160px_120px_1fr_80px] items-center gap-3 border-b border-line-soft px-4 py-2 last:border-0 hover:bg-panel"
                >
                  <span className="font-mono text-[11.5px] text-dim">{h.created_at ? new Date(h.created_at).toLocaleString() : "—"}</span>
                  <span className="text-[11.5px] text-muted">{h.user_name || "—"}</span>
                  <span className="truncate font-mono text-[11.5px] text-fg/90">{h.action_type} {h.element_name}</span>
                  <span className="text-[11px] text-dim">{h.element_type}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
