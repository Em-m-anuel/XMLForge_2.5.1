import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/Icon";
import { Badge, Button, Input, Select } from "../components/ui";
import { cn } from "../utils/cn";
import { useStore } from "../store";
import { columnService, type Column } from "../api/columns";
import type { Table } from "../api/tables";

const W = 236;
const HEADER = 30;
const ROW = 19;

function nodeHeight(cols: Column[]) {
  return HEADER + cols.length * ROW + 8;
}

type Pos = { x: number; y: number };

export function RelationDiagram({ dbId, focusTableId }: { dbId?: string; db?: any; focus?: string; focusTableId?: number }) {
  const { go, tables, dbs, activeDb, columns } = useStore();
  const effectiveDbId = dbId || activeDb;
  const db = dbs.find(d => String(d.id) === String(effectiveDbId));
  const containerRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<Record<string, Pos>>({});
  const [drag, setDrag] = useState<{ name: string; dx: number; dy: number } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [columnsByTable, setColumnsByTable] = useState<Record<number, Column[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<'diagram' | 'list'>('diagram');
  const [showCols, setShowCols] = useState(true);
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('xmlforge_fav_tables') || '[]');
    } catch { return []; }
  });

  // Favoris
  const toggleFav = (name: string) => {
    setFavorites(prev => {
      const next = prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name];
      localStorage.setItem('xmlforge_fav_tables', JSON.stringify(next));
      return next;
    });
  };

  // Optimisation V2.3 : utiliser GET /databases/{id}/schema (1 requête) au lieu de N GET /columns
  // Fallback vers N requêtes si schema indisponible
  useEffect(() => {
    if (!tables.length || !effectiveDbId) return;
    setLoading(true);
    setError(null);
    const loadViaSchema = async () => {
      try {
        const { queryService } = await import("../api/queries");
        const schema = await queryService.schema(effectiveDbId);
        // schema.tables = [{name, columns:[{name, type, primary_key, foreign_key, references...}], foreign_keys, primary_key, row_count}]
        const map: Record<number, Column[]> = {};
        const nameToId: Record<string, number> = {};
        tables.forEach(t => { nameToId[t.name] = t.id; });
        schema.tables?.forEach((tbl: any) => {
          const id = nameToId[tbl.name];
          if (!id) return;
          // Convertir colonnes schéma vers Column type
          const cols: Column[] = (tbl.columns || []).map((c: any, idx: number) => ({
            id: idx, // pas d'id réel dans schema, mais on garde index pour affichage
            uuid: "",
            name: c.name,
            type: c.type,
            length: c.length || "-",
            nullable: c.nullable,
            primary_key: c.primary_key,
            foreign_key: c.foreign_key || !!c.references,
            unique: c.unique,
            auto_increment: c.auto_increment,
            default: c.default,
            references: c.references,
            on_delete: "NO ACTION",
            on_update: "NO ACTION",
            index: c.index,
            comment: c.comment || "",
            status: "ACTIVE",
            table_id: id,
          }));
          map[id] = cols;
        });
        setColumnsByTable(map);
        setLoading(false);
      } catch (e: any) {
        // Fallback N requêtes
        try {
          const entries = await Promise.all(tables.map(async t => {
            try {
              const cols = await columnService.list(t.id, false);
              return [t.id, cols] as const;
            } catch {
              return [t.id, []] as const;
            }
          }));
          setColumnsByTable(Object.fromEntries(entries));
        } catch (err: any) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      }
    };
    loadViaSchema();
  }, [tables, effectiveDbId]);

  const layout = useMemo(() => {
    const p: Record<string, Pos> = {};
    let y = 32;
    let x = 32;
    tables.forEach((t, i) => {
      const cols = columnsByTable[t.id] || [];
      const h = showCols ? nodeHeight(cols) : HEADER + 8;
      if (i > 0 && i % 3 === 0) {
        x += 300;
        y = 32;
      }
      p[t.name] = { x, y };
      y += h + 52;
    });
    return { p };
  }, [tables, columnsByTable, showCols]);

  useEffect(() => {
    setPos(layout.p);
  }, [layout]);

  useEffect(() => {
    if (!drag) return;
    const move = (e: MouseEvent) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPos((s) => ({
        ...s,
        [drag.name]: {
          x: Math.max(8, (e.clientX - rect.left - rect.width/2)/zoom + rect.width/2/zoom + drag.dx),
          y: Math.max(8, (e.clientY - rect.top)/zoom + drag.dy),
        },
      }));
    };
    const up = () => setDrag(null);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [drag, zoom]);

  const edges = useMemo(() => {
    const out: { from: string; fromCol: string; fromId: number; to: string; toCol: string }[] = [];
    tables.forEach((t) => {
      const cols = columnsByTable[t.id] || [];
      cols.filter(c => c.foreign_key && c.references).forEach(c => {
        const [refTable, refCol] = (c.references || "").split('.');
        if (refTable) {
          out.push({ from: t.name, fromCol: c.name, fromId: t.id, to: refTable, toCol: refCol || "id" });
        }
      });
    });
    return out;
  }, [tables, columnsByTable]);

  const filteredTables = useMemo(() => {
    const s = search.trim().toLowerCase();
    if (!s) return tables;
    return tables.filter(t => t.name.toLowerCase().includes(s) || (columnsByTable[t.id] || []).some(c => c.name.toLowerCase().includes(s)));
  }, [tables, search, columnsByTable]);

  const focusTable = tables.find(t => t.id === focusTableId);
  const related = useMemo(() => {
    if (!focusTable) return null;
    const set = new Set<string>([focusTable.name]);
    edges.forEach((e) => {
      if (e.from === focusTable.name) set.add(e.to);
      if (e.to === focusTable.name) set.add(e.from);
    });
    return set;
  }, [focusTable, edges]);

  const height = Math.max(
    460,
    Math.max(...filteredTables.map((t) => (pos[t.name]?.y ?? 0) + nodeHeight(columnsByTable[t.id] || []))) + 60,
  );
  const width = Math.max(900, Math.max(...filteredTables.map((t) => (pos[t.name]?.x ?? 0))) + W + 60);

  const incoming = (tableName: string) => edges.filter(e => e.to === tableName);
  const outgoing = (tableName: string) => edges.filter(e => e.from === tableName);

  if (loading) {
    return <div className="p-6 text-[12px] text-dim">Chargement du schéma...</div>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-danger/30 bg-danger-soft p-4">
        <p className="text-[13px] font-medium text-danger">Impossible de charger le schéma.</p>
        <p className="mt-1 text-[12px] text-muted">{error}</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-raised px-3 py-1.5">
        <Icon name="relations" size={13} className="text-accent" />
        <span className="text-[12px] font-medium text-fg">Schéma</span>
        <Badge tone="neutral" mono>
          {tables.length} tables
        </Badge>
        <Badge tone="accent" icon="link">
          {edges.length} FK
        </Badge>
        {focusTable && (
          <Badge tone="violet" icon="eye">
            focus: {focusTable.name}
          </Badge>
        )}
        <div className="flex items-center gap-1">
          <Button size="xs" variant={viewMode === 'diagram' ? 'primary' : 'ghost'} onClick={() => setViewMode('diagram')}>Diagramme</Button>
          <Button size="xs" variant={viewMode === 'list' ? 'primary' : 'ghost'} onClick={() => setViewMode('list')}>Liste</Button>
        </div>
        <div className="w-48">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Rechercher table/colonne..." className="h-6 text-[11px]" />
        </div>
        <div className="flex items-center gap-1">
          <Button size="xs" variant="ghost" onClick={() => setZoom(z => Math.max(0.4, z - 0.1))}>-</Button>
          <span className="w-10 text-center font-mono text-[11px] text-dim">{Math.round(zoom*100)}%</span>
          <Button size="xs" variant="ghost" onClick={() => setZoom(z => Math.min(2, z + 0.1))}>+</Button>
          <Button size="xs" variant="ghost" onClick={() => setZoom(1)}>Reset</Button>
        </div>
        <label className="flex items-center gap-1 text-[11px] text-dim">
          <input type="checkbox" checked={showCols} onChange={(e) => setShowCols(e.target.checked)} />
          Colonnes
        </label>
        <div className="flex-1" />
        <Button size="xs" variant="ghost" icon="refresh" onClick={() => setPos(layout.p)}>
          Réinitialiser layout
        </Button>
      </div>

      {viewMode === 'list' ? (
        <div className="divide-y divide-line-soft">
          {filteredTables.map(t => {
            const cols = columnsByTable[t.id] || [];
            const inc = incoming(t.name);
            const out = outgoing(t.name);
            const isFav = favorites.includes(t.name);
            return (
              <div key={t.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-panel">
                <button onClick={() => toggleFav(t.name)} className={cn("text-[14px]", isFav ? "text-accent" : "text-dim")}>
                  {isFav ? "★" : "☆"}
                </button>
                <span className="font-mono text-[13px] text-fg">{t.name}</span>
                <Badge tone="neutral">{cols.length} colonnes</Badge>
                <Badge tone="accent">{inc.length + out.length} relations</Badge>
                {t.is_protected && <Badge tone="warn" icon="lock">Protégée</Badge>}
                <div className="flex-1" />
                <div className="text-[11px] text-dim">
                  {out.length > 0 && <span>Référence: {out.map(o => `${o.fromCol}→${o.to}.${o.toCol}`).join(', ')}</span>}
                  {inc.length > 0 && <span className="ml-2">Référencée par: {inc.map(i => `${i.from}.${i.fromCol}`).join(', ')}</span>}
                </div>
                <Button size="xs" variant="ghost" onClick={() => go({ v: "table", db: String(effectiveDbId), table: String(t.id), tab: "data" })}>
                  Ouvrir
                </Button>
              </div>
            );
          })}
          {filteredTables.length === 0 && <div className="p-6 text-center text-[12px] text-dim">Aucune table ne correspond.</div>}
        </div>
      ) : (
        <div
          ref={containerRef}
          className="grid-lines relative overflow-auto bg-bg"
          style={{ height: 720 }}
        >
          <div className="relative" style={{ width: width * zoom, height: height * zoom, transform: `scale(${zoom})`, transformOrigin: '0 0' }}>
            <svg className="pointer-events-none absolute inset-0" width={width} height={height}>
              {edges.map((e, i) => {
                const a = pos[e.from];
                const b = pos[e.to];
                if (!a || !b) return null;
                if (!filteredTables.some(t => t.name === e.from) || !filteredTables.some(t => t.name === e.to)) return null;
                const taCols = columnsByTable[e.fromId] || [];
                const tb = tables.find((t) => t.name === e.to);
                const tbCols = tb ? columnsByTable[tb.id] || [] : [];
                const ay = a.y + HEADER + taCols.findIndex((c) => c.name === e.fromCol) * ROW + ROW / 2;
                const by = b.y + HEADER + tbCols.findIndex((c) => c.name === e.toCol) * ROW + ROW / 2;
                const right = b.x > a.x + W - 20;
                const x1 = right ? a.x + W : a.x;
                const x2 = right ? b.x : b.x + W;
                const mx = (x1 + x2) / 2;
                const dim = related ? !(related.has(e.from) && related.has(e.to)) : false;
                return (
                  <g key={i} opacity={dim ? 0.15 : 1}>
                    <path
                      d={`M ${x1} ${ay} C ${mx} ${ay}, ${mx} ${by}, ${x2} ${by}`}
                      fill="none"
                      stroke={selected === e.from || selected === e.to ? "#5f92c4" : "#3d5f80"}
                      strokeWidth={selected === e.from || selected === e.to ? 2 : 1.25}
                    />
                    <circle cx={x1} cy={ay} r={3} fill="#0d0d10" stroke="#5f92c4" strokeWidth={1.2} />
                    <circle cx={x2} cy={by} r={3} fill="#0d0d10" stroke="#5f92c4" strokeWidth={1.2} />
                  </g>
                );
              })}
            </svg>

            {filteredTables.map((t) => {
              const p = pos[t.name] ?? { x: 0, y: 0 };
              const cols = columnsByTable[t.id] || [];
              const dim = related ? !related.has(t.name) : false;
              const isFav = favorites.includes(t.name);
              return (
                <div
                  key={t.id}
                  className={cn(
                    "absolute select-none rounded-lg border bg-panel shadow-[0_8px_24px_-12px_rgba(0,0,0,0.9)] transition-opacity",
                    selected === t.name ? "border-accent/70" : "border-line",
                    t.is_protected && selected !== t.name && "border-warn/40",
                    dim && "opacity-30",
                  )}
                  style={{ left: p.x, top: p.y, width: W }}
                >
                  <div
                    onMouseDown={(e) => {
                      const rect = containerRef.current?.getBoundingClientRect();
                      if (!rect) return;
                      setDrag({ name: t.name, dx: p.x - (e.clientX - rect.left)/zoom, dy: p.y - (e.clientY - rect.top)/zoom });
                      setSelected(t.name);
                    }}
                    className="flex cursor-grab items-center gap-1.5 rounded-t-lg border-b border-line bg-raised px-2.5 py-1.5 active:cursor-grabbing"
                  >
                    <Icon name="table" size={12} className="text-dim" />
                    <span className="flex-1 truncate font-mono text-[12px] font-medium text-fg">{t.name}</span>
                    <button onClick={(e) => { e.stopPropagation(); toggleFav(t.name); }} className={cn("text-[12px]", isFav ? "text-accent" : "text-dim")}>
                      {isFav ? "★" : "☆"}
                    </button>
                    {t.is_protected && <Icon name="lock" size={11} className="text-warn" />}
                    <span className="font-mono text-[10px] text-dim">{cols.length || t.columns_count}</span>
                  </div>
                  {showCols && (
                    <div className="py-1">
                      {cols.map((c) => (
                        <div
                          key={c.id}
                          className="flex items-center gap-1.5 px-2.5 py-[1.5px] font-mono text-[10.5px] leading-[16px]"
                        >
                          {c.primary_key ? (
                            <Icon name="key" size={9} className="shrink-0 text-xml" />
                          ) : c.foreign_key ? (
                            <Icon name="link" size={9} className="shrink-0 text-accent" />
                          ) : (
                            <span className="w-2.5 shrink-0" />
                          )}
                          <span className={cn("truncate", c.primary_key ? "text-fg" : "text-muted")}>{c.name}</span>
                          <span className="flex-1" />
                          <span className="shrink-0 text-[9.5px] text-dim">{c.type}</span>
                        </div>
                      ))}
                      {cols.length === 0 && <div className="px-2.5 py-1 text-[10px] text-dim">Aucune colonne</div>}
                    </div>
                  )}
                  <div className="flex items-center justify-between border-t border-line-soft px-2.5 py-1">
                    <span className="text-[9.5px] text-dim">
                      {focusTableId === t.id ? `Référencée par ${incoming(t.name).length} · Référence ${outgoing(t.name).length}` : `${cols.length} colonnes`}
                    </span>
                    <button
                      onClick={() => go({ v: "table", db: String(effectiveDbId), table: String(t.id), tab: "data" })}
                      className="text-[9.5px] text-accent hover:underline"
                    >
                      Ouvrir →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {focusTable && (
        <div className="border-t border-line bg-raised px-4 py-2.5">
          <p className="text-[12px] font-medium text-fg">Focus : {focusTable.name}</p>
          <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-muted">
            <span>Référence : {outgoing(focusTable.name).map(o => `${o.fromCol} → ${o.to}.${o.toCol}`).join(', ') || "Aucune"}</span>
            <span>Référencée par : {incoming(focusTable.name).map(i => `${i.from}.${i.fromCol}`).join(', ') || "Aucune"}</span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 border-t border-line bg-raised px-3 py-1.5 text-[11px] text-dim">
        <Icon name="info" size={11} />
        Diagramme basé sur schéma XML réel · Glisser-déposer · Zoom · Favoris ★ · Liste/Diagramme · Focus table
      </div>
    </div>
  );
}
