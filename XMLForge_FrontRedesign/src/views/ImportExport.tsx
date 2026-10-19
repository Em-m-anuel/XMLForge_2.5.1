import { useRef, useState } from "react";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Field,
  Panel,
  SectionHeader,
  Select,
  Switch,
  Tabs,
  useToast,
} from "../components/ui";
import { PageHeader } from "../components/layout/PageHeader";
import { cn } from "../utils/cn";
import { useStore } from "../store";
import { XmlPanel } from "./XmlPanel";
import { xmlService } from "../api/xml";

type Mode = "import" | "export" | "xml2sql" | "sql2xml";

const SAMPLE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<database name="Bibliotheque" scope="personal">
    <table name="categories">
        <columns>
            <column name="id" type="INT" nullable="false" primary_key="true" auto_increment="true" />
            <column name="label" type="VARCHAR" length="80" nullable="false" unique="true" />
        </columns>
        <rows>
            <row><data><id>1</id><label>Roman</label></data></row>
        </rows>
    </table>
</database>`;

const SAMPLE_SQL = `CREATE TABLE categories (
  id INT NOT NULL AUTO_INCREMENT,
  label VARCHAR(80) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=XMLForge;`;

export function ImportExport() {
  const { dbs, activeDb, setActiveDb, tables, fetchTables } = useStore();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>("import");
  const [dbId, setDbId] = useState(activeDb);
  const db = dbs.find((d) => String(d.id) === dbId);
  const fileRef = useRef<HTMLInputElement>(null);

  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number>(0);
  const [fileContent, setFileContent] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [sqlSource, setSqlSource] = useState(SAMPLE_SQL);
  const [xmlResult, setXmlResult] = useState("");
  const [sqlResult, setSqlResult] = useState("");
  const [validationMsg, setValidationMsg] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setFileName(file.name);
    setFileSize(file.size);
    const text = await file.text();
    setFileContent(text);
    // Validation simple locale
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(text, "text/xml");
      const err = doc.getElementsByTagName("parsererror");
      if (err.length > 0) {
        setValidationMsg(`XML invalide : ${err[0].textContent?.slice(0, 100) || "erreur"}`);
      } else {
        const tables = doc.getElementsByTagName("table").length;
        const rows = doc.getElementsByTagName("row").length;
        setValidationMsg(`XML valide : ${tables} table(s), ${rows} ligne(s) détectées`);
      }
    } catch (e: any) {
      setValidationMsg(`Erreur lecture : ${e.message}`);
    }
  };

  const clearFile = () => {
    setFileName(null);
    setFileSize(0);
    setFileContent("");
    setValidationMsg(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleImportXml = async () => {
    if (!fileContent) {
      toast({ kind: "error", title: "Aucun fichier" });
      return;
    }
    setBusy(true);
    try {
      // Si on a un dbId, on sync la base, sinon on importe comme nouvelle base
      if (dbId) {
        await xmlService.syncDatabase(dbId, fileContent);
        toast({ kind: "success", title: "Import réussi", detail: `${db?.name} synchronisée` });
        await fetchTables(dbId);
      } else {
        const res = await xmlService.importXmlRaw(fileContent);
        toast({ kind: "success", title: "Base importée", detail: res.name || "Nouvelle base" });
      }
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur import", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  const handleExportXml = async () => {
    if (!dbId) return;
    setBusy(true);
    try {
      const res = await xmlService.exportDatabaseXml(dbId);
      setXmlResult(res.xml);
      // Téléchargement
      const blob = new Blob([res.xml], { type: "application/xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${db?.name || 'database'}.xml`;
      a.click();
      URL.revokeObjectURL(url);
      toast({ kind: "success", title: "Export XML", detail: `${db?.name}.xml` });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur export", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  const handleXmlToSql = async () => {
    if (!dbId) return;
    setBusy(true);
    try {
      const xmlRes = await xmlService.exportDatabaseXml(dbId);
      const sqlRes = await xmlService.xmlToSql(xmlRes.xml, db?.name);
      setSqlResult(sqlRes.sql);
      toast({ kind: "success", title: "Conversion XML → SQL" });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur conversion", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  const handleSqlToXml = async () => {
    setBusy(true);
    try {
      const res = await xmlService.sqlToXml(sqlSource, "Converted");
      setXmlResult(res.xml);
      toast({ kind: "success", title: "Conversion SQL → XML" });
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur conversion", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="anim-fade">
      <PageHeader
        icon="download"
        accent
        title="Import & Export"
        subtitle="Échangez des documents XML avec le moteur natif"
        meta={[
          { label: "Base", value: db?.name ?? "—", icon: "database" },
          { label: "Tables", value: tables.length, icon: "table" },
          { label: "Stockage", value: "XML natif", icon: "hdd" },
        ]}
        actions={
          <>
            <Select
              value={dbId}
              onChange={(e) => {
                setDbId(e.target.value);
                setActiveDb(e.target.value);
              }}
            >
              <option value="">— Nouvelle base —</option>
              {dbs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </>
        }
        tabs={
          <Tabs
            tabs={[
              { id: "import" as const, label: "Importer XML", icon: "upload" },
              { id: "export" as const, label: "Exporter XML", icon: "download" },
              { id: "xml2sql" as const, label: "XML → SQL", icon: "terminal" },
              { id: "sql2xml" as const, label: "SQL → XML", icon: "code" },
            ]}
            value={mode}
            onChange={setMode as any}
          />
        }
      />

      <div className="mx-auto grid w-full max-w-[1400px] gap-4 px-6 py-5 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          {mode === "import" && (
            <div className="space-y-4">
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) handleFile(f);
                }}
                className={cn(
                  "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center",
                  dragging ? "border-accent/70 bg-accent-soft/30" : "border-line bg-surface hover:border-[#363641]",
                )}
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-raised text-xml">
                  <Icon name="upload" size={16} />
                </span>
                <p className="text-[13.5px] font-medium text-fg">
                  {fileName ? fileName : "Déposez votre fichier XML ici"}
                </p>
                <p className="text-[12px] text-muted">Documents .xml conformes au schéma XMLForge</p>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xml"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleFile(f);
                    }}
                  />
                  <Button size="sm" icon="folder" onClick={() => fileRef.current?.click()}>
                    Choisir fichier
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setFileName("exemple.xml");
                      setFileSize(SAMPLE_XML.length);
                      setFileContent(SAMPLE_XML);
                      setValidationMsg("Exemple chargé : 1 table, 1 ligne");
                    }}
                  >
                    Utiliser exemple
                  </Button>
                </div>
              </div>

              {fileName && (
                <div className="rounded-lg border border-line bg-surface p-3">
                  <div className="flex items-center gap-2">
                    <Icon name="code" size={14} className="text-xml" />
                    <span className="font-mono text-[12px] text-fg">{fileName}</span>
                    <Badge tone="neutral" mono>{(fileSize / 1024).toFixed(1)} KB</Badge>
                    {validationMsg && <Badge tone={validationMsg.includes("valide") ? "ok" : "danger"}>{validationMsg.includes("valide") ? "Valide" : "Invalide"}</Badge>}
                    <div className="flex-1" />
                    <Button size="xs" variant="ghost" onClick={clearFile}>Changer fichier</Button>
                    <Button size="xs" variant="ghost" onClick={clearFile}>Annuler</Button>
                  </div>
                  {validationMsg && <p className="mt-2 text-[11.5px] text-muted">{validationMsg}</p>}
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="primary" icon="upload" loading={busy} disabled={!fileContent || !!validationMsg?.includes("invalide")} onClick={handleImportXml}>
                  Lancer l'import
                </Button>
                <Button variant="ghost" onClick={clearFile}>
                  Annuler
                </Button>
                {busy && <span className="flex items-center gap-1 text-[11px] text-dim"><span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-accent" />Import en cours...</span>}
              </div>

              {fileContent && (
                <XmlPanel
                  doc={fileContent}
                  title={fileName || "import.xml"}
                  subtitle="Aperçu avant import — vérifiez avant de lancer"
                  height={400}
                />
              )}
            </div>
          )}

          {mode === "export" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Button variant="primary" icon="download" loading={busy} onClick={handleExportXml} disabled={!dbId}>
                  Exporter XML
                </Button>
                <Button variant="ghost" icon="refresh" onClick={() => { setXmlResult(""); toast({ kind: "info", title: "Aperçu effacé" }); }}>
                  Effacer
                </Button>
              </div>
              <XmlPanel
                doc={xmlResult || "<!-- Cliquez Exporter pour générer le XML réel depuis le backend -->"}
                title={`${db?.name || 'export'}.xml`}
                subtitle="Document XML réel depuis le moteur"
                height={500}
                readOnly
              />
            </div>
          )}

          {mode === "xml2sql" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Badge tone="xml">XML</Badge>
                <Icon name="arrowRight" size={13} className="text-dim" />
                <Badge tone="accent">SQL</Badge>
                <div className="flex-1" />
                <Button variant="primary" icon="refresh" loading={busy} onClick={handleXmlToSql} disabled={!dbId}>
                  Convertir
                </Button>
              </div>
              <XmlPanel doc={sqlResult || "-- Cliquez Convertir pour générer le SQL depuis le XML réel"} title="SQL généré" language="sql" height={500} readOnly />
            </div>
          )}

          {mode === "sql2xml" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Badge tone="accent">SQL</Badge>
                <Icon name="arrowRight" size={13} className="text-dim" />
                <Badge tone="xml">XML</Badge>
                <div className="flex-1" />
                <Button variant="primary" icon="refresh" loading={busy} onClick={handleSqlToXml}>
                  Convertir
                </Button>
              </div>
              <div className="grid gap-4 xl:grid-cols-2">
                <XmlPanel doc={sqlSource} title="SQL source" language="sql" height={400} onApply={async (v) => setSqlSource(v)} />
                <XmlPanel doc={xmlResult || "<!-- Résultat conversion SQL → XML apparaîtra ici -->"} title="XML généré" height={400} readOnly />
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Panel>
            <SectionHeader title="Moteur" />
            <ul className="mt-2.5 space-y-2 text-[12px]">
              {[
                { k: "Stockage", v: "XML natif" },
                { k: "Validation", v: "XSD strict" },
                { k: "Sync", v: "Automatique" },
                { k: "SQLite", v: "Absent" },
              ].map((r) => (
                <li key={r.k} className="flex items-center justify-between">
                  <span className="text-dim">{r.k}</span>
                  <span className="font-mono text-[11.5px] text-muted">{r.v}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel>
            <SectionHeader title="Base active" />
            <div className="mt-2 text-[12px] text-muted">
              {db ? (
                <>
                  <p className="font-medium text-fg">{db.name}</p>
                  <p className="mt-1">Tables: {db.tables_count}</p>
                  <p>Version: {db.document_version}</p>
                  <p>Scope: {db.scope}</p>
                </>
              ) : (
                <p>Aucune base sélectionnée — import créera une nouvelle base.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
