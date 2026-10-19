import { useEffect, useState } from "react";
import { Icon } from "../../components/Icon";
import {
  Badge,
  Button,
  Panel,
  SectionHeader,
  Switch,
  Tabs,
  useToast,
} from "../../components/ui";
import { useStore } from "../../store";
import { AddColumnModal, ConfirmModal, EditColumnModal } from "../../components/modals";

export function StructureTab({ dbId, tableId }: { dbId: string; tableId: number }) {
  const { tables, columns, columnsLoading, columnsError, dropColumn, setProtected, fetchColumns } = useStore();
  const table = tables.find(t => t.id === tableId);
  const toast = useToast();
  const [view, setView] = useState<"cards" | "table">("cards");
  const [addOpen, setAddOpen] = useState(false);
  const [editCol, setEditCol] = useState<any | null>(null);
  const [drop, setDrop] = useState<any | null>(null);

  // Écouter refresh colonnes après édition
  useEffect(() => {
    const h = () => fetchColumns(tableId);
    window.addEventListener("xf-refresh-columns", h);
    return () => window.removeEventListener("xf-refresh-columns", h);
  }, [tableId, fetchColumns]);

  if (!table) return <div className="p-4 text-[12px] text-dim">Table introuvable.</div>;

  if (columnsLoading) {
    return <div className="flex items-center gap-2 p-4 text-[12px] text-muted"><span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />Chargement colonnes...</div>;
  }

  if (columnsError) {
    return (
      <div className="rounded-lg border border-danger/30 bg-danger-soft p-4">
        <p className="text-[13px] font-medium text-danger">Impossible de charger les colonnes.</p>
        <p className="mt-1 text-[12px] text-muted">{columnsError}</p>
        <Button size="sm" className="mt-3" onClick={() => fetchColumns(tableId)}>Réessayer</Button>
      </div>
    );
  }

  const indexes = columns.filter((c) => c.primary_key || c.unique || c.index);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Tabs
          size="sm"
          tabs={[
            { id: "cards" as const, label: "Colonnes", icon: "columns", count: columns.length },
            { id: "table" as const, label: "Vue table", icon: "table" },
          ]}
          value={view}
          onChange={setView as any}
        />
        <div className="flex-1" />
        <Button
          size="sm"
          icon={table.is_protected ? "unlock" : "lock"}
          variant={table.is_protected ? "default" : "ghost"}
          onClick={() => setProtected(dbId, table.id, !table.is_protected)}
        >
          {table.is_protected ? "Déverrouiller" : "Protéger"}
        </Button>
        <Button size="sm" variant="primary" icon="plus" onClick={() => setAddOpen(true)}>
          Ajouter colonne
        </Button>
      </div>

      {view === "cards" ? (
        <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {columns.map((c) => (
            <div
              key={c.id}
              className="group relative rounded-lg border border-line bg-surface p-3 transition-colors hover:border-[#363641]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    {c.primary_key ? (
                      <Icon name="key" size={12} className="shrink-0 text-xml" />
                    ) : c.foreign_key ? (
                      <Icon name="link" size={12} className="shrink-0 text-accent" />
                    ) : null}
                    <span className="truncate font-mono text-[13px] font-medium text-fg">{c.name}</span>
                  </div>
                  <span className="mt-1 block font-mono text-[11.5px] text-accent">{c.type}{c.length && c.length !== '-' ? `(${c.length})` : ''}</span>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                  <Button size="xs" variant="ghost" onClick={() => setEditCol(c)}>
                    <Icon name="pencil" size={12} />
                  </Button>
                  <Button size="xs" variant="ghost" onClick={() => setDrop(c)}>
                    <Icon name="trash" size={12} />
                  </Button>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {c.primary_key && <Badge tone="xml" icon="key">PK</Badge>}
                {c.auto_increment && <Badge tone="xml" icon="bolt">AI</Badge>}
                {!c.nullable && <Badge tone="neutral" mono>NN</Badge>}
                {c.unique && <Badge tone="violet" mono>UNIQUE</Badge>}
                {c.index && !c.primary_key && <Badge tone="accent" icon="index">INDEX</Badge>}
                {c.foreign_key && c.references && <Badge tone="accent" icon="link">FK → {c.references}</Badge>}
              </div>
              <div className="mt-2.5 border-t border-line-soft pt-2 text-[11px] text-dim">
                Défaut: <span className="font-mono text-muted">{c.default ?? "NULL"}</span>
                {c.comment && <span className="mt-1 block">{c.comment}</span>}
              </div>
            </div>
          ))}
          {columns.length === 0 && <div className="col-span-full p-6 text-center text-[12px] text-dim">Aucune colonne. Ajoutez votre première colonne.</div>}
        </div>
      ) : (
        <div className="mt-3 overflow-hidden rounded-lg border border-line bg-surface">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="bg-raised">
                {["Colonne", "Type", "Nullable", "Défaut", "Unique", "PK", "Auto inc", "FK", ""].map((h) => (
                  <th
                    key={h}
                    className="border-b border-line px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-dim"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {columns.map((c) => (
                <tr key={c.id} className="group transition-colors hover:bg-panel">
                  <td className="border-b border-line-soft px-3 py-1.5 font-mono text-[12px] text-fg">{c.name}</td>
                  <td className="border-b border-line-soft px-3 py-1.5 font-mono text-[11.5px] text-accent">{c.type}{c.length !== '-' ? `(${c.length})` : ''}</td>
                  <td className="border-b border-line-soft px-3 py-1.5">
                    {c.nullable ? <span className="text-dim">YES</span> : <span className="text-fg">NO</span>}
                  </td>
                  <td className="border-b border-line-soft px-3 py-1.5 font-mono text-[11.5px] text-muted">{c.default ?? "NULL"}</td>
                  <td className="border-b border-line-soft px-3 py-1.5">
                    {c.unique ? <Icon name="check" size={13} className="text-ok" /> : <Icon name="minus" size={13} className="text-dim" />}
                  </td>
                  <td className="border-b border-line-soft px-3 py-1.5">
                    {c.primary_key ? <Icon name="check" size={13} className="text-xml" /> : <Icon name="minus" size={13} className="text-dim" />}
                  </td>
                  <td className="border-b border-line-soft px-3 py-1.5">
                    {c.auto_increment ? <Icon name="check" size={13} className="text-xml" /> : <Icon name="minus" size={13} className="text-dim" />}
                  </td>
                  <td className="border-b border-line-soft px-3 py-1.5 font-mono text-[11.5px] text-muted">
                    {c.references || "—"}
                  </td>
                  <td className="border-b border-line-soft px-2 py-1.5">
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                      <Button size="xs" variant="ghost" onClick={() => setEditCol(c)}>
                        <Icon name="pencil" size={12} />
                      </Button>
                      <Button size="xs" variant="ghost" onClick={() => setDrop(c)}>
                        <Icon name="trash" size={12} />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Panel padding={false}>
          <div className="border-b border-line px-4 py-2.5">
            <SectionHeader title="Index" description={`${indexes.length} index déclarés`} />
          </div>
          <ul className="divide-y divide-line-soft">
            {indexes.map((c) => (
              <li key={c.id} className="flex items-center gap-2.5 px-4 py-2">
                <Icon name="index" size={12} className={c.primary_key ? "text-xml" : "text-dim"} />
                <span className="font-mono text-[12px] text-fg">
                  {c.primary_key ? "PRIMARY" : c.unique ? `uq_${table.name}_${c.name}` : `idx_${table.name}_${c.name}`}
                </span>
                <span className="text-[11.5px] text-dim">({c.name})</span>
                <div className="flex-1" />
                <Badge tone={c.primary_key ? "xml" : c.unique ? "violet" : "neutral"}>{c.primary_key ? "PRIMARY" : c.unique ? "UNIQUE" : "INDEX"}</Badge>
              </li>
            ))}
            {indexes.length === 0 && <li className="px-4 py-4 text-[12px] text-dim">Aucun index déclaré.</li>}
          </ul>
        </Panel>

        <Panel>
          <SectionHeader title="Options table" />
          <div className="mt-3 space-y-3.5">
            {[
              { label: "Moteur", value: "XMLForge (XML natif)" },
              { label: "Commentaire", value: table.description || table.comment || "—" },
              { label: "Créée", value: table.created_at ? new Date(table.created_at).toLocaleString() : "—" },
              { label: "Mise à jour", value: table.updated_at ? new Date(table.updated_at).toLocaleString() : "—" },
              { label: "Colonnes", value: String(columns.length) },
              { label: "Statut", value: table.status },
            ].map((o) => (
              <div key={o.label} className="flex items-start justify-between gap-4 text-[12px]">
                <span className="text-dim">{o.label}</span>
                <span className="text-right font-mono text-[11.5px] text-muted">{o.value}</span>
              </div>
            ))}
            <div className="border-t border-line pt-3">
              <Switch
                checked={!!table.is_protected}
                onChange={(v) => setProtected(dbId, table.id, v)}
                label="Protection écriture"
                description="Bloque INSERT / UPDATE / DELETE jusqu'au déverrouillage."
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <Button
              size="sm"
              icon="download"
              onClick={async () => {
                try {
                  const { xmlService } = await import("../../api/xml");
                  await xmlService.exportTableXml(table.id);
                  toast({ kind: "success", title: "Structure exportée", detail: `${table.name}.xml` });
                } catch (e: any) {
                  toast({ kind: "error", title: "Erreur export", detail: e.message });
                }
              }}
            >
              Exporter structure
            </Button>
            <Button size="sm" variant="ghost" icon="refresh" onClick={() => fetchColumns(table.id)}>
              Actualiser
            </Button>
          </div>
        </Panel>
      </div>

      <AddColumnModal open={addOpen} onClose={() => setAddOpen(false)} dbId={dbId} tableId={table.id} />
      <EditColumnModal open={!!editCol} onClose={() => setEditCol(null)} column={editCol} />
      <ConfirmModal
        open={!!drop}
        onClose={() => setDrop(null)}
        title="Supprimer colonne"
        description={`Supprimer la colonne ${drop?.name} (${drop?.type}) de la table ${table.name} ?`}
        confirmLabel="Supprimer"
        danger
        onConfirm={() => drop && dropColumn(drop.id)}
      />
    </div>
  );
}
