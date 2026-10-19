import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/Icon";
import { Badge, Button, EmptyState, IconButton, Tabs, useToast } from "../components/ui";
import { cn } from "../utils/cn";
import { useStore } from "../store";
import type { QueryResult } from "../api/queries";

export function SqlConsole({
  dbId,
  initialQuery,
  height = "h-52",
  showHistory = true,
}: {
  dbId?: string;
  dbName?: string;
  initialQuery?: string;
  height?: string;
  showHistory?: boolean;
}) {
  const { dbs, activeDb, tables, history, queryResult, queryLoading, queryError, executeQuery } = useStore();
  const toast = useToast();
  const effectiveDbId = dbId || activeDb;
  const db = dbs.find((d) => String(d.id) === String(effectiveDbId));
  const [sql, setSql] = useState(initialQuery ?? `SELECT *\nFROM ${tables[0]?.name ?? "users"}\nLIMIT 25;`);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [histTab, setHistTab] = useState<"recent" | "saved">("recent");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (initialQuery) setSql(initialQuery);
  }, [initialQuery, effectiveDbId]);

  useEffect(() => {
    if (queryResult) setResult(queryResult);
  }, [queryResult]);

  const run = async () => {
    if (!effectiveDbId) {
      toast({ kind: "error", title: "Aucune base sélectionnée" });
      return;
    }
    if (!sql.trim()) {
      toast({ kind: "error", title: "Requête vide" });
      return;
    }
    try {
      const r = await executeQuery(effectiveDbId, sql);
      setResult(r);
    } catch (e: any) {
      setResult({ status: "error", message: e.message, ms: 0 } as any);
    }
  };

  const filtered = useMemo(
    () => history.filter((h) => (histTab === "saved" ? h.saved : true)),
    [history, histTab],
  );

  const columns = result?.rows?.[0] ? Object.keys(result.rows[0].data || result.rows[0]) : result?.columns || [];

  return (
    <div className={cn("grid gap-3", showHistory && "xl:grid-cols-[1fr_290px]")}>
      <div className="min-w-0">
        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="flex items-center gap-2 border-b border-line bg-raised px-2.5 py-1.5">
            <Icon name="terminal" size={13} className="text-accent" />
            <span className="font-mono text-[11.5px] text-muted">{db?.name || effectiveDbId || "—"}</span>
            <Badge tone="neutral" mono>
              SQL
            </Badge>
            <div className="flex-1" />
            <Button size="xs" variant="ghost" onClick={() => setSql("")}>
              Effacer
            </Button>
            <Button size="xs" variant="primary" icon="play" loading={queryLoading} onClick={run}>
              Exécuter
            </Button>
          </div>
          <div className="flex">
            <div
              className={cn(
                "select-none border-r border-line-soft bg-surface py-2.5 text-right font-mono text-[11.5px] leading-[1.55] text-[#3f3f4a]",
                height,
              )}
            >
              {sql.split("\n").map((_, i) => (
                <div key={i} className="px-2">
                  {i + 1}
                </div>
              ))}
            </div>
            <textarea
              ref={areaRef}
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  run();
                }
              }}
              spellCheck={false}
              className={cn(
                "flex-1 resize-none bg-surface px-3 py-2.5 font-mono text-[12.5px] leading-[1.55] text-fg placeholder:text-dim focus:outline-none",
                height,
              )}
              placeholder="SELECT * FROM users WHERE email IS NOT NULL;"
            />
          </div>
          <div className="flex items-center gap-3 border-t border-line bg-raised px-3 py-1.5 text-[11px] text-dim">
            <span className="flex items-center gap-1.5">
              <span className="rounded border border-line px-1 py-0.5 text-[10px]">⌘</span>
              <span className="rounded border border-line px-1 py-0.5 text-[10px]">↵</span> exécuter
            </span>
            <span className="flex items-center gap-1.5">
              <Icon name="database" size={11} />
              {db?.name || "—"} · {tables.length} tables
            </span>
            <div className="flex-1" />
            <span>{sql.split("\n").length} lignes</span>
          </div>
        </div>

        {/* Result */}
        <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
          <div className="flex items-center gap-2 border-b border-line bg-raised px-3 py-1.5">
            <span className="text-[11.5px] font-medium text-fg">Résultat</span>
            {result && (
              <>
                {(result as any).status === "error" || queryError ? (
                  <Badge tone="danger" icon="xCircle">
                    Erreur
                  </Badge>
                ) : (
                  <Badge tone="ok" icon="checkCircle">
                    {result.rows ? `${result.rows.length} lignes` : result.count != null ? `${result.count} comptées` : `${(result as any).affected ?? 0} affectées`}
                  </Badge>
                )}
                <span className="font-mono text-[11px] text-dim">{(result as any).ms || result.timing?.ms || 0} ms</span>
              </>
            )}
            <div className="flex-1" />
          </div>

          {!result && (
            <EmptyState
              icon="play"
              title="Aucun résultat"
              description="Exécutez une requête pour afficher le résultat ici."
            />
          )}
          {(result as any)?.status === "error" || queryError ? (
            <div className="p-3">
              <div className="flex items-start gap-2.5 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5">
                <Icon name="alert" size={14} className="mt-px shrink-0 text-danger" />
                <div>
                  <p className="text-[12.5px] font-medium text-danger">{(result as any)?.message || queryError}</p>
                  <p className="mt-1 font-mono text-[11px] text-muted">
                    {db?.name || "—"} · moteur XML natif
                  </p>
                </div>
              </div>
            </div>
          ) : null}
          {result && !(result as any).status && !queryError && !result.rows && (
            <div className="flex items-center gap-2.5 px-3.5 py-4 text-[12.5px] text-muted">
              <Icon name="checkCircle" size={14} className="text-ok" />
              {(result as any).message || "Requête exécutée"} · {(result as any).affected ?? result.count ?? 0} ligne(s)
            </div>
          )}
          {result?.rows && (
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full border-collapse text-[12px]">
                <thead className="sticky top-0 bg-raised">
                  <tr>
                    <th className="w-10 border-b border-line px-2 py-1.5 text-left font-mono text-[10.5px] font-medium uppercase tracking-wide text-dim">
                      #
                    </th>
                    {columns.map((c) => (
                      <th
                        key={c}
                        className="border-b border-line px-3 py-1.5 text-left font-mono text-[10.5px] font-medium uppercase tracking-wide text-dim"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((r: any, i: number) => {
                    const data = r.data || r;
                    return (
                      <tr key={i} className="transition-colors hover:bg-panel">
                        <td className="border-b border-line-soft px-2 py-1.5 font-mono text-[11px] text-dim">{i + 1}</td>
                        {columns.map((c) => (
                          <td
                            key={c}
                            className={cn(
                              "max-w-[280px] truncate border-b border-line-soft px-3 py-1.5 font-mono text-[11.5px]",
                              data[c] === null ? "italic text-dim" : "text-fg/90",
                            )}
                          >
                            {data[c] === null ? "NULL" : String(data[c])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showHistory && (
        <div className="min-w-0">
          <div className="overflow-hidden rounded-lg border border-line bg-surface">
            <div className="px-1 pt-1">
              <Tabs
                size="sm"
                tabs={[
                  { id: "recent" as const, label: "Récentes", count: history.length },
                  { id: "saved" as const, label: "Favoris", count: history.filter((h) => h.saved).length },
                ]}
                value={histTab}
                onChange={setHistTab as any}
              />
            </div>
            <div className="max-h-[560px] overflow-y-auto p-1.5">
              {filtered.length === 0 && (
                <p className="px-2 py-8 text-center text-[11.5px] text-dim">
                  {histTab === "saved" ? "Aucune requête favorite" : "Aucun historique"}
                </p>
              )}
              {filtered.map((h) => (
                <div
                  key={h.id}
                  className="group rounded-md px-2 py-1.5 transition-colors hover:bg-panel"
                  onClick={() => setSql(h.sql)}
                >
                  <div className="flex items-center gap-1.5">
                    <Icon
                      name={h.status === "ok" ? "checkCircle" : "xCircle"}
                      size={11}
                      className={h.status === "ok" ? "text-ok" : "text-danger"}
                    />
                    <span className="text-[10.5px] text-dim">{h.at}</span>
                    <span className="font-mono text-[10.5px] text-dim">{h.ms}ms</span>
                    <div className="flex-1" />
                  </div>
                  <p className="mt-1 line-clamp-2 cursor-pointer font-mono text-[11px] leading-relaxed text-muted group-hover:text-fg">
                    {h.sql}
                  </p>
                  {h.error && <p className="mt-1 text-[10.5px] text-danger">{h.error}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
