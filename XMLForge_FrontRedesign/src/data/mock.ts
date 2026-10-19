/* ------------------------------------------------------------------ */
/*  XMLForge V2 — mocked dataset. Presentation only, no backend logic.  */
/* ------------------------------------------------------------------ */

export type Col = {
  name: string;
  type: string;
  nullable: boolean;
  def?: string | null;
  pk?: boolean;
  ai?: boolean;
  unique?: boolean;
  index?: boolean;
  fk?: { table: string; column: string };
  comment?: string;
};

export type Row = Record<string, string | number | null> & { id: number };

export type Table = {
  name: string;
  cols: Col[];
  rows: Row[];
  protected?: boolean;
  createdAt: string;
  updatedAt: string;
  comment?: string;
  collation?: string;
};

export type Db = {
  id: string;
  name: string;
  scope: "personal" | "common";
  owner: string;
  createdAt: string;
  updatedAt: string;
  description?: string;
  sizeBytes: number;
  tables: Table[];
  members: { user: string; role: "Owner" | "Manage" | "Edit" | "View" }[];
};

/* ------------------------------------------------------------- generators */

const FN = [
  "Emmanuel", "Alexandre", "Camille", "Julien", "Sofia", "Nadia", "Marc", "Léa", "Thomas", "Inès",
  "Hugo", "Sarah", "Karim", "Élise", "Antoine", "Manon", "Yanis", "Clara", "Bastien", "Aïcha",
];
const LN = [
  "Bernard", "Moreau", "Lefèvre", "Dubois", "Martin", "Nguyen", "Silva", "Kouassi", "Rossi", "Haddad",
  "Petit", "Fontaine", "Girard", "Charpentier", "Marchand", "Barbier", "Renaud", "Leclerc", "Faure", "Diallo",
];
const COUNTRIES = ["FR", "BE", "CA", "DE", "ES", "IT", "JP", "US", "BR", "SN", "MA", "GB"];
const GENRES = [
  "Roman", "Essai", "Science-fiction", "Policier", "Histoire", "Philosophie", "Poésie", "Jeunesse",
  "Bande dessinée", "Informatique", "Biographie", "Théâtre",
];
const BOOK_WORDS = [
  "Le silence", "La lumière", "L'ombre", "Mémoires", "Chroniques", "Le voyage", "L'horizon", "Fragments",
  "La cité", "Le fleuve", "Vertiges", "L'écho", "Racines", "L'orée", "Dérives", "Le phare",
];
const BOOK_SUFFIX = [
  "des origines", "du temps", "d'ailleurs", "perdu", "d'hiver", "de verre", "sauvage", "intérieur",
  "des rois", "de la nuit", "sans fin", "des ombres",
];
const DEPTS = [
  ["Ingénierie", "ENGI"], ["Ressources humaines", "RHUM"], ["Finance", "FINC"], ["Marketing", "MKTG"],
  ["Support client", "SUPC"], ["Juridique", "JURI"], ["Opérations", "OPER"], ["Recherche", "RCHD"], ["Direction", "DIRX"],
];
const POSITIONS = [
  ["Ingénieur logiciel", "A"], ["Ingénieur senior", "B"], ["Chef d'équipe", "C"], ["Analyste", "A"],
  ["Comptable", "B"], ["Assistant", "A"], ["Responsable RH", "C"], ["Technicien", "A"], ["Consultant", "B"],
  ["Architecte", "D"], ["Stagiaire", "E"], ["Directeur", "E"],
];
const POST_TITLES = [
  "Comprendre le moteur XML", "Indexation et performance", "Sauvegardes locales",
  "Gestion des clés étrangères", "Le serveur TCP expliqué", "Migration depuis la v1",
  "Bonnes pratiques de schéma", "Déboguer une requête lente",
];

const pick = <T,>(a: T[], i: number) => a[i % a.length];
const pad = (n: number, l = 2) => String(n).padStart(l, "0");

function date(base: [number, number, number], offsetDays: number, withTime = true) {
  const d = new Date(Date.UTC(base[0], base[1] - 1, base[2]));
  d.setUTCDate(d.getUTCDate() + offsetDays);
  const p = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  if (!withTime) return p;
  return `${p} ${pad(8 + (offsetDays % 12))}:${pad((offsetDays * 7) % 60)}:${pad((offsetDays * 13) % 60)}`;
}

function makeRows(n: number, fn: (i: number) => Row): Row[] {
  return Array.from({ length: n }, (_, i) => fn(i + 1));
}

const slug = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ']/g, "")
    .replace(/[^a-z0-9]+/g, ".");

/* ---------------------------------------------------------------- Bibliothèque */

const C = {
  id: (extra: Partial<Col> = {}): Col => ({
    name: "id",
    type: "INT",
    nullable: false,
    pk: true,
    ai: true,
    ...extra,
  }),
  fk: (name: string, table: string, extra: Partial<Col> = {}): Col => ({
    name,
    type: "INT",
    nullable: false,
    index: true,
    fk: { table, column: "id" },
    ...extra,
  }),
  created: (): Col => ({
    name: "created_at",
    type: "DATETIME",
    nullable: false,
    def: "CURRENT_TIMESTAMP",
  }),
};

const usersTable: Table = {
  name: "users",
  createdAt: "2025-02-11 09:12:04",
  updatedAt: "2026-02-18 17:41:02",
  comment: "Comptes de la bibliothèque",
  cols: [
    C.id(),
    { name: "name", type: "VARCHAR(150)", nullable: false, index: true },
    { name: "email", type: "VARCHAR(255)", nullable: true, unique: true },
    { name: "role", type: "ENUM('admin','member','viewer')", nullable: false, def: "'member'" },
    { name: "active", type: "TINYINT(1)", nullable: false, def: "1" },
    { name: "last_login", type: "DATETIME", nullable: true },
    C.created(),
  ],
  rows: makeRows(152, (i) => ({
    id: i,
    name: `${pick(FN, i)} ${pick(LN, i * 3 + 1)}`,
    email: i % 17 === 0 ? null : `${slug(pick(FN, i))}.${slug(pick(LN, i * 3 + 1))}@xmlforge.io`,
    role: i === 1 ? "admin" : i % 9 === 0 ? "viewer" : "member",
    active: i % 23 === 0 ? 0 : 1,
    last_login: i % 11 === 0 ? null : date([2026, 2, 1], -(i % 45)),
    created_at: date([2025, 2, 11], i * 2),
  })),
};

const authorsTable: Table = {
  name: "authors",
  createdAt: "2025-02-11 09:14:22",
  updatedAt: "2026-01-30 11:02:55",
  cols: [
    C.id(),
    { name: "name", type: "VARCHAR(150)", nullable: false, index: true },
    { name: "country", type: "CHAR(2)", nullable: true },
    { name: "birth_year", type: "SMALLINT", nullable: true },
    C.created(),
  ],
  rows: makeRows(93, (i) => ({
    id: i,
    name: `${pick(FN, i * 5)} ${pick(LN, i * 2 + 3)}`,
    country: i % 8 === 0 ? null : pick(COUNTRIES, i * 2),
    birth_year: i % 13 === 0 ? null : 1932 + ((i * 7) % 68),
    created_at: date([2025, 2, 11], i * 3),
  })),
};

const categoriesTable: Table = {
  name: "categories",
  createdAt: "2025-02-11 09:15:48",
  updatedAt: "2025-12-04 08:22:10",
  cols: [
    C.id(),
    { name: "label", type: "VARCHAR(80)", nullable: false, unique: true },
    { name: "description", type: "TEXT", nullable: true },
  ],
  rows: makeRows(12, (i) => ({
    id: i,
    label: GENRES[i - 1],
    description: i % 4 === 0 ? null : `Ouvrages classés dans ${GENRES[i - 1].toLowerCase()}.`,
  })),
};

const booksTable: Table = {
  name: "books",
  createdAt: "2025-02-11 09:18:01",
  updatedAt: "2026-02-19 09:03:41",
  comment: "Catalogue principal",
  cols: [
    C.id(),
    { name: "title", type: "VARCHAR(220)", nullable: false, index: true },
    { name: "isbn", type: "VARCHAR(20)", nullable: false, unique: true },
    C.fk("author_id", "authors"),
    { name: "category_id", type: "INT", nullable: true, index: true, fk: { table: "categories", column: "id" } },
    { name: "published_year", type: "YEAR", nullable: true },
    { name: "stock", type: "INT", nullable: false, def: "0" },
    C.created(),
  ],
  rows: makeRows(428, (i) => ({
    id: i,
    title: `${pick(BOOK_WORDS, i)} ${pick(BOOK_SUFFIX, i * 3 + 1)}`,
    isbn: `978-2-${pad(1000 + i, 4)}-${pad((i * 37) % 10000, 4)}-${i % 10}`,
    author_id: ((i * 5) % 93) + 1,
    category_id: i % 9 === 0 ? null : ((i * 3) % 12) + 1,
    published_year: i % 19 === 0 ? null : 1954 + ((i * 11) % 71),
    stock: (i * 3) % 14,
    created_at: date([2025, 2, 12], i),
  })),
};

const loansTable: Table = {
  name: "loans",
  createdAt: "2025-03-02 14:20:00",
  updatedAt: "2026-02-20 18:55:12",
  protected: true,
  comment: "Emprunts — table protégée",
  cols: [
    C.id(),
    C.fk("book_id", "books"),
    C.fk("user_id", "users"),
    { name: "loaned_at", type: "DATETIME", nullable: false },
    { name: "due_at", type: "DATETIME", nullable: false },
    { name: "returned_at", type: "DATETIME", nullable: true, index: true },
  ],
  rows: makeRows(817, (i) => ({
    id: i,
    book_id: ((i * 7) % 428) + 1,
    user_id: ((i * 11) % 152) + 1,
    loaned_at: date([2025, 3, 2], i),
    due_at: date([2025, 3, 2], i + 21),
    returned_at: i % 5 === 0 ? null : date([2025, 3, 2], i + 9),
  })),
};

const reservationsTable: Table = {
  name: "reservations",
  createdAt: "2025-09-01 10:00:00",
  updatedAt: "2026-02-17 12:30:00",
  cols: [
    C.id(),
    C.fk("user_id", "users"),
    C.fk("book_id", "books"),
    { name: "status", type: "ENUM('pending','ready','cancelled')", nullable: false, def: "'pending'" },
    { name: "reserved_at", type: "DATETIME", nullable: false },
  ],
  rows: makeRows(64, (i) => ({
    id: i,
    user_id: ((i * 13) % 152) + 1,
    book_id: ((i * 5) % 428) + 1,
    status: i % 6 === 0 ? "cancelled" : i % 3 === 0 ? "ready" : "pending",
    reserved_at: date([2025, 9, 1], i * 2),
  })),
};

/* ---------------------------------------------------------------- GestionRH */

const employeesTable: Table = {
  name: "employees",
  createdAt: "2024-06-14 08:30:00",
  updatedAt: "2026-02-12 15:12:30",
  cols: [
    C.id(),
    { name: "first_name", type: "VARCHAR(80)", nullable: false },
    { name: "last_name", type: "VARCHAR(80)", nullable: false, index: true },
    { name: "email", type: "VARCHAR(180)", nullable: false, unique: true },
    C.fk("department_id", "departments"),
    C.fk("position_id", "positions"),
    { name: "hired_at", type: "DATE", nullable: false },
    { name: "salary", type: "DECIMAL(10,2)", nullable: true },
    { name: "active", type: "TINYINT(1)", nullable: false, def: "1" },
  ],
  rows: makeRows(248, (i) => ({
    id: i,
    first_name: pick(FN, i * 3),
    last_name: pick(LN, i * 7 + 2),
    email: `${slug(pick(FN, i * 3))}.${slug(pick(LN, i * 7 + 2))}@gestionrh.local`,
    department_id: ((i * 3) % 9) + 1,
    position_id: ((i * 5) % 12) + 1,
    hired_at: date([2019, 1, 6], i * 9, false),
    salary: i % 15 === 0 ? null : (32000 + ((i * 137) % 62000)).toFixed(2),
    active: i % 31 === 0 ? 0 : 1,
  })),
};

const departmentsTable: Table = {
  name: "departments",
  createdAt: "2024-06-14 08:31:00",
  updatedAt: "2025-11-02 09:00:00",
  cols: [
    C.id(),
    { name: "name", type: "VARCHAR(120)", nullable: false, unique: true },
    { name: "code", type: "CHAR(4)", nullable: false, unique: true },
    { name: "manager_id", type: "INT", nullable: true, fk: { table: "employees", column: "id" } },
    { name: "budget", type: "DECIMAL(12,2)", nullable: true },
  ],
  rows: makeRows(9, (i) => ({
    id: i,
    name: DEPTS[i - 1][0],
    code: DEPTS[i - 1][1],
    manager_id: i * 4 <= 248 ? i * 4 : null,
    budget: (120000 + i * 48000).toFixed(2),
  })),
};

const positionsTable: Table = {
  name: "positions",
  createdAt: "2024-06-14 08:32:00",
  updatedAt: "2025-10-18 14:00:00",
  cols: [
    C.id(),
    { name: "title", type: "VARCHAR(120)", nullable: false, unique: true },
    { name: "grade", type: "VARCHAR(2)", nullable: false },
    { name: "min_salary", type: "DECIMAL(10,2)", nullable: false, def: "30000.00" },
  ],
  rows: makeRows(12, (i) => ({
    id: i,
    title: POSITIONS[i - 1][0],
    grade: POSITIONS[i - 1][1],
    min_salary: (28000 + i * 2600).toFixed(2),
  })),
};

const salariesTable: Table = {
  name: "salaries",
  createdAt: "2024-07-01 09:00:00",
  updatedAt: "2026-01-15 17:45:00",
  protected: true,
  cols: [
    C.id(),
    C.fk("employee_id", "employees"),
    { name: "amount", type: "DECIMAL(10,2)", nullable: false },
    { name: "effective_from", type: "DATE", nullable: false },
    { name: "approved", type: "TINYINT(1)", nullable: false, def: "0" },
  ],
  rows: makeRows(612, (i) => ({
    id: i,
    employee_id: ((i * 3) % 248) + 1,
    amount: (34000 + ((i * 97) % 58000)).toFixed(2),
    effective_from: date([2021, 1, 1], i * 3, false),
    approved: i % 4 === 0 ? 0 : 1,
  })),
};

const leavesTable: Table = {
  name: "leaves",
  createdAt: "2024-08-01 09:00:00",
  updatedAt: "2026-02-05 11:20:00",
  cols: [
    C.id(),
    C.fk("employee_id", "employees"),
    { name: "start_date", type: "DATE", nullable: false },
    { name: "end_date", type: "DATE", nullable: false },
    { name: "type", type: "ENUM('cp','rtt','maladie','sans solde')", nullable: false },
    { name: "approved", type: "TINYINT(1)", nullable: true },
    { name: "reason", type: "TEXT", nullable: true },
  ],
  rows: makeRows(189, (i) => ({
    id: i,
    employee_id: ((i * 7) % 248) + 1,
    start_date: date([2025, 1, 6], i * 4, false),
    end_date: date([2025, 1, 6], i * 4 + 5, false),
    type: ["cp", "rtt", "maladie", "sans solde"][i % 4],
    approved: i % 7 === 0 ? null : i % 3 === 0 ? 0 : 1,
    reason: i % 5 === 0 ? null : "Congés planifiés",
  })),
};

/* ---------------------------------------------------------------- Demo (common) */

const demoUsers: Table = {
  name: "users",
  createdAt: "2025-05-02 10:00:00",
  updatedAt: "2026-02-10 09:30:00",
  cols: [
    C.id(),
    { name: "username", type: "VARCHAR(60)", nullable: false, unique: true },
    { name: "display_name", type: "VARCHAR(120)", nullable: true },
    { name: "email", type: "VARCHAR(180)", nullable: true },
    C.created(),
  ],
  rows: makeRows(35, (i) => ({
    id: i,
    username: `user_${pad(i, 3)}`,
    display_name: `${pick(FN, i * 2)} ${pick(LN, i)}`,
    email: i % 12 === 0 ? null : `user${pad(i, 3)}@demo.local`,
    created_at: date([2025, 5, 2], i),
  })),
};

const demoPosts: Table = {
  name: "posts",
  createdAt: "2025-05-02 10:05:00",
  updatedAt: "2026-02-14 16:00:00",
  cols: [
    C.id(),
    C.fk("user_id", "users"),
    { name: "title", type: "VARCHAR(200)", nullable: false },
    { name: "body", type: "TEXT", nullable: true },
    { name: "published", type: "TINYINT(1)", nullable: false, def: "0" },
    C.created(),
  ],
  rows: makeRows(142, (i) => ({
    id: i,
    user_id: ((i * 3) % 35) + 1,
    title: pick(POST_TITLES, i),
    body: i % 9 === 0 ? null : "Article de démonstration pour la base COMMON.",
    published: i % 4 === 0 ? 0 : 1,
    created_at: date([2025, 5, 3], i * 2),
  })),
};

const demoComments: Table = {
  name: "comments",
  createdAt: "2025-05-04 11:00:00",
  updatedAt: "2026-02-15 20:10:00",
  cols: [
    C.id(),
    C.fk("post_id", "posts"),
    C.fk("user_id", "users"),
    { name: "body", type: "TEXT", nullable: false },
    C.created(),
  ],
  rows: makeRows(305, (i) => ({
    id: i,
    post_id: ((i * 5) % 142) + 1,
    user_id: ((i * 7) % 35) + 1,
    body: "Commentaire de démonstration.",
    created_at: date([2025, 5, 4], i),
  })),
};

/* ---------------------------------------------------------------- databases */

export const DATABASES: Db[] = [
  {
    id: "bibliotheque",
    name: "Bibliotheque",
    scope: "personal",
    owner: "Emmanuel",
    createdAt: "2025-02-11 09:12:04",
    updatedAt: "2026-02-20 18:55:12",
    description: "Catalogue et suivi des prêts de la bibliothèque municipale.",
    sizeBytes: 4_812_544,
    tables: [usersTable, booksTable, authorsTable, categoriesTable, loansTable, reservationsTable],
    members: [
      { user: "Emmanuel", role: "Owner" },
      { user: "Alexandre", role: "Manage" },
      { user: "Camille", role: "Edit" },
      { user: "Nadia", role: "View" },
    ],
  },
  {
    id: "gestionrh",
    name: "GestionRH",
    scope: "personal",
    owner: "Emmanuel",
    createdAt: "2024-06-14 08:30:00",
    updatedAt: "2026-01-15 17:45:00",
    description: "Référentiel salariés, départements et congés.",
    sizeBytes: 9_663_280,
    tables: [employeesTable, departmentsTable, positionsTable, salariesTable, leavesTable],
    members: [
      { user: "Emmanuel", role: "Owner" },
      { user: "Sofia", role: "Edit" },
    ],
  },
  {
    id: "demo",
    name: "Demo",
    scope: "common",
    owner: "XMLForge",
    createdAt: "2025-05-02 10:00:00",
    updatedAt: "2026-02-15 20:10:00",
    description: "Base partagée, accessible à tous les utilisateurs actifs.",
    sizeBytes: 1_204_224,
    tables: [demoUsers, demoPosts, demoComments],
    members: [
      { user: "Emmanuel", role: "Manage" },
      { user: "Alexandre", role: "Edit" },
      { user: "Camille", role: "View" },
      { user: "Nadia", role: "View" },
      { user: "Sofia", role: "View" },
    ],
  },
];

/* ------------------------------------------------------------------ people */

export type AppUser = {
  id: number;
  name: string;
  email: string;
  role: "Admin" | "Editor" | "Viewer";
  status: "active" | "disabled" | "invited";
  lastSeen: string;
  databases: string[];
};

export const USERS: AppUser[] = [
  { id: 1, name: "Emmanuel", email: "nyx@xmlforge.io", role: "Admin", status: "active", lastSeen: "il y a 2 min", databases: ["Bibliotheque", "GestionRH", "Demo"] },
  { id: 2, name: "Alexandre", email: "alex@xmlforge.io", role: "Editor", status: "active", lastSeen: "il y a 42 min", databases: ["Bibliotheque", "Demo"] },
  { id: 3, name: "Camille", email: "camille@xmlforge.io", role: "Editor", status: "active", lastSeen: "hier", databases: ["Bibliotheque"] },
  { id: 4, name: "Nadia", email: "nadia@xmlforge.io", role: "Viewer", status: "active", lastSeen: "il y a 3 j", databases: ["Bibliotheque", "Demo"] },
  { id: 5, name: "Sofia", email: "sofia@xmlforge.io", role: "Editor", status: "invited", lastSeen: "jamais", databases: ["GestionRH"] },
  { id: 6, name: "Julien", email: "julien@xmlforge.io", role: "Viewer", status: "disabled", lastSeen: "il y a 2 mois", databases: [] },
  { id: 7, name: "Karim", email: "karim@xmlforge.io", role: "Viewer", status: "active", lastSeen: "il y a 6 h", databases: ["Demo"] },
];

/* ----------------------------------------------------------------- history */

export type Activity = { id: number; kind: "create" | "edit" | "import" | "export" | "sql" | "lock" | "user"; text: string; target?: string; at: string };

export const ACTIVITY: Activity[] = [
  { id: 1, kind: "create", text: "Table créée", target: "reservations", at: "il y a 4 min" },
  { id: 2, kind: "import", text: "Base importée depuis XML", target: "Bibliotheque", at: "il y a 38 min" },
  { id: 3, kind: "edit", text: "3 lignes mises à jour", target: "books", at: "il y a 1 h" },
  { id: 4, kind: "lock", text: "Table verrouillée", target: "loans", at: "il y a 2 h" },
  { id: 5, kind: "sql", text: "Requête exécutée", target: "SELECT * FROM users", at: "il y a 3 h" },
  { id: 6, kind: "export", text: "Export XML généré", target: "GestionRH", at: "hier, 18:12" },
  { id: 7, kind: "user", text: "Permission modifiée", target: "Camille → Edit", at: "hier, 16:40" },
  { id: 8, kind: "edit", text: "Colonne ajoutée", target: "books.stock", at: "il y a 2 j" },
];

export type QueryHistoryItem = {
  id: number;
  sql: string;
  at: string;
  ms: number;
  rows: number | null;
  status: "ok" | "error";
  saved?: boolean;
  db: string;
  error?: string;
};

export const QUERY_HISTORY: QueryHistoryItem[] = [
  { id: 1, sql: "SELECT * FROM users WHERE role = 'admin';", at: "il y a 3 min", ms: 4, rows: 1, status: "ok", saved: true, db: "Bibliotheque" },
  { id: 2, sql: "SELECT b.title, a.name FROM books b JOIN authors a ON a.id = b.author_id LIMIT 50;", at: "il y a 26 min", ms: 11, rows: 50, status: "ok", saved: true, db: "Bibliotheque" },
  { id: 3, sql: "UPDATE books SET stock = stock - 1 WHERE id = 42;", at: "il y a 1 h", ms: 6, rows: 1, status: "ok", db: "Bibliotheque" },
  { id: 4, sql: "SELECT * FROM loans WHERE returned_at IS NULL;", at: "il y a 2 h", ms: 0, rows: null, status: "error", db: "Bibliotheque", error: "Table 'loans' is protected — unlock required" },
  { id: 5, sql: "SELECT COUNT(*) FROM employees WHERE active = 1;", at: "hier", ms: 3, rows: 1, status: "ok", saved: true, db: "GestionRH" },
  { id: 6, sql: "DELETE FROM comments WHERE post_id = 12;", at: "hier", ms: 8, rows: 9, status: "ok", db: "Demo" },
  { id: 7, sql: "SELECT * FROM salary;", at: "il y a 2 j", ms: 0, rows: null, status: "error", db: "GestionRH", error: "Unknown table 'salary'" },
];

/* -------------------------------------------------------------------- logs */

export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

export const LOGS: { id: number; level: LogLevel; at: string; source: string; message: string }[] = [
  { id: 1, level: "INFO", at: "18:55:12.410", source: "engine", message: "Table 'reservations' created in Bibliotheque" },
  { id: 2, level: "INFO", at: "18:55:12.402", source: "engine", message: "Foreign key reservations.book_id → books.id registered" },
  { id: 3, level: "WARN", at: "18:54:58.117", source: "tcp", message: "TCP client 127.0.0.1:52431 disconnected unexpectedly" },
  { id: 4, level: "DEBUG", at: "18:54:41.990", source: "xml", message: "Parsed 428 nodes from books.xml in 34ms" },
  { id: 5, level: "INFO", at: "18:52:03.221", source: "rest", message: "POST /api/tables/loans/rows 200 (7ms)" },
  { id: 6, level: "ERROR", at: "18:49:37.008", source: "xml", message: "Invalid XML: unclosed tag <table> at line 84" },
  { id: 7, level: "INFO", at: "18:47:12.556", source: "auth", message: "Session refreshed for user 'Emmanuel'" },
  { id: 8, level: "WARN", at: "18:45:02.331", source: "engine", message: "Write on protected table 'loans' rejected" },
  { id: 9, level: "INFO", at: "18:44:19.774", source: "rest", message: "GET /api/databases 200 (3ms)" },
  { id: 10, level: "DEBUG", at: "18:43:58.101", source: "storage", message: "Compacted bibliotheque.xml (4.8 MB → 4.6 MB)" },
  { id: 11, level: "INFO", at: "18:41:10.005", source: "tcp", message: "TCP server listening on 127.0.0.1:3307" },
  { id: 12, level: "ERROR", at: "18:39:47.512", source: "sql", message: "Syntax error near 'FORM users' at position 6" },
  { id: 13, level: "INFO", at: "18:38:22.117", source: "engine", message: "Database 'GestionRH' exported to XML (9.2 MB)" },
  { id: 14, level: "WARN", at: "18:36:04.880", source: "auth", message: "Failed login attempt for 'julien' (account disabled)" },
  { id: 15, level: "DEBUG", at: "18:34:51.402", source: "xml", message: "Sync check: 3 files unchanged" },
  { id: 16, level: "INFO", at: "18:33:30.219", source: "rest", message: "PUT /api/tables/books/rows/42 200 (5ms)" },
  { id: 17, level: "INFO", at: "18:31:08.664", source: "engine", message: "Index rebuilt on books.title" },
  { id: 18, level: "ERROR", at: "18:29:44.301", source: "storage", message: "Write timeout on /var/xmlforge/data (retry 1/3)" },
  { id: 19, level: "INFO", at: "18:28:12.070", source: "storage", message: "Write retry succeeded" },
  { id: 20, level: "DEBUG", at: "18:26:59.884", source: "tcp", message: "Handshake OK with client 127.0.0.1:52422" },
  { id: 21, level: "INFO", at: "18:25:17.442", source: "auth", message: "User 'Camille' granted Edit on Bibliotheque" },
  { id: 22, level: "WARN", at: "18:22:41.009", source: "engine", message: "Column 'stock' has no index and is used in 12 filters" },
  { id: 23, level: "INFO", at: "18:20:03.771", source: "rest", message: "GET /api/tables/books/rows?page=3 200 (11ms)" },
  { id: 24, level: "DEBUG", at: "18:18:37.512", source: "xml", message: "Schema validation passed for Bibliotheque" },
];

/* ------------------------------------------------------------------- audit */

export const AUDIT: { id: number; user: string; action: string; target: string; at: string; ip: string; result: "success" | "denied" }[] = [
  { id: 1, user: "Emmanuel", action: "table.create", target: "Bibliotheque.reservations", at: "2026-02-20 18:55:12", ip: "127.0.0.1", result: "success" },
  { id: 2, user: "Emmanuel", action: "db.import", target: "Bibliotheque", at: "2026-02-20 18:17:44", ip: "127.0.0.1", result: "success" },
  { id: 3, user: "Camille", action: "row.update", target: "Bibliotheque.books", at: "2026-02-20 17:02:19", ip: "127.0.0.1", result: "success" },
  { id: 4, user: "Nadia", action: "row.delete", target: "Bibliotheque.loans", at: "2026-02-20 16:41:03", ip: "127.0.0.1", result: "denied" },
  { id: 5, user: "Emmanuel", action: "table.lock", target: "Bibliotheque.loans", at: "2026-02-20 16:39:55", ip: "127.0.0.1", result: "success" },
  { id: 6, user: "Alexandre", action: "sql.execute", target: "Bibliotheque", at: "2026-02-20 15:58:02", ip: "127.0.0.1", result: "success" },
  { id: 7, user: "Emmanuel", action: "permission.grant", target: "Camille → Edit", at: "2026-02-19 18:25:17", ip: "127.0.0.1", result: "success" },
  { id: 8, user: "Julien", action: "auth.login", target: "session", at: "2026-02-19 18:36:04", ip: "127.0.0.1", result: "denied" },
  { id: 9, user: "Emmanuel", action: "db.export", target: "GestionRH", at: "2026-02-19 18:38:22", ip: "127.0.0.1", result: "success" },
  { id: 10, user: "Emmanuel", action: "column.add", target: "Bibliotheque.books.stock", at: "2026-02-18 10:12:41", ip: "127.0.0.1", result: "success" },
  { id: 11, user: "Sofia", action: "row.insert", target: "GestionRH.leaves", at: "2026-02-18 09:44:07", ip: "127.0.0.1", result: "success" },
  { id: 12, user: "Karim", action: "db.open", target: "Demo", at: "2026-02-17 21:10:33", ip: "127.0.0.1", result: "success" },
];

/* ------------------------------------------------------------------ server */

export const SERVER = {
  version: "2.0.4",
  build: "2026.02.14-a71c3f",
  uptime: "6 j 14 h 32 min",
  startedAt: "2026-02-14 04:22:09",
  rest: { host: "localhost", port: 5000, status: "running" as const, requests: 12_482, latency: 7 },
  tcp: { host: "localhost", port: 3307, status: "running" as const, clients: 3, maxClients: 32 },
  engine: { status: "healthy" as const, documents: 14, lastSync: "il y a 34 s" },
  storage: { status: "healthy" as const, path: "/var/xmlforge/data", free: "38.2 GB", used: "1.4 GB" },
};

export const DIAGNOSTICS: { id: string; label: string; status: "ok" | "warn" | "error"; detail: string }[] = [
  { id: "d1", label: "XML engine", status: "ok", detail: "Moteur natif opérationnel (14 documents)" },
  { id: "d2", label: "REST API", status: "ok", detail: "localhost:5000 répond en 7 ms" },
  { id: "d3", label: "TCP server", status: "ok", detail: "3 clients connectés sur :3307" },
  { id: "d4", label: "Storage", status: "ok", detail: "1.4 GB utilisés, 38.2 GB libres" },
  { id: "d5", label: "Schema integrity", status: "warn", detail: "1 clé étrangère sans index (reservations.book_id)" },
  { id: "d6", label: "Backup", status: "warn", detail: "Dernière sauvegarde il y a 3 j" },
  { id: "d7", label: "XML syntax", status: "ok", detail: "Tous les documents valides" },
  { id: "d8", label: "Auth provider", status: "ok", detail: "Fournisseur local actif" },
];

/* ---------------------------------------------------------------- settings */

export const SETTINGS_DEFAULT = {
  startupDatabase: "bibliotheque",
  pageSize: 25,
  autoSyncXml: true,
  confirmDestructive: true,
  showNullBadges: true,
  theme: "dark",
  density: "comfortable",
  restEnabled: true,
  tcpEnabled: true,
  tcpPort: 3307,
  logLevel: "INFO",
  retentionDays: 30,
  protectOnImport: false,
  strictSchema: true,
};

/* ------------------------------------------------------------ XML snippets */

export function tableToXml(dbName: string, t: Table): string {
  const cols = t.cols
    .map((c) => {
      const attrs = [
        `name="${c.name}"`,
        `type="${c.type}"`,
        c.nullable ? `nullable="true"` : `nullable="false"`,
        c.pk ? `primary_key="true"` : null,
        c.ai ? `auto_increment="true"` : null,
        c.unique ? `unique="true"` : null,
        c.index ? `index="true"` : null,
        c.def ? `default="${c.def.replace(/'/g, "")}"` : null,
        c.fk ? `foreign_key="${c.fk.table}.${c.fk.column}"` : null,
      ]
        .filter(Boolean)
        .join(" ");
      return `        <column ${attrs} />`;
    })
    .join("\n");
  const rows = t.rows
    .slice(0, 4)
    .map((r) => {
      const cells = t.cols
        .map((c) => {
          const v = r[c.name];
          if (v === null || v === undefined) return `            <${c.name} null="true" />`;
          return `            <${c.name}>${String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</${c.name}>`;
        })
        .join("\n");
      return `        <row>\n${cells}\n        </row>`;
    })
    .join("\n");
  return [
    `<database name="${dbName}">`,
    `    <table name="${t.name}"${t.protected ? ' protected="true"' : ""}>`,
    `        <structure>`,
    cols,
    `        </structure>`,
    `        <data>`,
    rows,
    `        </data>`,
    `    </table>`,
    `</database>`,
  ].join("\n");
}

export function dbToXml(db: Db): string {
  const tables = db.tables
    .map((t) =>
      tableToXml(db.name, t)
        .split("\n")
        .slice(1, -1)
        .map((l) => (l.startsWith("    ") ? l : "    " + l))
        .join("\n"),
    )
    .join("\n");
  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<!-- XMLForge v2 · ${db.name} · ${db.scope === "common" ? "COMMON" : "PERSONAL"} -->`,
    `<database name="${db.name}" scope="${db.scope}" owner="${db.owner}" engine="xmlforge" version="2.0">`,
    tables,
    `</database>`,
  ].join("\n");
}

export function dbToSql(db: Db): string {
  const parts: string[] = [
    `-- XMLForge v2 · schéma généré depuis ${db.name}.xml`,
    `CREATE DATABASE IF NOT EXISTS \`${db.name}\`;`,
    `USE \`${db.name}\`;`,
    "",
  ];
  db.tables.forEach((t) => {
    const lines = t.cols.map((c) => {
      const bits = [`  \`${c.name}\` ${c.type}`];
      if (!c.nullable) bits.push("NOT NULL");
      if (c.ai) bits.push("AUTO_INCREMENT");
      if (c.def) bits.push(`DEFAULT ${c.def}`);
      if (c.unique && !c.pk) bits.push("UNIQUE");
      return bits.join(" ");
    });
    const pk = t.cols.find((c) => c.pk);
    if (pk) lines.push(`  PRIMARY KEY (\`${pk.name}\`)`);
    t.cols
      .filter((c) => c.fk)
      .forEach((c) =>
        lines.push(`  FOREIGN KEY (\`${c.name}\`) REFERENCES \`${c.fk!.table}\` (\`${c.fk!.column}\`)`),
      );
    parts.push(`CREATE TABLE \`${t.name}\` (\n${lines.join(",\n")}\n) ENGINE=XMLForge;`);
    t.cols
      .filter((c) => c.index && !c.pk)
      .forEach((c) => parts.push(`CREATE INDEX idx_${t.name}_${c.name} ON \`${t.name}\` (\`${c.name}\`);`));
    parts.push("");
  });
  return parts.join("\n");
}

export const IMPORT_SAMPLE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<database name="Bibliotheque" scope="personal" owner="Emmanuel">
    <table name="categories">
        <structure>
            <column name="id" type="INT" nullable="false" primary_key="true" auto_increment="true" />
            <column name="label" type="VARCHAR(80)" nullable="false" unique="true" />
            <column name="description" type="TEXT" nullable="true" />
        </structure>
        <data>
            <row>
                <id>1</id>
                <label>Roman</label>
                <description null="true" />
            </row>
            <row>
                <id>2</id>
                <label>Essai</label>
                <description>Ouvrages de réflexion.</description>
            </row>
        </data>
    </table>
</database>`;

/* ---------------------------------------------------------------- helpers */

export function getDb(id: string) {
  return DATABASES.find((d) => d.id === id);
}
export function getTable(db: Db | undefined, name: string) {
  return db?.tables.find((t) => t.name === name);
}
export function rowCount(t: Table) {
  return t.rows.length;
}
export function relOf(t: Table) {
  return t.cols.filter((c) => c.fk).map((c) => ({ from: `${t.name}.${c.name}`, to: `${c.fk!.table}.${c.fk!.column}` }));
}
export function formatSize(b: number) {
  if (b > 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024).toFixed(0)} KB`;
}
export const CURRENT_USER = { name: "Emmanuel", email: "nyx@xmlforge.io", role: "Admin" as const, initials: "EM" };
