import { useState } from "react";
import { Icon, type IconName } from "../components/Icon";
import {
  Badge,
  Button,
  Field,
  Input,
  Panel,
  SectionHeader,
  Select,
  Switch,
  useToast,
} from "../components/ui";
import { ShutdownModal } from "../components/ShutdownModal";
import { PageHeader } from "../components/layout/PageHeader";
import { cn } from "../utils/cn";
import { useStore } from "../store";

const SECTIONS: { id: string; label: string; icon: IconName }[] = [
  { id: "general", label: "Général", icon: "sliders" },
  { id: "appearance", label: "Apparence", icon: "eye" },
  { id: "database", label: "Base de données", icon: "database" },
  { id: "server", label: "Serveur", icon: "server" },
  { id: "security", label: "Sécurité", icon: "shield" },
  { id: "storage", label: "Stockage", icon: "hdd" },
  { id: "advanced", label: "Avancé", icon: "settings" },
];

export function SettingsView() {
  const { dbs, serverHealth, tcpStatus, isAdmin } = useStore();
  const toast = useToast();
  const [section, setSection] = useState("general");
  const [pageSize, setPageSize] = useState(25);
  const [theme, setTheme] = useState("dark");
  const [shutdownOpen, setShutdownOpen] = useState(false);

  return (
    <div className="anim-fade">
      <PageHeader
        icon="settings"
        accent
        title="Paramètres"
        subtitle="Configuration locale XMLForge"
      />

      <div className="mx-auto grid w-full max-w-[1200px] gap-4 px-6 py-5 lg:grid-cols-[200px_1fr]">
        <nav className="flex flex-col gap-0.5">
          {SECTIONS.map((sec) => (
            <button
              key={sec.id}
              onClick={() => setSection(sec.id)}
              className={cn(
                "flex h-8 items-center gap-2 rounded-md px-2.5 text-[12.5px] transition-colors",
                section === sec.id ? "bg-raised text-fg" : "text-muted hover:bg-surface hover:text-fg",
              )}
            >
              <Icon name={sec.icon} size={13} className={section === sec.id ? "text-accent" : "text-dim"} />
              {sec.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0 space-y-4">
          {section === "general" && (
            <Panel>
              <SectionHeader title="Général" description="Affichage des données" />
              <div className="mt-4 space-y-4">
                <Field label="Lignes par page" hint="Nombre de lignes dans la vue Données">
                  <Select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className="w-40">
                    {[15, 25, 50, 100].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="space-y-3 border-t border-line pt-3">
                  <Switch checked={true} onChange={() => {}} label="Afficher badges NULL" description="Badge explicite pour valeurs nulles." />
                  <Switch checked={true} onChange={() => {}} label="Confirmer actions destructives" description="Confirmation avant suppression." />
                </div>
              </div>
            </Panel>
          )}

          {section === "server" && (
            <Panel>
              <SectionHeader title="Serveur" description="REST et TCP locaux" />
              <div className="mt-4 space-y-3">
                <div className="flex justify-between text-[12px]"><span className="text-dim">REST</span><span className="font-mono text-muted">localhost:5000</span></div>
                <div className="flex justify-between text-[12px]"><span className="text-dim">TCP</span><span className="font-mono text-muted">localhost:3307</span></div>
                <div className="flex justify-between text-[12px]"><span className="text-dim">Version</span><span className="font-mono text-muted">{serverHealth?.version || "5.0.0"}</span></div>
                <div className="flex justify-between text-[12px]"><span className="text-dim">TCP actif</span><span className="font-mono text-muted">{tcpStatus?.running ? "Oui" : "Non"}</span></div>
              </div>
            </Panel>
          )}

          {section === "storage" && (
            <Panel>
              <SectionHeader title="Stockage" description="Emplacement documents XML" />
              <div className="mt-4 space-y-4">
                <Field label="Type stockage">
                  <Input value="XML natif uniquement" readOnly className="w-96 opacity-70" />
                </Field>
                <Field label="SQLite">
                  <Input value="Absent (retiré définitivement)" readOnly className="w-96 opacity-70" />
                </Field>
                <div className="rounded-md border border-line-soft bg-panel p-3 text-[12px] text-muted">
                  En mode installé, les données sont sous %LOCALAPPDATA%\XMLForge\data\ (sécurité, jamais dans Program Files).
                </div>
              </div>
            </Panel>
          )}

          {section === "advanced" && (
            <div className="space-y-4">
              <Panel>
                <SectionHeader title="Avancé" description="Opérations système" />
                <p className="mt-3 text-[12px] text-dim">Cette section est informative. La configuration réelle se fait via variables d'environnement côté backend (XMLFORGE_*, voir .env.example).</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {[
                    { k: "Moteur", v: "XMLForge 2.0 (XML natif)" },
                    { k: "Bases", v: `${dbs.length} bases` },
                    { k: "Stockage", v: "XML uniquement" },
                  ].map((x) => (
                    <div key={x.k} className="rounded-md border border-line-soft bg-panel px-3 py-2">
                      <p className="text-[11px] text-dim">{x.k}</p>
                      <p className="mt-0.5 font-mono text-[12px] text-muted">{x.v}</p>
                    </div>
                  ))}
                </div>
                {isAdmin && (
                  <div className="mt-6 border-t border-line pt-4">
                    <p className="text-[12px] font-medium text-fg">Fermeture application</p>
                    <p className="mt-1 text-[11.5px] text-dim">Arrête proprement Flask :5000 et TCP :3307, libère les ports.</p>
                    <Button size="sm" variant="danger" icon="power" className="mt-3" onClick={() => setShutdownOpen(true)}>
                      Fermer XMLForge
                    </Button>
                  </div>
                )}
              </Panel>
            </div>
          )}

          {section !== "general" && section !== "server" && section !== "storage" && section !== "advanced" && (
            <Panel>
              <SectionHeader title={SECTIONS.find(s => s.id === section)?.label || section} />
              <p className="mt-3 text-[12px] text-dim">Cette section est informative. La configuration réelle se fait via variables d'environnement côté backend (XMLFORGE_*, voir .env.example).</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {[
                  { k: "Moteur", v: "XMLForge 2.0 (XML natif)" },
                  { k: "Bases", v: `${dbs.length} bases` },
                  { k: "Stockage", v: "XML uniquement" },
                ].map((x) => (
                  <div key={x.k} className="rounded-md border border-line-soft bg-panel px-3 py-2">
                    <p className="text-[11px] text-dim">{x.k}</p>
                    <p className="mt-0.5 font-mono text-[12px] text-muted">{x.v}</p>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
      <ShutdownModal open={shutdownOpen} onClose={() => setShutdownOpen(false)} />
    </div>
  );
}
