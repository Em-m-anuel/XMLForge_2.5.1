import { useEffect, useState, useCallback } from "react";
import { Icon } from "../../components/Icon";
import {
  Badge,
  Button,
  Checkbox,
  Dropdown,
  EmptyState,
  ErrorState,
  IconButton,
  Input,
  LoadingState,
  MenuItem,
  MenuLabel,
  Select,
  useToast,
} from "../../components/ui";
import { cn } from "../../utils/cn";
import { useStore } from "../../store";
import { RowModal } from "../../components/modals";

const PAGE_SIZES = [15, 25, 50, 100];

export function DataTab({ dbId, tableId }: { dbId: string; tableId: number }) {
  // ---- TOUS LES HOOKS EN PREMIER (ordre stable) ----
  const { columns, rows, rowsTotal, rowsLoading, rowsError, fetchRows, deleteRows, go, tables, updateCell } = useStore();
  const table = tables.find(t => t.id === tableId);
  const toast = useToast();

  const [q, setQ] = useState("");
  const [filterCol, setFilterCol] = useState("");
  const [filterVal, setFilterVal] = useState("");
  const [sortCol, setSortCol] = useState("");
  const [sortDir, setSortDir] = useState<"ASC" | "DESC">("ASC");
  const [hidden, setHidden] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<number[]>([]);
  const [rowModal, setRowModal] = useState<{ open: boolean; row: any | null }>({ open: false, row: null });
  const [editing, setEditing] = useState<{ rowId: number; col: string; value: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [focusedCell, setFocusedCell] = useState<{ rowId: number; col: string } | null>(null);

  // Effet : init filterCol depuis première colonne
  useEffect(() => {
    if (columns.length && !filterCol) {
      setFilterCol(columns[0]?.name || "");
    }
  }, [columns, filterCol]);

  // Écouter événement nouveau row depuis TableWorkspace
  useEffect(() => {
    const h = () => setRowModal({ open: true, row: null });
    window.addEventListener("xf-new-row", h);
    return () => window.removeEventListener("xf-new-row", h);
  }, []);

  // Charger lignes
  useEffect(() => {
    if (!tableId) return;
    fetchRows(tableId, {
      limit: pageSize,
      offset: (page - 1) * pageSize,
      search: q.trim(),
      sort: sortCol,
      order: sortDir,
      filters: filterCol && filterVal ? { [filterCol]: filterVal } : {},
    });
  }, [tableId, page, pageSize, q, sortCol, sortDir, filterCol, filterVal, fetchRows]);

  // Derived values (pas de hooks)
  const visibleCols = columns.filter((c) => !hidden.includes(c.name));
  const pages = Math.max(1, Math.ceil(rowsTotal / pageSize));
  const current = Math.min(page, pages);
  const allOnPageSelected = rows.length > 0 && rows.every((r) => selected.includes(r.id));

  const startEdit = useCallback((rowId: number, col: string, currentValue: any) => {
    if (table?.is_protected) {
      toast({ kind: "error", title: "Table protégée", detail: "Déverrouillez pour modifier" });
      return;
    }
    const colDef = columns.find(c => c.name === col);
    if (colDef?.auto_increment) {
      toast({ kind: "info", title: "Colonne auto-incrément", detail: "Non modifiable" });
      return;
    }
    setFocusedCell({ rowId, col });
    setEditing({ rowId, col, value: currentValue === null || currentValue === undefined ? "" : String(currentValue) });
  }, [table, columns, toast]);

  const saveEdit = useCallback(async (next?: { rowId: number; col: string } | null) => {
    if (!editing) return;
    setSaving(true);
    try {
      const colDef = columns.find(c => c.name === editing.col);
      const val = editing.value === "" && colDef?.nullable ? null : editing.value;
      await updateCell(tableId, editing.rowId, { [editing.col]: val });
      setEditing(null);
      if (next) {
        setFocusedCell(next);
      }
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur sauvegarde", detail: e.message });
    } finally {
      setSaving(false);
    }
  }, [editing, columns, tableId, updateCell, toast]);

  const cancelEdit = useCallback(() => setEditing(null), []);

  const moveFocus = useCallback((dir: 'next' | 'prev' | 'up' | 'down') => {
    if (!focusedCell || !visibleCols.length || !rows.length) return;
    const colIdx = visibleCols.findIndex(c => c.name === focusedCell.col);
    const rowIdx = rows.findIndex(r => r.id === focusedCell.rowId);
    let newColIdx = colIdx;
    let newRowIdx = rowIdx;
    if (dir === 'next') {
      newColIdx = colIdx + 1;
      if (newColIdx >= visibleCols.length) {
        newColIdx = 0;
        newRowIdx = Math.min(rows.length - 1, rowIdx + 1);
      }
    } else if (dir === 'prev') {
      newColIdx = colIdx - 1;
      if (newColIdx < 0) {
        newColIdx = visibleCols.length - 1;
        newRowIdx = Math.max(0, rowIdx - 1);
      }
    } else if (dir === 'up') {
      newRowIdx = Math.max(0, rowIdx - 1);
    } else if (dir === 'down') {
      newRowIdx = Math.min(rows.length - 1, rowIdx + 1);
    }
    const newCol = visibleCols[newColIdx];
    const newRow = rows[newRowIdx];
    if (newCol && newRow) {
      setFocusedCell({ rowId: newRow.id, col: newCol.name });
    }
  }, [focusedCell, visibleCols, rows]);

  // Navigation clavier — DOIT être avant tout return conditionnel (hook stable)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (editing) return;
      if (!focusedCell) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); moveFocus('next'); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); moveFocus('prev'); }
      if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus('up'); }
      if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus('down'); }
      if (e.key === 'Tab') {
        e.preventDefault();
        moveFocus(e.shiftKey ? 'prev' : 'next');
      }
      if (e.key === 'Enter' && focusedCell) {
        const row = rows.find(r => r.id === focusedCell.rowId);
        if (row) startEdit(focusedCell.rowId, focusedCell.col, row.data[focusedCell.col]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focusedCell, editing, visibleCols, rows, moveFocus, startEdit]);

  // ---- FIN DES HOOKS, début des guards conditionnels ----
  if (!table) {
    return <LoadingState label="Chargement table..." />;
  }

  if (rowsLoading && rows.length === 0) return <LoadingState label={`Chargement des lignes de ${table.name}...`} />;

  if (rowsError)
    return (
      <ErrorState
        title="Impossible de charger les lignes"
        description={rowsError}
        onRetry={() => fetchRows(tableId, { limit: pageSize, offset: (page - 1) * pageSize })}
      />
    );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-56">
          <Input icon="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Rechercher..." />
        </div>

        <Dropdown
          width="w-72"
          trigger={({ toggle }) => (
            <Button size="sm" icon="filter" onClick={toggle} variant={filterVal ? "primary" : "default"}>
              {filterVal ? `Filtre: ${filterCol}` : "Filtrer"}
            </Button>
          )}
        >
          {(close) => (
            <div className="p-1.5">
              <MenuLabel>Colonne</MenuLabel>
              <Select
                className="w-full"
                value={filterCol}
                onChange={(e) => setFilterCol(e.target.value)}
              >
                {columns.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <MenuLabel className="pt-2">Valeur</MenuLabel>
              <Input
                value={filterVal}
                onChange={(e) => setFilterVal(e.target.value)}
                placeholder="valeur"
              />
              <div className="mt-2.5 flex justify-between gap-2">
                <Button size="xs" variant="ghost" onClick={() => { setFilterCol(""); setFilterVal(""); close(); }}>
                  Effacer
                </Button>
                <Button size="xs" variant="primary" onClick={() => { setPage(1); close(); }}>
                  Appliquer
                </Button>
              </div>
            </div>
          )}
        </Dropdown>

        <Dropdown
          width="w-56"
          trigger={({ toggle }) => (
            <Button size="sm" icon="sort" onClick={toggle} variant={sortCol ? "primary" : "default"}>
              {sortCol ? `Tri: ${sortCol} ${sortDir === "ASC" ? "↑" : "↓"}` : "Trier"}
            </Button>
          )}
        >
          {(close) => (
            <>
              <MenuLabel>Trier par</MenuLabel>
              {columns.map((c) => (
                <MenuItem
                  key={c.name}
                  icon={sortCol === c.name ? (sortDir === "ASC" ? "chevronUp" : "chevronDown") : undefined}
                  onClick={() => {
                    if (sortCol === c.name) {
                      setSortDir(d => d === "ASC" ? "DESC" : "ASC");
                    } else {
                      setSortCol(c.name);
                      setSortDir("ASC");
                    }
                    close();
                  }}
                >
                  {c.name}
                </MenuItem>
              ))}
            </>
          )}
        </Dropdown>

        <Dropdown
          width="w-52"
          trigger={({ toggle }) => (
            <Button size="sm" icon="columns" onClick={toggle}>
              Colonnes ({visibleCols.length}/{columns.length})
            </Button>
          )}
        >
          {() => (
            <>
              <MenuLabel>Colonnes visibles</MenuLabel>
              {columns.map((c) => (
                <div key={c.name} className="px-2.5 py-1">
                  <Checkbox
                    checked={!hidden.includes(c.name)}
                    label={c.name}
                    onChange={(v) => setHidden((h) => (v ? h.filter((x) => x !== c.name) : [...h, c.name]))}
                  />
                </div>
              ))}
            </>
          )}
        </Dropdown>

        <div className="flex-1" />

        {selected.length > 0 && (
          <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-2 py-1">
            <span className="text-[11.5px] text-danger">{selected.length} sélectionnée(s)</span>
            <Button
              size="xs"
              variant="danger"
              icon="trash"
              onClick={() => {
                if (table.is_protected) {
                  toast({ kind: "error", title: "Table protégée" });
                  return;
                }
                deleteRows(tableId, selected);
                setSelected([]);
              }}
            >
              Supprimer
            </Button>
          </div>
        )}

        <IconButton
          icon="refresh"
          label="Actualiser"
          onClick={() => fetchRows(tableId, { limit: pageSize, offset: (page - 1) * pageSize, search: q })}
        />
        <Button
          size="sm"
          variant="primary"
          icon="plus"
          onClick={() => {
            if (table.is_protected) {
              toast({ kind: "error", title: "Table protégée" });
              return;
            }
            setRowModal({ open: true, row: null });
          }}
        >
          Ajouter ligne
        </Button>
      </div>

      <div className="mt-2 text-[11.5px] text-dim">
        {rowsTotal.toLocaleString()} ligne{rowsTotal > 1 ? "s" : ""} {q && `(recherche "${q}")`} · Double-clic pour éditer · Entrée pour sauvegarder · Esc pour annuler
      </div>

      <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="bg-raised">
                <th className="w-9 border-b border-line px-2 py-1.5">
                  <Checkbox
                    checked={allOnPageSelected}
                    partial={rows.some((r) => selected.includes(r.id)) && !allOnPageSelected}
                    onChange={(v) =>
                      setSelected((s) => (v ? [...new Set([...s, ...rows.map((r) => r.id)])] : s.filter((id) => !rows.some((r) => r.id === id))))
                    }
                    label=""
                  />
                </th>
                {visibleCols.map((c) => (
                  <th
                    key={c.name}
                    className="group min-w-[120px] cursor-pointer border-b border-line px-3 py-1.5 text-left hover:bg-panel"
                    onClick={() =>
                      setSortCol((prev) => {
                        if (prev === c.name) {
                          setSortDir(d => d === "ASC" ? "DESC" : "ASC");
                          return prev;
                        }
                        setSortDir("ASC");
                        return c.name;
                      })
                    }
                  >
                    <span className="flex items-center gap-1.5">
                      {c.primary_key && <Icon name="key" size={10} className="text-xml" />}
                      {c.foreign_key && <Icon name="link" size={10} className="text-accent" />}
                      <span className="font-mono text-[11px] font-medium uppercase tracking-wide text-fg/85">{c.name}</span>
                      {sortCol === c.name && <Icon name={sortDir === "ASC" ? "chevronUp" : "chevronDown"} size={11} className="text-accent" />}
                      <span className="ml-auto font-mono text-[10px] text-dim opacity-0 group-hover:opacity-100">
                        {c.type}
                      </span>
                    </span>
                  </th>
                ))}
                <th className="w-16 border-b border-line px-2 py-1.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className={cn("group transition-colors hover:bg-panel", selected.includes(r.id) && "bg-accent-soft/30")}
                >
                  <td className="border-b border-line-soft px-2 py-1.5">
                    <Checkbox
                      checked={selected.includes(r.id)}
                      onChange={(v) => setSelected((s) => (v ? [...s, r.id] : s.filter((x) => x !== r.id)))}
                      label=""
                    />
                  </td>
                  {visibleCols.map((c) => {
                    const isEditing = editing?.rowId === r.id && editing?.col === c.name;
                    const isFocused = focusedCell?.rowId === r.id && focusedCell?.col === c.name;
                    return (
                      <td key={c.name} className={cn("max-w-[300px] border-b border-line-soft px-3 py-1.5", isFocused && "bg-accent-soft/20 ring-1 ring-accent/30")} onClick={() => setFocusedCell({ rowId: r.id, col: c.name })} onDoubleClick={() => startEdit(r.id, c.name, r.data[c.name])}>
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <Input
                              autoFocus
                              value={editing.value}
                              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  const colIdx = visibleCols.findIndex(c => c.name === editing.col);
                                  const nextCol = visibleCols[colIdx + 1];
                                  if (nextCol) {
                                    saveEdit({ rowId: editing.rowId, col: nextCol.name });
                                    setTimeout(() => {
                                      const row = rows.find(r => r.id === editing.rowId);
                                      if (row) startEdit(editing.rowId, nextCol.name, row.data[nextCol.name]);
                                    }, 100);
                                  } else {
                                    saveEdit();
                                  }
                                }
                                if (e.key === 'Escape') cancelEdit();
                                if (e.key === 'Tab') {
                                  e.preventDefault();
                                  const dir = e.shiftKey ? 'prev' : 'next';
                                  const colIdx = visibleCols.findIndex(c => c.name === editing.col);
                                  const rowIdx = rows.findIndex(r => r.id === editing.rowId);
                                  let newColIdx = dir === 'next' ? colIdx + 1 : colIdx - 1;
                                  let newRowIdx = rowIdx;
                                  if (newColIdx >= visibleCols.length) {
                                    newColIdx = 0;
                                    newRowIdx = Math.min(rows.length - 1, rowIdx + 1);
                                  }
                                  if (newColIdx < 0) {
                                    newColIdx = visibleCols.length - 1;
                                    newRowIdx = Math.max(0, rowIdx - 1);
                                  }
                                  const newCol = visibleCols[newColIdx];
                                  const newRow = rows[newRowIdx];
                                  if (newCol && newRow) {
                                    saveEdit({ rowId: newRow.id, col: newCol.name });
                                    setTimeout(() => startEdit(newRow.id, newCol.name, newRow.data[newCol.name]), 100);
                                  }
                                }
                              }}
                              className="h-6 text-[11px]"
                              disabled={saving}
                            />
                            <Button size="xs" variant="primary" loading={saving} onClick={() => saveEdit()}>✓</Button>
                            <Button size="xs" variant="ghost" onClick={cancelEdit}>✕</Button>
                          </div>
                        ) : r.data[c.name] === null || r.data[c.name] === undefined ? (
                          <Badge tone="neutral" mono>
                            NULL
                          </Badge>
                        ) : c.foreign_key && c.references ? (
                          <button
                            onClick={() => {
                              const refTable = c.references?.split('.')[0];
                              const target = tables.find(t => t.name === refTable);
                              if (target) go({ v: "table", db: dbId, table: String(target.id), tab: "data" });
                            }}
                            className="flex items-center gap-1 font-mono text-[11.5px] text-accent hover:underline"
                          >
                            {String(r.data[c.name])}
                            <Icon name="arrowRight" size={10} />
                          </button>
                        ) : (
                          <span className="block truncate font-mono text-[11.5px] text-fg/90">{String(r.data[c.name])}</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="border-b border-line-soft px-2 py-1.5">
                    <div className="flex justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <IconButton icon="pencil" label="Modifier" onClick={() => setRowModal({ open: true, row: r })} />
                      <IconButton icon="trash" label="Supprimer" tone="danger" onClick={() => deleteRows(tableId, [r.id])} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {rows.length === 0 && (
          <EmptyState
            icon="rows"
            title="Aucune donnée"
            description="Cette table ne contient aucune ligne."
            action={
              <Button size="sm" variant="primary" icon="plus" onClick={() => setRowModal({ open: true, row: null })}>
                Ajouter ligne
              </Button>
            }
          />
        )}

        <div className="flex flex-wrap items-center gap-3 border-t border-line bg-raised px-3 py-1.5">
          <span className="text-[11.5px] text-dim">
            {rowsTotal === 0 ? "0" : `${(current - 1) * pageSize + 1}–${Math.min(current * pageSize, rowsTotal)}`} sur {rowsTotal.toLocaleString()}
          </span>
          <Select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="h-6.5">
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>
                {s} / page
              </option>
            ))}
          </Select>
          <div className="flex-1" />
          <div className="flex items-center gap-1">
            <IconButton icon="chevronRight" label="Précédente" className="rotate-180" disabled={current === 1} onClick={() => setPage(current - 1)} />
            <span className="px-2 font-mono text-[11.5px] text-dim">Page {current} / {pages}</span>
            <IconButton icon="chevronRight" label="Suivante" disabled={current === pages} onClick={() => setPage(current + 1)} />
          </div>
        </div>
      </div>

      {rowModal.open && (
        <RowModal open={rowModal.open} onClose={() => setRowModal({ open: false, row: null })} tableId={tableId} columns={columns} row={rowModal.row} />
      )}
    </div>
  );
}
