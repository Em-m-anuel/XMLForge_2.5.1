/**
 * XMLForge V2 — Store réel connecté au backend XML-only
 * Remplace les mocks par des appels API réels
 * Design conservé, logique métier branchée sur backend existant
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useToast } from "./components/ui";
import { apiLogin, apiLogout, apiMe, getStoredUser, type AuthUser } from "./api/auth";
import { databaseService, type Database } from "./api/databases";
import { tableService, type Table } from "./api/tables";
import { columnService, type Column } from "./api/columns";
import { rowService, type Row } from "./api/rows";
import { queryService, type QueryResult } from "./api/queries";
import { xmlService } from "./api/xml";
import { serverService } from "./api/server";
import { tcpService } from "./api/tcp";

export type DbTab = "tables" | "sql" | "relations" | "xml" | "share";
export type TableTab = "data" | "structure" | "relations" | "sql" | "xml" | "permissions";
export type AdminTab = "users" | "permissions" | "audit" | "history";

export type Nav =
  | { v: "overview" }
  | { v: "databases" }
  | { v: "db"; db: string; tab: DbTab }
  | { v: "table"; db: string; table: string; tab: TableTab }
  | { v: "sql" }
  | { v: "relations" }
  | { v: "xml" }
  | { v: "import" }
  | { v: "admin"; tab: AdminTab }
  | { v: "server" }
  | { v: "logs" }
  | { v: "settings" };

// Types réels pour compat UI
export type RealDb = Database & {
  tables?: Table[]
}

type Ctx = {
  session: { user: AuthUser | null; authenticated: boolean };
  login: (email: string, password: string) => Promise<{ ok: true } | { ok: false; error: string }>;
  logout: () => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<{ ok: true } | { ok: false; error: string }>;
  canManageDb: (db: Database) => boolean;
  isAdmin: boolean;

  nav: Nav;
  go: (n: Nav) => void;
  activeDb: string;
  setActiveDb: (id: string) => void;

  sidebar: boolean;
  toggleSidebar: () => void;

  palette: boolean;
  setPalette: (v: boolean) => void;

  dbs: Database[];
  dbsLoading: boolean;
  dbsError: string | null;
  fetchDatabases: () => Promise<void>;
  db: () => Database | undefined;

  createDatabase: (name: string, scope: 'PERSONAL' | 'COMMON', description: string, commonPermission?: string | null) => Promise<void>;
  updateDatabase: (dbId: string, patch: { name: string; description: string }) => Promise<{ ok: true } | { ok: false; error: string }>;
  dropDatabase: (dbId: string) => Promise<void>;

  tables: Table[];
  tablesLoading: boolean;
  tablesError: string | null;
  fetchTables: (dbId?: string) => Promise<void>;
  createTable: (dbId: string, name: string, opts?: { is_protected?: boolean; file_identifier?: string | null; description?: string }) => Promise<Table>;
  dropTable: (dbId: string, tableId: number) => Promise<void>;
  duplicateTable: (dbId: string, tableId: number, newName: string) => Promise<Table>;
  truncateTable: (dbId: string, tableId: number) => Promise<void>;
  setProtected: (dbId: string, tableId: number, value: boolean, key?: string | null) => Promise<void>;
  unlockTable: (tableId: number, key: string) => Promise<void>;

  columns: Column[];
  columnsLoading: boolean;
  columnsError: string | null;
  fetchColumns: (tableId: number) => Promise<void>;
  addColumn: (payload: any) => Promise<Column>;
  dropColumn: (colId: number) => Promise<void>;

  rows: Row[];
  rowsTotal: number;
  rowsLoading: boolean;
  rowsError: string | null;
  fetchRows: (tableId: number, opts?: any) => Promise<void>;
  insertRow: (tableId: number, data: Record<string, any>) => Promise<void>;
  updateCell: (tableId: number, rowId: number, data: Record<string, any>) => Promise<void>;
  deleteRows: (tableId: number, rowIds: number[]) => Promise<void>;

  queryResult: QueryResult | null;
  queryLoading: boolean;
  queryError: string | null;
  executeQuery: (dbId: string, sql: string) => Promise<QueryResult>;

  xmlDoc: string;
  xmlLoading: boolean;
  xmlError: string | null;
  fetchXml: (tableId?: number, dbId?: string) => Promise<void>;
  applyXml: (tableId: number, xml: string) => Promise<void>;
  syncDatabaseXml: (dbId: string, xml: string) => Promise<void>;

  serverHealth: any;
  tcpStatus: any;
  fetchServerStatus: () => Promise<{ health: any; status: any } | void>;

  favDbs: string[];
  favTables: string[];
  toggleFavDb: (id: string) => void;
  toggleFavTable: (id: string) => void;

  history: any[];
  pushHistory: (q: any) => void;
  toggleSaved: (id: number) => void;
};

const StoreCtx = createContext<Ctx | null>(null);
export const useStore = () => {
  const c = useContext(StoreCtx);
  if (!c) throw new Error("useStore outside provider");
  return c;
};

export function StoreProvider({ children }: { children: ReactNode }) {
  const toast = useToast();

  const [nav, setNav] = useState<Nav>({ v: "overview" });
  const [activeDb, setActiveDb] = useState<string>("");
  const [sidebar, setSidebar] = useState(false);
  const [palette, setPalette] = useState(false);

  const [session, setSession] = useState<{ user: AuthUser | null; authenticated: boolean }>(() => {
    const stored = getStoredUser();
    const token = localStorage.getItem('xmlforge_token');
    return {
      user: stored as AuthUser | null,
      authenticated: !!token && !!stored,
    };
  });

  const isAdmin = useMemo(() => {
    return !!(session.user?.is_admin || session.user?.role?.toLowerCase() === 'admin');
  }, [session.user]);

  const [dbs, setDbs] = useState<Database[]>([]);
  const [dbsLoading, setDbsLoading] = useState(false);
  const [dbsError, setDbsError] = useState<string | null>(null);

  const [tables, setTables] = useState<Table[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);

  const [columns, setColumns] = useState<Column[]>([]);
  const [columnsLoading, setColumnsLoading] = useState(false);
  const [columnsError, setColumnsError] = useState<string | null>(null);

  const [rows, setRows] = useState<Row[]>([]);
  const [rowsTotal, setRowsTotal] = useState(0);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState<string | null>(null);

  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  const [xmlDoc, setXmlDoc] = useState<string>("");
  const [xmlLoading, setXmlLoading] = useState(false);
  const [xmlError, setXmlError] = useState<string | null>(null);

  const [serverHealth, setServerHealth] = useState<any>(null);
  const [tcpStatus, setTcpStatus] = useState<any>(null);

  const [favDbs, setFavDbs] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('xmlforge_fav_dbs') || '[]'); } catch { return []; }
  });
  const [favTables, setFavTables] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('xmlforge_fav_tables') || '[]'); } catch { return []; }
  });

  const toggleFavDb = (id: string) => {
    setFavDbs(prev => {
      const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id];
      localStorage.setItem('xmlforge_fav_dbs', JSON.stringify(next));
      return next;
    });
  };

  const toggleFavTable = (id: string) => {
    setFavTables(prev => {
      const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id];
      localStorage.setItem('xmlforge_fav_tables', JSON.stringify(next));
      return next;
    });
  };

  const [history, setHistory] = useState<any[]>([]);

  const dbReqId = useRef(0);
  const tablesReqId = useRef(0);
  const columnsReqId = useRef(0);
  const rowsReqId = useRef(0);
  const xmlReqId = useRef(0);
  const queryReqId = useRef(0);
  const serverReqId = useRef(0);

  const go = useCallback((n: Nav) => {
    setNav(n);
    if ("db" in n) setActiveDb(n.db);
    window.scrollTo({ top: 0 });
  }, []);

  const db = useCallback(() => dbs.find(d => String(d.id) === String(activeDb) || d.name === activeDb), [dbs, activeDb]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin({ email, password });
    if (res.ok) {
      setSession({ user: res.user, authenticated: true });
      toast({ kind: "success", title: "Session ouverte", detail: `Connecté en tant que ${res.user.email}` });
      return { ok: true as const };
    } else {
      return { ok: false as const, error: (res as any).error };
    }
  }, [toast]);

  const logout = useCallback(async () => {
    await apiLogout();
    setSession({ user: null, authenticated: false });
    setNav({ v: "overview" });
    setDbs([]);
    setTables([]);
    setColumns([]);
    setRows([]);
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const { apiRegister } = await import("./api/auth");
    const res = await apiRegister({ name, email, password });
    if (res.ok) {
      toast({ kind: "success", title: "Compte créé", detail: "Vous pouvez maintenant vous connecter." });
      return { ok: true as const };
    } else {
      return { ok: false as const, error: (res as any).error };
    }
  }, [toast]);

  const canManageDb = useCallback((db: Database) => {
    if (isAdmin) return true;
    return !!(db.access?.can_admin || db.is_owner);
  }, [isAdmin]);

  const fetchDatabases = useCallback(async () => {
    if (!session.authenticated) return;
    const req = ++dbReqId.current;
    setDbsLoading(true);
    setDbsError(null);
    try {
      const data = await databaseService.list(true);
      if (req !== dbReqId.current) return;
      setDbs(data);
      if (data.length && !activeDb) {
        setActiveDb(String(data[0].id));
      }
    } catch (e: any) {
      if (req !== dbReqId.current) return;
      setDbsError(e.message);
      toast({ kind: "error", title: "Erreur bases", detail: e.message });
    } finally {
      if (req === dbReqId.current) setDbsLoading(false);
    }
  }, [session.authenticated, activeDb, toast]);

  const createDatabase = useCallback(async (name: string, scope: 'PERSONAL' | 'COMMON', description: string, commonPermission?: string | null) => {
    try {
      const db = await databaseService.create({
        name: name.trim(),
        description: description.trim(),
        scope: scope.toUpperCase() as any,
        common_permission: scope.toLowerCase() === 'common' ? (commonPermission as any) || 'VIEW' : null,
      });
      setDbs(s => [db, ...s]);
      setActiveDb(String(db.id));
      toast({ kind: "success", title: "Base créée", detail: name });
      go({ v: "db", db: String(db.id), tab: "tables" });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur création base", detail: e.message });
      throw e;
    }
  }, [toast, go]);

  const updateDatabase = useCallback(async (dbId: string, patch: { name: string; description: string }) => {
    const current = dbs.find(d => String(d.id) === dbId);
    if (!current) return { ok: false as const, error: "Base introuvable." };
    if (!canManageDb(current)) {
      return { ok: false as const, error: "Permission refusée. Owner ou Manage requis." };
    }
    if (!patch.name.trim()) return { ok: false as const, error: "Le nom de la base est requis." };
    try {
      const updated = await databaseService.update(dbId, {
        name: patch.name.trim(),
        description: patch.description.trim(),
      }, current.document_version);
      setDbs(s => s.map(d => String(d.id) === dbId ? updated : d));
      toast({ kind: "success", title: "Base mise à jour", detail: updated.name });
      return { ok: true as const };
    } catch (e: any) {
      if (e.isConflict) {
        toast({ kind: "error", title: "Conflit de version", detail: e.message });
        return { ok: false as const, error: e.message };
      }
      return { ok: false as const, error: e.message };
    }
  }, [dbs, canManageDb, toast]);

  const dropDatabase = useCallback(async (dbId: string) => {
    try {
      await databaseService.delete(dbId);
      setDbs(s => s.filter(d => String(d.id) !== dbId));
      toast({ kind: "warn", title: "Base supprimée", detail: dbId });
      if (String(activeDb) === String(dbId)) {
        setActiveDb("");
        go({ v: "databases" });
      }
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur suppression", detail: e.message });
      throw e;
    }
  }, [activeDb, go, toast]);

  const fetchTables = useCallback(async (dbId?: string) => {
    const id = dbId || activeDb;
    if (!id) {
      setTables([]);
      return;
    }
    const req = ++tablesReqId.current;
    setTablesLoading(true);
    setTablesError(null);
    if (dbId && dbId !== activeDb) {
      setTables([]);
      setColumns([]);
      setRows([]);
      setQueryResult(null);
      setXmlDoc("");
    }
    try {
      const data = await tableService.list(id, true);
      if (req !== tablesReqId.current) return;
      setTables(data);
    } catch (e: any) {
      if (req !== tablesReqId.current) return;
      setTablesError(e.message);
      setTables([]);
      toast({ kind: "error", title: "Erreur tables", detail: e.message });
    } finally {
      if (req === tablesReqId.current) setTablesLoading(false);
    }
  }, [activeDb, toast]);

  const fetchColumns = useCallback(async (tableId: number) => {
    const req = ++columnsReqId.current;
    setColumnsLoading(true);
    setColumnsError(null);
    setColumns([]);
    try {
      const data = await columnService.list(tableId, true);
      if (req !== columnsReqId.current) return;
      setColumns(data);
    } catch (e: any) {
      if (req !== columnsReqId.current) return;
      setColumnsError(e.message);
      setColumns([]);
      toast({ kind: "error", title: "Erreur colonnes", detail: e.message });
    } finally {
      if (req === columnsReqId.current) setColumnsLoading(false);
    }
  }, [toast]);

  const fetchRows = useCallback(async (tableId: number, opts: any = {}) => {
    const req = ++rowsReqId.current;
    setRowsLoading(true);
    setRowsError(null);
    setRows([]);
    setRowsTotal(0);
    try {
      const res = await rowService.list(tableId, {
        limit: opts.limit || 25,
        offset: opts.offset || 0,
        search: opts.search || '',
        sort: opts.sort || '',
        order: opts.order || 'ASC',
        filters: opts.filters || {},
      });
      if (req !== rowsReqId.current) return;
      setRows(res.rows || []);
      setRowsTotal(res.total || 0);
    } catch (e: any) {
      if (req !== rowsReqId.current) return;
      setRowsError(e.message);
      setRows([]);
      setRowsTotal(0);
      if (e.status !== 403) {
        toast({ kind: "error", title: "Erreur données", detail: e.message });
      }
    } finally {
      if (req === rowsReqId.current) setRowsLoading(false);
    }
  }, [toast]);

  const createTable = useCallback(async (dbId: string, name: string, opts?: { is_protected?: boolean; file_identifier?: string | null; description?: string }) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    if (!currentDb) throw new Error("Base introuvable");
    try {
      const table = await tableService.create({
        name: name.trim(),
        database_id: Number(dbId),
        description: opts?.description || "",
        is_protected: opts?.is_protected || false,
        file_identifier: opts?.file_identifier || null,
      }, currentDb.document_version);
      setTables(s => [...s, table]);
      toast({ kind: "success", title: "Table créée", detail: name });
      try {
        const updatedDb = await databaseService.get(dbId);
        setDbs(s => s.map(d => String(d.id) === dbId ? updatedDb : d));
      } catch {}
      return table;
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur création table", detail: e.message });
      throw e;
    }
  }, [dbs, toast]);

  const dropTable = useCallback(async (dbId: string, tableId: number) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    try {
      await tableService.delete(tableId, currentDb?.document_version);
      setTables(s => s.filter(t => t.id !== tableId));
      toast({ kind: "warn", title: "Table supprimée", detail: String(tableId) });
      try {
        const updatedDb = await databaseService.get(dbId);
        setDbs(s => s.map(d => String(d.id) === dbId ? updatedDb : d));
      } catch {}
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur suppression table", detail: e.message });
      throw e;
    }
  }, [dbs, toast]);

  const setProtected = useCallback(async (dbId: string, tableId: number, value: boolean, key?: string | null) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    try {
      const updated = await tableService.update(tableId, {
        is_protected: value,
        file_identifier: value ? (key || null) : null,
      }, currentDb?.document_version);
      setTables(s => s.map(t => t.id === tableId ? updated : t));
      toast({ kind: value ? "info" : "success", title: value ? "Table protégée" : "Protection retirée", detail: updated.name });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur protection", detail: e.message });
      throw e;
    }
  }, [dbs, toast]);

  const duplicateTable = useCallback(async (dbId: string, tableId: number, newName: string) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    try {
      const cols = await columnService.list(tableId, false);
      const newTable = await tableService.create({
        name: newName.trim(),
        database_id: Number(dbId),
        description: `Copie de ${tables.find(t => t.id === tableId)?.name || tableId}`,
      }, currentDb?.document_version);
      for (const col of cols) {
        try {
          await columnService.create({
            name: col.name,
            type: col.type,
            length: col.length,
            nullable: col.nullable,
            primary_key: col.primary_key,
            foreign_key: col.foreign_key,
            references: col.references,
            unique: col.unique,
            auto_increment: col.auto_increment,
            index: col.index,
            default: col.default,
            comment: col.comment,
            table_id: newTable.id,
          });
        } catch (e) {
          console.warn(`Erreur copie colonne ${col.name}`, e);
        }
      }
      await fetchTables(dbId);
      toast({ kind: "success", title: "Structure dupliquée", detail: `${newName} créée depuis table ${tableId}` });
      return newTable;
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur duplication", detail: e.message });
      throw e;
    }
  }, [dbs, tables, toast, fetchTables]);

  const truncateTable = useCallback(async (dbId: string, tableId: number) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    try {
      const table = tables.find(t => t.id === tableId);
      if (!table) throw new Error("Table introuvable");
      await queryService.execute(dbId, `DELETE FROM ${table.name};`, currentDb?.document_version);
      toast({ kind: "success", title: "Table vidée", detail: table.name });
      await fetchRows(tableId, { limit: 25, offset: 0 });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur truncate", detail: e.message });
      throw e;
    }
  }, [dbs, tables, toast, fetchRows]);

  const unlockTable = useCallback(async (tableId: number, key: string) => {
    try {
      await tableService.unlock(tableId, key);
      toast({ kind: "success", title: "Table déverrouillée", detail: `Accès personnel pour table ${tableId}` });
      try {
        const raw = sessionStorage.getItem('xmlforge_unlocks');
        const list = raw ? JSON.parse(raw) : [];
        if (!list.includes(tableId)) {
          list.push(tableId);
          sessionStorage.setItem('xmlforge_unlocks', JSON.stringify(list));
        }
      } catch {}
    } catch (e: any) {
      toast({ kind: "error", title: "Clé invalide", detail: e.message });
      throw e;
    }
  }, [toast]);

  const addColumn = useCallback(async (payload: any) => {
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      const col = await columnService.create(payload, currentDb?.document_version);
      setColumns(s => [...s, col]);
      setTables(s => s.map(t => t.id === payload.table_id ? { ...t, columns_count: (t.columns_count || 0) + 1 } : t));
      toast({ kind: "success", title: "Colonne ajoutée", detail: `${payload.name} (${payload.type})` });
      return col;
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur colonne", detail: e.message });
      throw e;
    }
  }, [dbs, activeDb, toast]);

  const dropColumn = useCallback(async (colId: number) => {
    const col = columns.find(c => c.id === colId);
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      await columnService.delete(colId, currentDb?.document_version);
      setColumns(s => s.filter(c => c.id !== colId));
      if (col) {
        setTables(s => s.map(t => t.id === col.table_id ? { ...t, columns_count: Math.max(0, (t.columns_count || 1) - 1) } : t));
      }
      toast({ kind: "warn", title: "Colonne supprimée", detail: String(colId) });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur suppression colonne", detail: e.message });
      throw e;
    }
  }, [columns, dbs, activeDb, toast]);

  const insertRow = useCallback(async (tableId: number, data: Record<string, any>) => {
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      const row = await rowService.create(tableId, data, currentDb?.document_version);
      setRows(s => [row, ...s]);
      setRowsTotal(s => s + 1);
      toast({ kind: "success", title: "Ligne insérée", detail: `id ${row.id}` });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur insertion", detail: e.message });
      throw e;
    }
  }, [dbs, activeDb, toast]);

  const updateCell = useCallback(async (tableId: number, rowId: number, data: Record<string, any>) => {
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      const updated = await rowService.update(tableId, rowId, data, currentDb?.document_version);
      setRows(s => s.map(r => r.id === rowId ? updated : r));
      toast({ kind: "success", title: "Ligne mise à jour", detail: `id ${rowId}` });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur mise à jour", detail: e.message });
      throw e;
    }
  }, [dbs, activeDb, toast]);

  const deleteRows = useCallback(async (tableId: number, rowIds: number[]) => {
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      for (const id of rowIds) {
        await rowService.delete(tableId, id, currentDb?.document_version);
      }
      setRows(s => s.filter(r => !rowIds.includes(r.id)));
      setRowsTotal(s => Math.max(0, s - rowIds.length));
      toast({ kind: "success", title: `${rowIds.length} ligne(s) supprimée(s)`, detail: String(tableId) });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur suppression", detail: e.message });
      throw e;
    }
  }, [dbs, activeDb, toast]);

  const executeQuery = useCallback(async (dbId: string, sql: string) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    const req = ++queryReqId.current;
    setQueryLoading(true);
    setQueryError(null);
    setQueryResult(null);
    try {
      const result = await queryService.execute(dbId, sql, currentDb?.document_version);
      if (req !== queryReqId.current) return result;
      setQueryResult(result);
      setHistory(h => [{ id: Date.now(), sql: sql.slice(0, 160), at: "à l'instant", ms: result.timing?.ms || 0, rows: result.rows?.length ?? result.count ?? result.affected ?? null, status: "ok", db: dbId }, ...h].slice(0, 100));
      toast({ kind: "success", title: "Requête exécutée", detail: `${result.rows?.length || result.count || result.affected || 0} lignes` });
      if (result.rows === undefined) {
        try {
          await fetchTables(dbId);
          const updatedDb = await databaseService.get(dbId);
          if (req === queryReqId.current) {
            setDbs(s => s.map(d => String(d.id) === dbId ? updatedDb : d));
          }
        } catch {}
      }
      return result;
    } catch (e: any) {
      if (req !== queryReqId.current) throw e;
      setQueryError(e.message);
      setHistory(h => [{ id: Date.now(), sql: sql.slice(0, 160), at: "à l'instant", ms: 0, rows: null, status: "error", error: e.message, db: dbId }, ...h].slice(0, 100));
      toast({ kind: "error", title: "Erreur SQL", detail: e.message });
      throw e;
    } finally {
      if (req === queryReqId.current) setQueryLoading(false);
    }
  }, [dbs, toast, fetchTables]);

  const fetchXml = useCallback(async (tableId?: number, dbId?: string) => {
    const req = ++xmlReqId.current;
    setXmlLoading(true);
    setXmlError(null);
    setXmlDoc("");
    try {
      if (tableId) {
        const res = await xmlService.exportTableXml(tableId);
        if (req !== xmlReqId.current) return;
        setXmlDoc(res.xml || "");
      } else if (dbId) {
        const res = await xmlService.exportDatabaseXml(dbId);
        if (req !== xmlReqId.current) return;
        setXmlDoc(res.xml || "");
      }
    } catch (e: any) {
      if (req !== xmlReqId.current) return;
      setXmlError(e.message);
      setXmlDoc("");
    } finally {
      if (req === xmlReqId.current) setXmlLoading(false);
    }
  }, []);

  const applyXml = useCallback(async (tableId: number, xml: string) => {
    const currentDb = dbs.find(d => String(d.id) === String(activeDb));
    try {
      const result = await xmlService.syncTable(tableId, xml, currentDb?.document_version);
      setXmlDoc(result.xml || xml);
      toast({ kind: "success", title: "XML appliqué", detail: `Version ${result.document_version}` });
      await fetchTables();
      await fetchColumns(tableId);
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur XML", detail: e.message });
      throw e;
    }
  }, [dbs, activeDb, toast, fetchTables, fetchColumns]);

  const syncDatabaseXml = useCallback(async (dbId: string, xml: string) => {
    const currentDb = dbs.find(d => String(d.id) === dbId);
    try {
      const result = await xmlService.syncDatabase(dbId, xml, currentDb?.document_version);
      toast({ kind: "success", title: "Base synchronisée", detail: `Version ${result.document_version}` });
      await fetchDatabases();
      await fetchTables(dbId);
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur sync", detail: e.message });
      throw e;
    }
  }, [dbs, toast, fetchDatabases, fetchTables]);

  const fetchServerStatus = useCallback(async () => {
    const req = ++serverReqId.current;
    let healthData: any = null;
    let statusData: any = null;
    try {
      const health = await serverService.health();
      if (req !== serverReqId.current) return { health: null, status: null };
      setServerHealth(health);
      healthData = health;
    } catch {}
    try {
      const status = await tcpService.status();
      if (req !== serverReqId.current) return { health: healthData, status: null };
      setTcpStatus(status);
      statusData = status;
    } catch {}
    return { health: healthData, status: statusData };
  }, []);

  useEffect(() => {
    if (session.authenticated) {
      fetchDatabases();
      fetchServerStatus();
    }
  }, [session.authenticated, fetchDatabases, fetchServerStatus]);

  useEffect(() => {
    if (activeDb) {
      fetchTables(activeDb);
    } else {
      setTables([]);
    }
  }, [activeDb, fetchTables]);

  useEffect(() => {
    const handler = (e: any) => {
      if (e.detail?.reason === 'expired' || e.detail?.reason === 'unauthorized') {
        setSession({ user: null, authenticated: false });
        toast({ kind: "error", title: "Session expirée", detail: "Veuillez vous reconnecter." });
      }
    };
    window.addEventListener('xmlforge:unauthorized', handler as any);
    return () => window.removeEventListener('xmlforge:unauthorized', handler as any);
  }, [toast]);

  useEffect(() => {
    const token = localStorage.getItem('xmlforge_token');
    if (token && !session.authenticated) {
      apiMe().then(user => {
        if (user) {
          setSession({ user, authenticated: true });
        } else {
          localStorage.removeItem('xmlforge_token');
          localStorage.removeItem('xmlforge_user');
        }
      });
    }
  }, [session.authenticated]);

  const api = useMemo<Ctx>(() => ({
    session,
    login,
    logout,
    register,
    canManageDb,
    isAdmin,

    nav,
    go,
    activeDb,
    setActiveDb,

    sidebar,
    toggleSidebar: () => setSidebar(s => !s),

    palette,
    setPalette: setPalette as any,

    dbs,
    dbsLoading,
    dbsError,
    fetchDatabases,
    db,

    createDatabase,
    updateDatabase,
    dropDatabase,

    tables,
    tablesLoading,
    tablesError,
    fetchTables,
    createTable,
    dropTable,
    duplicateTable,
    truncateTable,
    setProtected,
    unlockTable,

    columns,
    columnsLoading,
    columnsError,
    fetchColumns,
    addColumn,
    dropColumn,

    rows,
    rowsTotal,
    rowsLoading,
    rowsError,
    fetchRows,
    insertRow,
    updateCell,
    deleteRows,

    queryResult,
    queryLoading,
    queryError,
    executeQuery,

    xmlDoc,
    xmlLoading,
    xmlError,
    fetchXml,
    applyXml,
    syncDatabaseXml,

    serverHealth,
    tcpStatus,
    fetchServerStatus,

    favDbs,
    favTables,
    toggleFavDb,
    toggleFavTable,

    history,
    pushHistory: (q: any) => setHistory(h => [{ ...q, id: Date.now(), at: "à l'instant" }, ...h].slice(0, 100)),
    toggleSaved: (id: number) => setHistory(h => h.map(q => q.id === id ? { ...q, saved: !q.saved } : q)),
  }), [
    session, login, logout, register, canManageDb, isAdmin,
    nav, go, activeDb,
    sidebar, palette,
    dbs, dbsLoading, dbsError, fetchDatabases, db,
    createDatabase, updateDatabase, dropDatabase,
    tables, tablesLoading, tablesError, fetchTables, createTable, dropTable, setProtected, unlockTable, duplicateTable, truncateTable,
    columns, columnsLoading, columnsError, fetchColumns, addColumn, dropColumn,
    rows, rowsTotal, rowsLoading, rowsError, fetchRows, insertRow, updateCell, deleteRows,
    queryResult, queryLoading, queryError, executeQuery,
    xmlDoc, xmlLoading, xmlError, fetchXml, applyXml, syncDatabaseXml,
    serverHealth, tcpStatus, fetchServerStatus,
    favDbs, favTables,
    history,
  ]);

  return <StoreCtx.Provider value={api}>{children}</StoreCtx.Provider>;
}
