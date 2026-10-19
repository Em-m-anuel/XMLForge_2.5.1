import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { Badge, Button, useToast } from "../components/ui";
import { cn } from "../utils/cn";

function esc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlightXml(src: string) {
  return esc(src).replace(
    /(&lt;!--[\s\S]*?--&gt;)|(&lt;\/?)([a-zA-Z_][\w:.-]*)|([a-zA-Z_][\w:.-]*)(=)("[^"]*")|(\/?&gt;)|(&amp;[\w#]+;)|(\d+)/g,
    (m, comment, open, tagName, attr, eq, str, close, ent, num) => {
      if (comment) return `<span class="tok-punc italic">${comment}</span>`;
      if (tagName) return `<span class="tok-punc">${open}</span><span class="tok-tag">${tagName}</span>`;
      if (attr) return `<span class="tok-attr">${attr}</span><span class="tok-punc">${eq}</span><span class="tok-str">${str}</span>`;
      if (close) return `<span class="tok-punc">${close}</span>`;
      if (ent) return `<span class="tok-num">${ent}</span>`;
      if (num) return `<span class="tok-num">${num}</span>`;
      return m;
    },
  );
}

type Issue = { line: number; message: string };

function validateXmlLocal(src: string): Issue[] {
  const issues: Issue[] = [];
  const stack: { name: string; line: number }[] = [];
  const lines = src.split("\n");
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith("<?") || line.startsWith("<!--")) return;
    const re = /<(\/?)([a-zA-Z_][\w:.-]*)([^>]*?)(\/?)>/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line))) {
      const [, closing, name, attrs, selfClose] = m;
      if (closing) {
        const last = stack.pop();
        if (!last) issues.push({ line: i + 1, message: `Fermeture inattendue </${name}>` });
        else if (last.name !== name)
          issues.push({ line: i + 1, message: `Balise </${name}> ne correspond pas à <${last.name}> ouverte ligne ${last.line}` });
      } else if (!selfClose) {
        stack.push({ name, line: i + 1 });
      }
      if (attrs && /=\s*$/.test(attrs)) issues.push({ line: i + 1, message: `Attribut sans valeur dans <${name}>` });
    }
  });
  stack.forEach((s) => issues.push({ line: s.line, message: `Balise <${s.name}> non fermée` }));
  return issues;
}

export function XmlPanel({
  doc,
  title = "Document XML",
  subtitle,
  height = 420,
  onApply,
  onLoad,
  loading,
  readOnly,
  meta,
}: {
  doc: string;
  title?: string;
  subtitle?: string;
  language?: "xml" | "sql";
  height?: number;
  onApply?: (value: string) => Promise<void> | void;
  onLoad?: () => void;
  loading?: boolean;
  readOnly?: boolean;
  meta?: { label: string; value: string }[];
}) {
  const toast = useToast();
  const [value, setValue] = useState(doc);
  const [issues, setIssues] = useState<Issue[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [validated, setValidated] = useState<boolean | null>(null);
  const [wrap, setWrap] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  useEffect(() => {
    setValue(doc);
    setIssues(null);
    setValidated(null);
  }, [doc]);

  const html = useMemo(() => highlightXml(value), [value]);
  const dirty = value !== doc;
  const lines = value.split("\n").length;

  // Gestion modifications en cours — confirmation avant perte
  useEffect(() => {
    if (!dirty) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [dirty]);

  const diff = useMemo(() => {
    if (!dirty) return [];
    const oldLines = doc.split("\n");
    const newLines = value.split("\n");
    const max = Math.max(oldLines.length, newLines.length);
    const out: { type: 'same' | 'add' | 'del' | 'mod'; old?: string; neu?: string; line: number }[] = [];
    for (let i = 0; i < max; i++) {
      const o = oldLines[i];
      const n = newLines[i];
      if (o === n) {
        out.push({ type: 'same', old: o, neu: n, line: i + 1 });
      } else if (o === undefined) {
        out.push({ type: 'add', neu: n, line: i + 1 });
      } else if (n === undefined) {
        out.push({ type: 'del', old: o, line: i + 1 });
      } else {
        out.push({ type: 'mod', old: o, neu: n, line: i + 1 });
      }
    }
    return out;
  }, [doc, value, dirty]);

  const validate = () => {
    setBusy(true);
    setTimeout(() => {
      const found = validateXmlLocal(value);
      setIssues(found);
      setValidated(found.length === 0);
      setBusy(false);
      if (found.length === 0) toast({ kind: "success", title: "Document valide", detail: `${lines} lignes` });
      else toast({ kind: "error", title: `${found.length} erreur(s)`, detail: found[0].message });
    }, 200);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      toast({ kind: "success", title: "Copié" });
    } catch {
      toast({ kind: "error", title: "Erreur copie" });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([value], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title}.xml`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast({ kind: "success", title: "Téléchargé", detail: `${title}.xml` });
  };

  const handleApply = async () => {
    if (!onApply) return;
    setBusy(true);
    try {
      await onApply(value);
    } catch (e: any) {
      // erreur déjà toastée dans store
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-raised px-3 py-1.5">
        <Icon name="code" size={13} className="text-xml" />
        <span className="text-[12px] font-medium text-fg">{title}</span>
        <Badge tone="xml" mono>
          XML
        </Badge>
        {subtitle && <span className="text-[11px] text-dim">{subtitle}</span>}
        {dirty && (
          <Badge tone="warn" icon="pencil">
            modifié
          </Badge>
        )}
        {validated === true && (
          <Badge tone="ok" icon="checkCircle">
            valide
          </Badge>
        )}
        {validated === false && (
          <Badge tone="danger" icon="alert">
            {issues?.length} erreurs
          </Badge>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-1.5">
          {dirty && (
            <Button size="xs" variant={showDiff ? "primary" : "ghost"} onClick={() => setShowDiff(v => !v)}>
              {showDiff ? "Éditeur" : "Diff"}
            </Button>
          )}
          <Button size="xs" variant="ghost" onClick={() => setWrap((w) => !w)} className={wrap ? "border-accent/40" : ""}>
            Wrap
          </Button>
          <Button size="xs" variant="ghost" icon="copy" onClick={handleCopy}>
            Copier
          </Button>
          <Button size="xs" variant="ghost" icon="download" onClick={handleDownload}>
            Télécharger
          </Button>
          <Button size="xs" variant="ghost" icon="refresh" onClick={() => { setValue(doc); setIssues(null); setValidated(null); setShowDiff(false); }}>
            Reset
          </Button>
          <Button size="xs" variant="ghost" icon="refresh" onClick={() => onLoad?.()}>
            Recharger
          </Button>
          <Button size="xs" loading={busy} onClick={validate} icon="checkCircle">
            Valider
          </Button>
          <Button
            size="xs"
            variant="primary"
            disabled={!dirty || readOnly || validated === false || loading}
            loading={busy}
            onClick={handleApply}
          >
            Appliquer
          </Button>
        </div>
      </div>

      {meta && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-line-soft bg-surface px-3 py-1.5 text-[11px]">
          {meta.map((m) => (
            <span key={m.label} className="flex items-center gap-1.5">
              <span className="text-dim">{m.label}</span>
              <span className="font-mono text-muted">{m.value}</span>
            </span>
          ))}
        </div>
      )}

      {dirty && (
        <div className="flex items-center gap-2 border-b border-warn/30 bg-warn-soft px-3 py-1.5 text-[11.5px] text-warn">
          <Icon name="alert" size={12} />
          <span>Modifications non appliquées — le document local diffère du stockage XML</span>
          <div className="flex-1" />
          <Button size="xs" variant="ghost" onClick={() => { setValue(doc); setShowDiff(false); }}>Abandonner</Button>
          <Button size="xs" variant="primary" disabled={validated === false} loading={busy} onClick={handleApply}>Appliquer</Button>
        </div>
      )}

      <div className="flex" style={{ height }}>
        <div
          className="select-none overflow-hidden border-r border-line-soft bg-surface py-2.5 text-right font-mono text-[11.5px] leading-[1.5] text-[#3f3f4a]"
          style={{ height }}
        >
          {showDiff ? diff.map((d, i) => (
            <div key={i} className={cn("px-2", d.type === 'add' && "bg-ok-soft text-ok", d.type === 'del' && "bg-danger-soft text-danger", d.type === 'mod' && "bg-warn-soft text-warn")}>
              {d.line}
            </div>
          )) : Array.from({ length: lines }).map((_, i) => (
            <div key={i} className="px-2">
              {i + 1}
            </div>
          ))}
        </div>
        <div className="relative flex-1 overflow-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center text-[12px] text-dim">Chargement XML...</div>
          ) : showDiff ? (
            <div className="p-0 font-mono text-[11px] leading-[1.5]">
              {diff.map((d, i) => (
                <div key={i} className={cn("flex gap-2 px-3 py-0.5", d.type === 'add' && "bg-ok-soft/40 text-ok", d.type === 'del' && "bg-danger-soft/40 text-danger", d.type === 'mod' && "bg-warn-soft/30 text-warn", d.type === 'same' && "text-muted")}>
                  <span className="w-6 shrink-0 text-dim">{d.type === 'add' ? '+' : d.type === 'del' ? '-' : d.type === 'mod' ? '~' : ' '}</span>
                  <span className="truncate">{d.type === 'del' ? d.old : d.type === 'add' ? d.neu : d.type === 'mod' ? `${d.old} → ${d.neu}` : d.old}</span>
                </div>
              ))}
              <div className="border-t border-line bg-raised px-3 py-1 text-[10px] text-dim">
                Diff local : + ajout, - suppression, ~ modification — non persisté tant que Appliquer n'a pas réussi
              </div>
            </div>
          ) : (
            <>
              <pre
                aria-hidden
                className={cn(
                  "pointer-events-none absolute inset-0 px-3 py-2.5 font-mono text-[12px] leading-[1.5] text-tok-text",
                  wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre",
                )}
                dangerouslySetInnerHTML={{ __html: html + "\n" }}
              />
              <textarea
                value={value}
                readOnly={readOnly}
                spellCheck={false}
                onChange={(e) => {
                  setValue(e.target.value);
                  setValidated(null);
                }}
                className="relative h-full w-full resize-none overflow-hidden bg-transparent px-3 py-2.5 font-mono text-[12px] leading-[1.5] text-transparent caret-accent focus:outline-none"
                style={{ whiteSpace: wrap ? "pre-wrap" : "pre", overflowX: wrap ? "hidden" : "auto" }}
              />
            </>
          )}
        </div>
      </div>

      {issues && issues.length > 0 && (
        <div className="border-t border-line bg-surface">
          <div className="flex items-center gap-2 border-b border-line-soft px-3 py-1.5">
            <Icon name="alert" size={12} className="text-danger" />
            <span className="text-[11.5px] font-medium text-danger">{issues.length} problème(s)</span>
          </div>
          <ul className="max-h-28 overflow-y-auto">
            {issues.slice(0, 20).map((is, i) => (
              <li key={i} className="flex items-center gap-3 px-3 py-1 font-mono text-[11.5px]">
                <span className="w-10 shrink-0 text-dim">L{is.line}</span>
                <span className="text-muted">{is.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-3 border-t border-line bg-raised px-3 py-1.5 text-[11px] text-dim">
        <span className="font-mono">{lines} lignes</span>
        <span className="font-mono">{(new TextEncoder().encode(value).length / 1024).toFixed(1)} KB</span>
        <span>UTF-8</span>
        <div className="flex-1" />
        <span className="font-mono">{value.length} caractères</span>
      </div>
    </div>
  );
}
