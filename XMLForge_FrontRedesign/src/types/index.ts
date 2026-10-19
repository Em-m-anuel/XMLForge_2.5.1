/**
 * Types réels XMLForge — source de vérité backend
 * Centralise les modèles retournés par l'API REST
 */

export type Access = {
  can_read: boolean
  can_write: boolean
  can_ddl: boolean
  can_admin: boolean
  level: 'VIEW' | 'EDIT' | 'MANAGE' | 'OWNER' | 'NONE' | string
}

export type Database = {
  id: number
  uuid: string
  name: string
  description: string
  creator_id: number
  creator_name: string
  owner_id: number
  owner_name: string
  scope: 'PERSONAL' | 'COMMON'
  common_permission: 'VIEW' | 'EDIT' | 'MANAGE' | null
  document_version: number
  sync_status: string
  created_at: string
  updated_at: string
  last_modified_by_id: number
  last_modified_by: string
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  tables_count: number
  key_identifier?: string
  access?: Access
  is_owner?: boolean
}

export type Table = {
  id: number
  uuid: string
  name: string
  description: string
  database_id: number
  creator_id: number
  creator_name: string
  created_at: string
  updated_at: string
  last_modified_by_id?: number
  last_modified_by?: string
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  is_protected: boolean
  has_file_identifier: boolean
  protected: boolean
  archived: boolean
  columns_count: number
  file_identifier?: string
  access?: Access
}

export type Column = {
  id: number
  uuid: string
  name: string
  type: string
  length: string
  nullable: boolean
  primary_key: boolean
  foreign_key: boolean
  unique: boolean
  auto_increment: boolean
  default: any
  references: string | null
  on_delete: string
  on_update: string
  index: boolean
  comment: string
  status: 'ACTIVE' | 'ARCHIVED'
  table_id: number
}

export type Row = {
  id: number
  uuid: string
  table_id: number
  data: Record<string, any>
  created_at?: string | null
  updated_at?: string | null
}

export type RowsResponse = {
  rows: Row[]
  total: number
  limit: number
  offset: number
  table?: Table
}

export type QueryResult = {
  rows?: any[]
  columns?: string[]
  total?: number
  count?: number
  inserted?: number
  updated?: number
  deleted?: number
  created?: string
  dropped?: string
  table?: any
  timing?: { ms: number }
  affected?: number
  message?: string
  status?: 'ok' | 'error'
  [key: string]: any
}

export type AuthUser = {
  id: number
  full_name: string
  email: string
  role: string
  is_admin: boolean
  is_active: boolean
  created_at?: string
  initials?: string
}

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
