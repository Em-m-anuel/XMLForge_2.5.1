import { useEffect, useState, useCallback, useRef } from "react";
import { Icon, type IconName } from "../components/Icon";
import { Badge, Button, Panel, SectionHeader, StatusDot, useToast } from "../components/ui";
import { ShutdownModal } from "../components/ShutdownModal";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore } from "../store";
import { tcpService } from "../api/tcp";

function ServiceCard({
  icon,
  name,
  status,
  rows,
}: {
  icon: IconName;
  name: string;
  status: "running" | "healthy" | "stopped";
  rows: { k: string; v: string }[];
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-raised text-accent">
          <Icon name={icon} size={14} />
        </span>
        <span className="flex-1 text-[13px] font-medium text-fg">{name}</span>
        <span className="flex items-center gap-1.5">
          <StatusDot tone={status === "stopped" ? "danger" : "ok"} pulse={status !== "stopped"} />
          <span className="text-[11.5px] text-muted capitalize">{status}</span>
        </span>
      </div>
      <dl className="mt-3 space-y-1.5 border-t border-line-soft pt-2.5">
        {rows.map((r) => (
          <div key={r.k} className="flex items-center justify-between gap-3">
            <dt className="text-[11.5px] text-dim">{r.k}</dt>
            <dd className="font-mono text-[11.5px] text-muted">{r.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ServerView() {
  const toast = useToast();
  const { serverHealth, tcpStatus, fetchServerStatus, dbs, isAdmin } = useStore();
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [shutdownOpen, setShutdownOpen] = useState(false);
  const mountedRef = useRef(true);
  const loadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setHealthError(null);
    setSessionsError(null);
    setLoadingSessions(true);
    try {
      // fetchServerStatus fait health + tcp status en 1 seul endroit (évite double /api/health)
      const result = (await fetchServerStatus()) as any;
      if (!mountedRef.current) return;
      if (result?.health) {
        setHealth(result.health);
      } else if (!serverHealth && !result?.health) {
        if (!result?.health) {
          if (!serverHealth) {
            setHealthError("Impossible de récupérer l'état du serveur");
          }
        }
      }
    } catch (e: any) {
      if (!mountedRef.current) return;
      setHealthError(e.message || "Erreur health");
      toast({ kind: "error", title: "Erreur health", detail: e.message });
    }

    try {
      const s = await tcpService.sessions();
      if (!mountedRef.current) return;
      // tcpService.sessions retourne { data: [...] } ou [...] selon implémentation
      const list = Array.isArray(s) ? s : (s as any)?.sessions || (s as any)?.data?.sessions || [];
      setSessions(list);
    } catch (e: any) {
      if (!mountedRef.current) return;
      setSessionsError(e.message || "Impossible de recuperer les sessions");
      setSessions([]);
    } finally {
      if (mountedRef.current) setLoadingSessions(false);
      loadingRef.current = false;
    }
  }, [fetchServerStatus, serverHealth, toast]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  const restStatus = health || serverHealth;
  const tcp = tcpStatus;

  return (
    <div className="anim-fade">
      <PageHeader
        icon="server"
        accent
        title="Serveur local"
        subtitle="Moteur natif XMLForge execute sur cette machine"
        badges={
          <Badge tone="ok" icon="cpu">
            Operationnel
          </Badge>
        }
        meta={[
          { label: "Version", value: restStatus?.version || "5.0.0", icon: "layers" },
          { label: "Bases", value: dbs.length, icon: "database" },
          { label: "Stockage", value: "XML natif", icon: "hdd" },
        ]}
        actions={
          <>
            <Button icon="refresh" onClick={load}>
              Actualiser
            </Button>
            {isAdmin && (
              <Button icon="power" variant="danger" onClick={() => setShutdownOpen(true)}>
                Fermer XMLForge
              </Button>
            )}
          </>
        }
      />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        {healthError && (
          <div className="mb-4 rounded-lg border border-danger/30 bg-danger-soft p-3">
            <p className="text-[12px] font-medium text-danger">REST API</p>
            <p className="mt-1 text-[11.5px] text-muted">Impossible de recuperer l'etat du serveur</p>
            <p className="font-mono text-[11px] text-dim">{healthError}</p>
            <Button size="xs" className="mt-2" onClick={load}>Reessayer</Button>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ServiceCard
            icon="wifi"
            name="REST API"
            status={restStatus ? "running" : "stopped"}
            rows={[
              { k: "Endpoint", v: `${tcp?.host || '0.0.0.0'}:${restStatus?.port || 5000}` },
              { k: "Service", v: restStatus?.service || "XMLForge Backend" },
              { k: "Storage", v: restStatus?.storage?.data_plane || restStatus?.storage || "XML" },
            ]}
          />
          <ServiceCard
            icon="server"
            name="Serveur TCP"
            status={tcp?.running ? "running" : "stopped"}
            rows={[
              { k: "Adresse", v: `${tcp?.host || '0.0.0.0'}:${tcp?.port || 3307}` },
              { k: "Active", v: tcp?.tcp_enabled ? "Oui" : tcp?.running ? "Oui" : "Non" },
              { k: "Protocole", v: "xmlforge/1" },
            ]}
          />
          <ServiceCard
            icon="cpu"
            name="Moteur XML"
            status="healthy"
            rows={[
              { k: "Documents", v: `${dbs.length} bases` },
              { k: "Type", v: "Natif XML" },
              { k: "Parser", v: "lxml" },
            ]}
          />
          <ServiceCard
            icon="hdd"
            name="Stockage"
            status="healthy"
            rows={[
              { k: "Type", v: "XML uniquement" },
              { k: "SQLite", v: "Absent" },
              { k: "Mode", v: "Local" },
            ]}
          />
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <Panel padding={false}>
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <SectionHeader title="Sessions TCP" description={sessionsError ? "Erreur" : `${sessions.length} session(s)`} />
              <Button size="xs" icon="refresh" onClick={load} loading={loadingSessions}>
                Actualiser
              </Button>
            </div>
            {sessionsError ? (
              <div className="px-4 py-6 text-center">
                <p className="text-[12px] font-medium text-danger">Sessions</p>
                <p className="mt-1 text-[11.5px] text-muted">Impossible de recuperer les sessions</p>
                <p className="mt-1 font-mono text-[11px] text-dim">{sessionsError}</p>
                <Button size="xs" className="mt-3" onClick={load}>Reessayer</Button>
              </div>
            ) : sessions.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px] text-dim">Aucune session TCP active.</div>
            ) : (
              <ul className="divide-y divide-line-soft">
                {sessions.map((s: any) => (
                  <li key={s.id || s.session_id} className="flex items-center gap-3 px-4 py-2">
                    <Icon name="terminal" size={12} className="text-dim" />
                    <span className="font-mono text-[11.5px] text-fg/90">{s.host || s.ip || "—"}:{s.port || ""}</span>
                    <span className="text-[11.5px] text-muted">{s.user_name || s.username || "—"}</span>
                    <div className="flex-1" />
                    <span className="font-mono text-[11px] text-dim">{s.database || ""}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <div className="flex flex-col gap-4">
            <Panel>
              <SectionHeader title="Runtime" />
              <dl className="mt-3 space-y-2">
                {[
                  { k: "Moteur", v: "XMLForge 2.0 (XML natif)" },
                  { k: "REST", v: "localhost:5000" },
                  { k: "TCP", v: "localhost:3307" },
                  { k: "Stockage", v: "XML uniquement" },
                  { k: "Permissions", v: "PERSONAL / COMMON" },
                ].map((r) => (
                  <div key={r.k} className="flex items-center justify-between gap-3 border-b border-line-soft pb-2 last:border-0 last:pb-0">
                    <dt className="text-[11.5px] text-dim">{r.k}</dt>
                    <dd className="font-mono text-[11.5px] text-muted">{r.v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="ghost" icon="refresh" onClick={load} className="flex-1">
                  Actualiser
                </Button>
              </div>
            </Panel>

            <Panel>
              <SectionHeader title="Informations" description="Chemins non exposes pour securite" />
              <p className="mt-2 text-[12px] leading-relaxed text-muted">
                XMLForge est une application locale. Les chemins de stockage reels (Control Plane, Data Plane, logs) ne sont pas exposes via l'API REST pour des raisons de securite. Le backend utilise des dossiers utilisateur inscriptibles (<span className="font-mono text-fg">%LOCALAPPDATA%\XMLForge</span> en mode installe).
              </p>
            </Panel>
          </div>
        </div>
      </div>
      <ShutdownModal open={shutdownOpen} onClose={() => setShutdownOpen(false)} />
    </div>
  );
}
