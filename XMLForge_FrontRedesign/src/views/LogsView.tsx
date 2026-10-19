import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { Badge, Button, Panel, SectionHeader } from "../components/ui";
import { PageHeader } from "../components/layout/PageHeader";
import { useStore } from "../store";
import { auditService } from "../api/audit";

export function LogsView() {
  const { serverHealth } = useStore();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await auditService.list(100);
      // Transformer audit en logs pour affichage
      const mapped = data.map((a: any, i: number) => ({
        id: a.id || i,
        level: "INFO",
        at: a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : "—",
        source: a.action?.split('.')[0] || "rest",
        message: `${a.action} ${a.element_name || ""} par ${a.user_name || ""}`,
      }));
      setLogs(mapped);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="anim-fade">
      <PageHeader
        icon="logs"
        accent
        title="Journaux"
        subtitle="Journal d'audit du moteur XML (les logs fichier ne sont pas exposés via REST pour sécurité)"
        meta={[
          { label: "Entrées", value: logs.length, icon: "rows" },
          { label: "Stockage", value: "XML", icon: "hdd" },
        ]}
        actions={
          <>
            <Button icon="refresh" onClick={load} loading={loading}>
              Actualiser
            </Button>
          </>
        }
      />

      <div className="mx-auto grid w-full max-w-[1400px] gap-4 px-6 py-5">
        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="grid grid-cols-[110px_80px_1fr] items-center gap-3 border-b border-line bg-raised px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
            <span>Heure</span>
            <span>Source</span>
            <span>Message</span>
          </div>
          {loading ? (
            <div className="px-4 py-10 text-center text-[12px] text-dim">Chargement...</div>
          ) : logs.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-[13px] text-muted">Aucun journal disponible.</p>
              <p className="mt-1 text-[11.5px] text-dim">Les logs fichier détaillés sont dans %LOCALAPPDATA%\XMLForge\logs\ (mode installé) et ne sont pas exposés via REST pour sécurité.</p>
            </div>
          ) : (
            <div className="max-h-[620px] overflow-y-auto">
              {logs.map((l) => (
                <div
                  key={l.id}
                  className="grid grid-cols-[110px_80px_1fr] items-center gap-3 border-b border-line-soft px-4 py-1.5 font-mono text-[11.5px] last:border-0 hover:bg-panel"
                >
                  <span className="text-dim">{l.at}</span>
                  <span className="text-muted">{l.source}</span>
                  <span className="truncate text-fg/85">{l.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Panel>
          <SectionHeader title="Informations" />
          <p className="mt-2 text-[12px] leading-relaxed text-muted">
            XMLForge ne sert pas les fichiers de log via HTTP pour des raisons de sécurité. En mode développement, les logs sont dans la console. En mode installé, ils sont dans <span className="font-mono text-fg">%LOCALAPPDATA%\XMLForge\logs\xmlforge.log</span> (rotation 5 MB × 3).
          </p>
          <p className="mt-2 text-[11.5px] text-dim">
            Version backend: {serverHealth?.version || "5.0.0"} · Stockage: XML natif · SQLite absent
          </p>
        </Panel>
      </div>
    </div>
  );
}
