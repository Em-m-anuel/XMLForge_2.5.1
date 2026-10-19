import { useEffect, useState } from "react";
import { Button, Field, Input, Modal, Select, Textarea, useToast } from "./ui";
import { Icon } from "./Icon";
import { cn } from "../utils/cn";
import { useStore } from "../store";
import type { Database } from "../api/databases";
import type { Table } from "../api/tables";
import type { Column } from "../api/columns";
import type { Row } from "../api/rows";
import { columnService } from "../api/columns";
import { permissionService } from "../api/permissions";

const TYPES = [
  "INT", "BIGINT", "SMALLINT", "TINYINT", "DECIMAL", "VARCHAR", "CHAR", "TEXT", "DATE", "DATETIME", "BOOLEAN", "FLOAT", "DOUBLE", "BLOB", "JSON"
];

/* ------------------------------------------------------------------ confirm */

export function ConfirmModal({
  open,
  onClose,
  title,
  description,
  confirmLabel = "Confirmer",
  danger,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      subtitle={description}
      icon={danger ? "alert" : "info"}
      width="max-w-md"
      level="critical"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-[12.5px] leading-relaxed text-muted">
        Cette action sera appliquée au document XML de la base puis propagée au moteur natif.
      </p>
    </Modal>
  );
}

/* ------------------------------------------------------------ create database */

export function CreateDatabaseModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { createDatabase } = useStore();
  const toast = useToast();
  const [name, setName] = useState("");
  const [scope, setScope] = useState<'PERSONAL' | 'COMMON'>('PERSONAL');
  const [desc, setDesc] = useState("");
  const [commonPerm, setCommonPerm] = useState('VIEW');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) {
      toast({ kind: "error", title: "Nom requis", detail: "Indiquez un nom de base" });
      return;
    }
    setBusy(true);
    try {
      await createDatabase(name.trim(), scope, desc.trim(), scope === 'COMMON' ? commonPerm : null);
      setName("");
      setDesc("");
      onClose();
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur création", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nouvelle base"
      subtitle="Crée un nouveau document XML géré par le moteur natif"
      icon="database"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button data-testid="create-db-confirm" variant="primary" loading={busy} onClick={submit}>
            Créer la base
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Nom" required>
          <Input data-testid="new-db-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Bibliotheque" />
        </Field>
        <Field label="Portée" hint="PERSONAL : visible par le propriétaire. COMMON : visible par tous les utilisateurs actifs.">
          <div className="grid grid-cols-2 gap-2">
            {(["PERSONAL", "COMMON"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={cn(
                  "rounded-md border px-3 py-2 text-left transition-colors",
                  scope === s ? "border-accent/60 bg-accent-soft" : "border-line bg-surface hover:border-[#363641]",
                )}
              >
                <span className="block text-[12.5px] font-medium text-fg">{s === "PERSONAL" ? "Personnelle" : "Commune"}</span>
                <span className="mt-0.5 block text-[11px] text-muted">
                  {s === "PERSONAL" ? "Privée, propriétaire unique" : "Partagée, utilisateurs actifs"}
                </span>
              </button>
            ))}
          </div>
        </Field>
        {scope === 'COMMON' && (
          <Field label="Permission collective">
            <Select value={commonPerm} onChange={(e) => setCommonPerm(e.target.value)} className="w-full">
              <option value="VIEW">VIEW — lecture pour tous</option>
              <option value="EDIT">EDIT — lecture + écriture</option>
              <option value="MANAGE">MANAGE — gestion complète</option>
            </Select>
          </Field>
        )}
        <Field label="Description">
          <Textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Optionnel" />
        </Field>
      </div>
    </Modal>
  );
}

/* -------------------------------------------------------------- edit database */

export function EditDatabaseModal({
  open,
  onClose,
  dbId,
}: {
  open: boolean;
  onClose: () => void;
  dbId: string;
}) {
  const { dbs, updateDatabase, canManageDb } = useStore();
  const db = dbs.find((d) => String(d.id) === dbId) as Database | undefined;
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [scope, setScope] = useState<'PERSONAL' | 'COMMON'>('PERSONAL');
  const [commonPerm, setCommonPerm] = useState<'VIEW' | 'EDIT' | 'MANAGE'>('VIEW');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !db) return;
    setName(db.name);
    setDesc(db.description ?? "");
    setScope((db.scope as any) || 'PERSONAL');
    setCommonPerm((db.common_permission as any) || 'VIEW');
    setError(null);
    setBusy(false);
  }, [open, db]);

  const allowed = db ? canManageDb(db) : false;
  const isAdmin = (db?.access?.can_admin || db?.is_owner) ? true : false;

  const submit = async () => {
    if (!db) return;
    if (!allowed) {
      setError("Permission refusée. Owner ou Manage requis.");
      return;
    }
    if (!name.trim()) {
      setError("Le nom de la base est requis.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // Construire payload avec scope si admin
      const payload: any = { name: name.trim(), description: desc.trim() };
      if (isAdmin) {
        payload.scope = scope;
        if (scope === 'COMMON') {
          payload.common_permission = commonPerm;
        }
      }
      const res = await updateDatabase(dbId, payload);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Modifier la base"
      subtitle={db ? `${db.scope} · propriétaire ${db.owner_name || db.creator_name} · v${db.document_version}` : undefined}
      icon="pencil"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" loading={busy} disabled={!allowed} onClick={submit}>
            Enregistrer
          </Button>
        </>
      }
    >
      {!db ? (
        <p className="text-[12.5px] text-muted">Base introuvable.</p>
      ) : (
        <div className="space-y-3">
          {!allowed && (
            <p className="flex items-center gap-1.5 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] text-warn">
              <Icon name="lock" size={12} />
              Lecture seule — Owner ou Manage requis.
            </p>
          )}
          <Field label="Nom de la base" required>
            <Input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!allowed}
              placeholder="Bibliotheque"
            />
          </Field>
          <Field label="Description">
            <Textarea
              rows={2}
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              disabled={!allowed}
              placeholder="Optionnel"
            />
          </Field>
          {isAdmin && (
            <>
              <Field label="Portée (scope)" hint="PERSONAL : privée, propriétaire unique. COMMON : partagée, visible par tous les utilisateurs actifs. Changement PERSONAL↔COMMON autorisé avec permission admin.">
                <div className="grid grid-cols-2 gap-2">
                  {(["PERSONAL", "COMMON"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setScope(s)}
                      disabled={!isAdmin}
                      className={cn(
                        "rounded-md border px-3 py-2 text-left transition-colors",
                        scope === s ? "border-accent/60 bg-accent-soft" : "border-line bg-surface hover:border-[#363641]",
                        !isAdmin && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      <span className="block text-[12.5px] font-medium text-fg">{s === "PERSONAL" ? "Personnelle" : "Commune"}</span>
                      <span className="mt-0.5 block text-[11px] text-muted">
                        {s === "PERSONAL" ? "Privée" : "Partagée"}
                      </span>
                    </button>
                  ))}
                </div>
              </Field>
              {scope === 'COMMON' && (
                <Field label="Permission collective">
                  <Select value={commonPerm} onChange={(e) => setCommonPerm(e.target.value as any)} className="w-full" disabled={!isAdmin}>
                    <option value="VIEW">VIEW — lecture pour tous</option>
                    <option value="EDIT">EDIT — lecture + écriture</option>
                    <option value="MANAGE">MANAGE — gestion complète</option>
                  </Select>
                </Field>
              )}
            </>
          )}
          {!isAdmin && (
            <div className="grid grid-cols-2 gap-2 rounded-md border border-line-soft bg-surface px-3 py-2 text-[11.5px]">
              <div>
                <p className="text-dim">Scope</p>
                <p className="mt-0.5 font-mono text-muted">{db.scope}</p>
              </div>
              <div>
                <p className="text-dim">Version</p>
                <p className="mt-0.5 font-mono text-muted">{db.document_version}</p>
              </div>
            </div>
          )}
          {error && (
            <p className="flex items-center gap-1.5 text-[12px] text-danger">
              <Icon name="alert" size={12} />
              {error}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}

/* --------------------------------------------------------------- create table */

export function CreateTableModal({
  open,
  onClose,
  dbId,
}: {
  open: boolean;
  onClose: () => void;
  dbId: string;
}) {
  const { createTable, tables } = useStore();
  const toast = useToast();
  const [name, setName] = useState("");
  const [withId, setWithId] = useState(true);
  const [isProtected, setIsProtected] = useState(false);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) {
      toast({ kind: "error", title: "Nom requis" });
      return;
    }
    if (tables.some((t) => t.name === name.trim())) {
      toast({ kind: "error", title: "Table déjà existante", detail: `${name} existe déjà` });
      return;
    }
    if (isProtected && !key.trim()) {
      toast({ kind: "error", title: "Clé requise", detail: "Le backend ne génère pas automatiquement la clé" });
      return;
    }
    setBusy(true);
    try {
      const table = await createTable(dbId, name.trim(), {
        is_protected: isProtected,
        file_identifier: isProtected ? key.trim() : null,
        description: "",
      });
      if (withId) {
        try {
          await columnService.create({
            name: "id",
            type: "INT",
            length: "11",
            nullable: false,
            primary_key: true,
            auto_increment: true,
            unique: false,
            foreign_key: false,
            index: false,
            table_id: table.id,
          });
          toast({ kind: "success", title: "Colonne id créée", detail: "PK AUTO_INCREMENT" });
        } catch (e: any) {
          toast({ kind: "error", title: "Erreur colonne id", detail: e.message });
        }
      }
      setName("");
      setKey("");
      setIsProtected(false);
      onClose();
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur création table", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Créer une table"
      subtitle={`Base ${dbId} · structure définie dans le document XML`}
      icon="table"
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button data-testid="create-table-confirm" variant="primary" loading={busy} onClick={submit}>
            Créer
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Nom de la table" required>
          <Input data-testid="new-table-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="users" />
        </Field>
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <input type="checkbox" checked={withId} onChange={(e) => setWithId(e.target.checked)} />
          Ajouter automatiquement une clé primaire "id"
        </label>
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <input type="checkbox" checked={isProtected} onChange={(e) => setIsProtected(e.target.checked)} />
          Table protégée
        </label>
        {isProtected && (
          <Field label="Code de protection" required>
            <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="XML-XXXX-YYYY" />
          </Field>
        )}
      </div>
    </Modal>
  );
}

/* ---------------------------------------------------------------- add column */

export function AddColumnModal({
  open,
  onClose,
  dbId,
  tableId,
}: {
  open: boolean;
  onClose: () => void;
  dbId: string;
  tableId: number;
}) {
  const { addColumn, tables } = useStore();
  const toast = useToast();
  const [form, setForm] = useState({ name: "", type: "VARCHAR", length: "255", nullable: true, primary_key: false, unique: false, auto_increment: false, index: false, foreign_key: false, references: "", default: "" });
  const [fkTableId, setFkTableId] = useState("");
  const [fkColumn, setFkColumn] = useState("");
  const [fkOptions, setFkOptions] = useState<Column[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm({ name: "", type: "VARCHAR", length: "255", nullable: true, primary_key: false, unique: false, auto_increment: false, index: false, foreign_key: false, references: "", default: "" });
    setFkTableId("");
    setFkColumn("");
    setFkOptions([]);
  }, [open]);

  const handleFkTableChange = async (id: string) => {
    setFkTableId(id);
    setFkColumn("");
    if (!id) { setFkOptions([]); return; }
    try {
      const cols = await columnService.list(Number(id), false);
      setFkOptions(cols);
    } catch { setFkOptions([]); }
  };

  const submit = async () => {
    if (!form.name.trim()) {
      toast({ kind: "error", title: "Nom requis" });
      return;
    }
    if (form.foreign_key && (!fkTableId || !fkColumn)) {
      toast({ kind: "error", title: "Référence FK incomplète" });
      return;
    }
    setBusy(true);
    try {
      const refTable = tables.find(t => String(t.id) === fkTableId);
      const references = form.foreign_key && refTable && fkColumn ? `${refTable.name}.${fkColumn}` : null;
      await addColumn({
        name: form.name.trim(),
        type: form.type,
        length: form.length || "-",
        nullable: form.nullable,
        primary_key: form.primary_key,
        foreign_key: form.foreign_key,
        references,
        unique: form.unique,
        auto_increment: form.auto_increment,
        index: form.index,
        default: form.default === "" ? null : form.default,
        table_id: tableId,
      });
      onClose();
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur colonne", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ajouter une colonne"
      subtitle={`Table ${tableId} · structure XML mise à jour`}
      icon="columns"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" loading={busy} onClick={submit}>
            Ajouter
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="Nom" required>
          <Input autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="age" />
        </Field>
        <Field label="Type">
          <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full">
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Longueur">
          <Input value={form.length} onChange={(e) => setForm({ ...form, length: e.target.value })} placeholder="255" />
        </Field>
        <Field label="Défaut">
          <Input value={form.default} onChange={(e) => setForm({ ...form, default: e.target.value })} placeholder="NULL" />
        </Field>
        <div className="col-span-2 flex flex-wrap gap-4">
          {[
            ["nullable", "Nullable"],
            ["unique", "Unique"],
            ["primary_key", "PK"],
            ["auto_increment", "Auto inc"],
            ["index", "Index"],
            ["foreign_key", "FK"],
          ].map(([k, label]) => (
            <label key={k} className="flex items-center gap-2 text-[12px] text-muted">
              <input type="checkbox" checked={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />
              {label}
            </label>
          ))}
        </div>
        {form.foreign_key && (
          <div className="col-span-2 grid grid-cols-2 gap-3 border-t border-line pt-3">
            <Field label="Table référencée">
              <Select value={fkTableId} onChange={(e) => handleFkTableChange(e.target.value)} className="w-full">
                <option value="">— Sélectionner —</option>
                {tables.filter(t => t.id !== tableId).map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Colonne référencée">
              <Select value={fkColumn} onChange={(e) => setFkColumn(e.target.value)} className="w-full" disabled={!fkTableId}>
                <option value="">— Sélectionner —</option>
                {fkOptions.map(c => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </Select>
            </Field>
          </div>
        )}
      </div>
    </Modal>
  );
}

/* -------------------------------------------------------------- edit column */

export function EditColumnModal({
  open,
  onClose,
  column,
}: {
  open: boolean;
  onClose: () => void;
  column: Column | null;
}) {
  const { tables, columns } = useStore();
  const toast = useToast();
  const [form, setForm] = useState({ name: "", type: "VARCHAR", length: "255", nullable: true, primary_key: false, unique: false, auto_increment: false, index: false, foreign_key: false, default: "", comment: "" });
  const [fkTableId, setFkTableId] = useState("");
  const [fkColumn, setFkColumn] = useState("");
  const [fkOptions, setFkOptions] = useState<Column[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !column) return;
    setForm({
      name: column.name,
      type: column.type,
      length: column.length,
      nullable: column.nullable,
      primary_key: column.primary_key,
      unique: column.unique,
      auto_increment: column.auto_increment,
      index: column.index,
      foreign_key: column.foreign_key,
      default: column.default || "",
      comment: column.comment || "",
    });
    if (column.references) {
      const [refTableName, refCol] = column.references.split('.');
      const refTable = tables.find(t => t.name === refTableName);
      if (refTable) {
        setFkTableId(String(refTable.id));
        setFkColumn(refCol || "");
        columnService.list(refTable.id, false).then(setFkOptions).catch(() => setFkOptions([]));
      }
    } else {
      setFkTableId("");
      setFkColumn("");
    }
  }, [open, column, tables]);

  const handleFkTableChange = async (id: string) => {
    setFkTableId(id);
    setFkColumn("");
    if (!id) { setFkOptions([]); return; }
    try {
      const cols = await columnService.list(Number(id), false);
      setFkOptions(cols);
    } catch { setFkOptions([]); }
  };

  const submit = async () => {
    if (!column) return;
    if (!form.name.trim()) {
      toast({ kind: "error", title: "Nom requis" });
      return;
    }
    setBusy(true);
    try {
      const refTable = tables.find(t => String(t.id) === fkTableId);
      const references = form.foreign_key && refTable && fkColumn ? `${refTable.name}.${fkColumn}` : column.references;
      await columnService.update(column.id, {
        name: form.name.trim(),
        type: form.type,
        length: form.length || "-",
        nullable: form.nullable,
        primary_key: form.primary_key,
        foreign_key: form.foreign_key,
        references,
        unique: form.unique,
        auto_increment: form.auto_increment,
        index: form.index,
        default: form.default === "" ? null : form.default,
        comment: form.comment,
      });
      toast({ kind: "success", title: "Colonne modifiée" });
      onClose();
      // Au lieu de reload complet, on laisse le parent refetch
      // via un event ou via le store (fetchColumns sera appelé par TableWorkspace/StructureTab)
      // On déclenche un event pour que StructureTab se recharge
      window.dispatchEvent(new CustomEvent("xf-refresh-columns"));
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur modification", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Modifier la colonne"
      subtitle={`${column?.name} · ${column?.type}`}
      icon="columns"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button variant="primary" loading={busy} onClick={submit}>Enregistrer</Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="Nom" required>
          <Input autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Type">
          <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full">
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </Select>
        </Field>
        <Field label="Longueur">
          <Input value={form.length} onChange={(e) => setForm({ ...form, length: e.target.value })} />
        </Field>
        <Field label="Défaut">
          <Input value={form.default} onChange={(e) => setForm({ ...form, default: e.target.value })} />
        </Field>
        <Field label="Commentaire" className="col-span-2">
          <Input value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} placeholder="Optionnel" />
        </Field>
        <div className="col-span-2 flex flex-wrap gap-4">
          {[
            ["nullable", "Nullable"],
            ["unique", "Unique"],
            ["primary_key", "PK"],
            ["auto_increment", "Auto inc"],
            ["index", "Index"],
            ["foreign_key", "FK"],
          ].map(([k, label]) => (
            <label key={k} className="flex items-center gap-2 text-[12px] text-muted">
              <input type="checkbox" checked={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />
              {label}
            </label>
          ))}
        </div>
        {form.foreign_key && (
          <div className="col-span-2 grid grid-cols-2 gap-3 border-t border-line pt-3">
            <Field label="Table référencée">
              <Select value={fkTableId} onChange={(e) => handleFkTableChange(e.target.value)} className="w-full">
                <option value="">— Sélectionner —</option>
                {tables.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
            </Field>
            <Field label="Colonne référencée">
              <Select value={fkColumn} onChange={(e) => setFkColumn(e.target.value)} className="w-full" disabled={!fkTableId}>
                <option value="">— Sélectionner —</option>
                {fkOptions.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
              </Select>
            </Field>
          </div>
        )}
      </div>
    </Modal>
  );
}

/* --------------------------------------------------------------- row editing */

export function RowModal({
  open,
  onClose,
  tableId,
  columns,
  row,
}: {
  open: boolean;
  onClose: () => void;
  tableId: number;
  columns: Column[];
  row: Row | null;
}) {
  const { insertRow, updateCell } = useStore();
  const [values, setValues] = useState<Record<string, string>>({});
  const [nulls, setNulls] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);

  const init = (r: Row | null) => {
    const v: Record<string, string> = {};
    const n: Record<string, boolean> = {};
    columns.forEach((c) => {
      if (c.auto_increment) return;
      const val = r ? r.data[c.name] : null;
      v[c.name] = val === null || val === undefined ? "" : String(val);
      n[c.name] = val === null || val === undefined;
    });
    setValues(v);
    setNulls(n);
  };

  useEffect(() => {
    if (open) init(row);
  }, [open, row, columns]);

  const editable = columns.filter((c) => !c.auto_increment);

  const submit = async () => {
    setBusy(true);
    try {
      const payload: Record<string, any> = {};
      editable.forEach((c) => {
        payload[c.name] = nulls[c.name] ? null : (values[c.name] === "" ? null : values[c.name]);
      });
      const filtered = Object.fromEntries(Object.entries(payload).filter(([k, v]) => {
        const col = columns.find(c => c.name === k);
        if (v === "" && col?.auto_increment) return false;
        return v !== undefined;
      }));
      if (row) {
        await updateCell(tableId, row.id, filtered);
      } else {
        await insertRow(tableId, filtered);
      }
      onClose();
    } catch {
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={row ? `Modifier ligne #${row.id}` : "Ajouter une ligne"}
      subtitle={`Table ${tableId}`}
      icon="rows"
      width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" loading={busy} onClick={submit}>
            {row ? "Enregistrer" : "Insérer"}
          </Button>
        </>
      }
    >
      <div className="space-y-2.5">
        {editable.map((c) => (
          <div key={c.name} className="grid grid-cols-[150px_1fr_auto] items-center gap-3">
            <div className="min-w-0">
              <p className="truncate font-mono text-[12px] text-fg">{c.name}</p>
              <p className="truncate text-[10.5px] text-dim">{c.type}{c.length && c.length !== '-' ? `(${c.length})` : ''}</p>
            </div>
            <Input
              value={values[c.name] ?? ""}
              disabled={nulls[c.name]}
              onChange={(e) => setValues({ ...values, [c.name]: e.target.value })}
              placeholder={nulls[c.name] ? "NULL" : c.default || (c.nullable ? "NULL autorisé" : "valeur")}
              className={cn(nulls[c.name] && "opacity-50")}
            />
            <button
              onClick={() => setNulls({ ...nulls, [c.name]: !nulls[c.name] })}
              disabled={!c.nullable}
              className={cn(
                "rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors",
                nulls[c.name] ? "border-accent/50 bg-accent-soft text-accent" : "border-line text-dim hover:text-fg",
                !c.nullable && "cursor-not-allowed opacity-30",
              )}
            >
              NULL
            </button>
          </div>
        ))}
      </div>
    </Modal>
  );
}

/* --------------------------------------------------------------- unlock table */

export function UnlockTableModal({
  open,
  onClose,
  dbId,
  tableId,
}: {
  open: boolean;
  onClose: () => void;
  dbId: string;
  tableId: number;
}) {
  const { unlockTable } = useStore();
  const [phrase, setPhrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (phrase.trim().length < 4) {
      setError("Clé trop courte (min. 4 caractères)");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await unlockTable(tableId, phrase.trim());
      setPhrase("");
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Déverrouiller la table"
      subtitle={`Table ${tableId} protégée en écriture`}
      icon="unlock"
      width="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" icon="unlock" loading={busy} onClick={submit}>
            Déverrouiller
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-[12.5px] leading-relaxed text-muted">
          La lecture reste disponible. Le déverrouillage autorise INSERT, UPDATE, DELETE jusqu'à la fin de la session (24h).
        </p>
        <Field label="Clé de protection" required hint="Code défini par le propriétaire">
          <Input
            type="password"
            autoFocus
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            placeholder="XML-XXXX-YYYY"
          />
        </Field>
        {error && (
          <p className="flex items-center gap-1.5 text-[12px] text-danger">
            <Icon name="alert" size={12} />
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

/* ---------------------------------------------------------------- share base */

export function ShareModal({ open, onClose, dbId }: { open: boolean; onClose: () => void; dbId: string }) {
  const { dbs } = useStore();
  const toast = useToast();
  const db = dbs.find((d) => String(d.id) === dbId);
  const [members, setMembers] = useState<any[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<'VIEW' | 'EDIT' | 'MANAGE'>('VIEW');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!dbId) return;
    setLoading(true);
    try {
      const perms = await permissionService.listDatabase(dbId);
      setMembers(perms);
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur permissions", detail: e.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      load();
      setEmail("");
    }
  }, [open, dbId]);

  const grant = async () => {
    if (!email.trim()) return;
    const rights = role === 'MANAGE' ? { can_read: true, can_write: true, can_ddl: true, can_admin: true }
      : role === 'EDIT' ? { can_read: true, can_write: true, can_ddl: true, can_admin: false }
      : { can_read: true, can_write: false, can_ddl: false, can_admin: false };
    try {
      await permissionService.grantDatabase(dbId, { email: email.trim(), ...rights });
      await load();
      setEmail("");
      toast({ kind: "success", title: "Accès partagé", detail: `${role} accordé` });
    } catch (e: any) {
      toast({ kind: "error", title: "Partage impossible", detail: e.message });
    }
  };

  const revoke = async (userId: number) => {
    try {
      await permissionService.revokeDatabase(dbId, userId);
      setMembers(s => s.filter(m => m.user_id !== userId));
    } catch (e: any) {
      toast({ kind: "error", title: "Retrait impossible", detail: e.message });
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Partager la base"
      subtitle={`${db?.name} · ${db?.scope === "COMMON" ? "COMMUNE — visible par tous" : "PERSONNELLE — accès explicite"}`}
      icon="share"
      width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Fermer
          </Button>
        </>
      }
    >
      {db?.scope === 'COMMON' ? (
        <div className="rounded-md border border-violet/30 bg-violet-soft/20 p-3 text-[12px] text-violet">
          Base COMMUNE : accès collectif {db.common_permission}. Tous les utilisateurs actifs y ont accès.
        </div>
      ) : (
        <>
          <div className="flex gap-2">
            <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="utilisateur@exemple.com" className="flex-1" />
            <Select value={role} onChange={(e) => setRole(e.target.value as any)} className="w-32">
              <option value="VIEW">VIEW</option>
              <option value="EDIT">EDIT</option>
              <option value="MANAGE">MANAGE</option>
            </Select>
            <Button variant="primary" size="sm" onClick={grant} disabled={!email.trim()}>
              Partager
            </Button>
          </div>
          <div className="mt-4 overflow-hidden rounded-md border border-line">
            <div className="grid grid-cols-[1fr_100px_60px] gap-2 border-b border-line bg-raised px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-dim">
              <span>Utilisateur</span>
              <span>Rôle</span>
              <span />
            </div>
            {loading ? (
              <div className="p-4 text-[12px] text-dim">Chargement...</div>
            ) : members.length === 0 ? (
              <div className="p-4 text-[12px] text-dim">Aucun partage.</div>
            ) : (
              members.map((m) => (
                <div key={m.id} className="grid grid-cols-[1fr_100px_60px] items-center gap-2 border-b border-line-soft px-3 py-1.5 last:border-0">
                  <span className="text-[12.5px] text-fg">{m.user_email || `User #${m.user_id}`}</span>
                  <span className="text-[11px] text-muted">{m.can_admin ? 'MANAGE' : m.can_write || m.can_ddl ? 'EDIT' : 'VIEW'}</span>
                  <button onClick={() => revoke(m.user_id)} className="flex h-6 w-6 items-center justify-center rounded text-dim hover:text-danger">
                    <Icon name="trash" size={12} />
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </Modal>
  );
}
