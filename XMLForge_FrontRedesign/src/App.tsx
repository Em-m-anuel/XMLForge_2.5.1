import { useEffect } from "react";
import { OverlayProvider, ToastProvider } from "./components/ui";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { StoreProvider, useStore } from "./store";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import { CommandPalette } from "./components/layout/CommandPalette";
import { PageHeader } from "./components/layout/PageHeader";
import { LoginView } from "./views/LoginView";
import { Overview } from "./views/Overview";
import { DatabasesView } from "./views/DatabasesView";
import { DatabaseView } from "./views/DatabaseView";
import { TableWorkspace } from "./views/TableWorkspace";
import { SqlConsole } from "./views/SqlConsole";
import { RelationDiagram } from "./views/RelationDiagram";
import { XmlPanel } from "./views/XmlPanel";
import { ImportExport } from "./views/ImportExport";
import { AdminView } from "./views/AdminView";
import { ServerView } from "./views/ServerView";
import { LogsView } from "./views/LogsView";
import { SettingsView } from "./views/SettingsView";

function ToolsPage() {
  const { nav, dbs, activeDb, tables, fetchXml, xmlDoc, xmlLoading } = useStore();
  const db = dbs.find((d) => String(d.id) === activeDb);

  useEffect(() => {
    if (db && (nav.v === "xml" || nav.v === "sql" || nav.v === "relations")) {
      if (nav.v === "xml") {
        fetchXml(undefined, String(db.id));
      }
    }
  }, [db, nav.v, fetchXml]);

  if (!db) {
    return (
      <div className="px-6 py-10 text-center text-[13px] text-dim">
        Aucune base sélectionnée. Allez dans Bases de données.
      </div>
    );
  }

  if (nav.v === "sql")
    return (
      <div className="anim-fade">
        <PageHeader
          icon="terminal"
          accent
          title="Console SQL"
          subtitle={`Interrogez ${db.name} avec le moteur XML natif`}
          meta={[
            { label: "Base", value: db.name, icon: "database" },
            { label: "Tables", value: db.tables_count, icon: "table" },
            { label: "Moteur", value: "XMLForge", icon: "cpu" },
          ]}
        />
        <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
          <ErrorBoundary name="SqlConsole">
            <SqlConsole dbId={String(db.id)} initialQuery={`SELECT *\nFROM ${tables[0]?.name ?? "users"}\nLIMIT 25;`} />
          </ErrorBoundary>
        </div>
      </div>
    );

  if (nav.v === "relations")
    return (
      <div className="anim-fade">
        <PageHeader
          icon="relations"
          accent
          title="Relations"
          subtitle={`Schéma relationnel de ${db.name}`}
          meta={[
            { label: "Tables", value: tables.length, icon: "table" },
            { label: "Moteur", value: "XMLForge", icon: "cpu" },
          ]}
        />
        <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
          <ErrorBoundary name="RelationDiagram">
            <RelationDiagram dbId={String(db.id)} />
          </ErrorBoundary>
        </div>
      </div>
    );

  return (
    <div className="anim-fade">
      <PageHeader
        icon="code"
        accent
        title="XML"
        subtitle={`Document XML natif de ${db.name}`}
        meta={[
          { label: "Base", value: db.name, icon: "database" },
          { label: "Moteur", value: "XMLForge 2.0", icon: "cpu" },
          { label: "Stockage", value: "XML natif", icon: "hdd" },
        ]}
      />
      <div className="mx-auto w-full max-w-[1400px] px-6 py-5">
        <ErrorBoundary name="XmlPanel">
          <XmlPanel
            doc={xmlDoc}
            title={`${db.name}.xml`}
            subtitle={`${tables.length} tables · Version ${db.document_version}`}
            height={560}
            loading={xmlLoading}
            onLoad={() => fetchXml(undefined, String(db.id))}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}

function CurrentView() {
  const { nav } = useStore();
  switch (nav.v) {
    case "overview":
      return <Overview />;
    case "databases":
      return <DatabasesView />;
    case "db":
      return <DatabaseView dbId={nav.db} tab={nav.tab} />;
    case "table":
      return <TableWorkspace dbId={nav.db} table={nav.table} tab={nav.tab} />;
    case "import":
      return <ImportExport />;
    case "admin":
      return <AdminView tab={nav.tab} />;
    case "server":
      return <ServerView />;
    case "logs":
      return <LogsView />;
    case "settings":
      return <SettingsView />;
    default:
      return <ToolsPage />;
  }
}

function Shell() {
  const { session, palette, setPalette } = useStore();

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette(!palette);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [palette, setPalette]);

  if (!session.authenticated) return <LoginView />;

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <ErrorBoundary name="CurrentView">
            <CurrentView />
          </ErrorBoundary>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <OverlayProvider>
        <StoreProvider>
          <Shell />
        </StoreProvider>
      </OverlayProvider>
    </ToastProvider>
  );
}
