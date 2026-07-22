import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'
import './MonacoEditor.css'

/**
 * Wrapper Monaco Editor qui rend EXACTEMENT le même HTML que la maquette
 * .code-pane > .code-pane-head + .code-pane-body
 * Prêt pour remplacement facile par Monaco sans refaire layout
 */
export function MonacoEditor({
  title,
  value,
  onChange,
  language = 'xml',
  readOnly = false,
  onCopy,
  onDownload,
  onFullscreen,
  id,
}){
  const [useMonaco, setUseMonaco] = useState(true)
  const paneId = id || `pane-${title.toLowerCase().replace(/\s+/g,'-')}`

  if(!useMonaco){
    // Fallback vers VSCodeEditor custom si Monaco échoue
    return (
      <div className="code-pane" id={paneId}>
        <div className="code-pane-head">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
          {title}
          <span className="lang-badge">{language.toUpperCase()}</span>
          <div className="code-pane-head-actions">
            <button className="icon-btn sm" title="Copier" onClick={onCopy}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button className="icon-btn sm" title="Télécharger" onClick={onDownload}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg></button>
            <button className="icon-btn sm" title="Plein écran" onClick={onFullscreen}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/></svg></button>
          </div>
        </div>
        <div className="code-pane-body" style={{padding:0}}>
          <textarea
            value={value}
            onChange={e=>onChange?.(e.target.value)}
            spellCheck={false}
            style={{width:'100%', height:'100%', background:'transparent', border:'none', color:'var(--text)', fontFamily:'var(--font-mono)', fontSize:12, lineHeight:'21px', padding:'14px 16px', resize:'none', outline:'none'}}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="code-pane" id={paneId}>
      <div className="code-pane-head">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
        {title}
        <span className="lang-badge">{language.toUpperCase()}</span>
        <div className="code-pane-head-actions">
          {readOnly && (
            <>
              <button className="icon-btn sm" title="↑ Convertir SQL → XML" onClick={onCopy} style={{display:'none'}} />
            </>
          )}
          <button className="icon-btn sm" title="Copier" onClick={onCopy}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
          <button className="icon-btn sm" title="Télécharger" onClick={onDownload}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
          </button>
          <button className="icon-btn sm" title="Plein écran" onClick={onFullscreen}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
          </button>
          <button className="icon-btn sm" title="Basculer éditeur classique" onClick={()=>setUseMonaco(false)} style={{fontSize:9}}>VS</button>
        </div>
      </div>
      <div className="code-pane-body" style={{padding:0, overflow:'hidden'}}>
        <Editor
          height="100%"
          language={language === 'xml' ? 'xml' : 'sql'}
          value={value}
          theme="vs-dark"
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: 'JetBrains Mono, monospace',
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
            tabSize: 2,
            background: '#13161D',
          }}
          onChange={(val)=> !readOnly && onChange?.(val)}
          onMount={(editor, monaco)=>{
            monaco.editor.defineTheme('xmlforge-dark', {
              base: 'vs-dark',
              inherit: true,
              rules: [
                { token: 'tag', foreground: '7CACFB' },
                { token: 'attribute.name', foreground: '5EE29A' },
                { token: 'attribute.value', foreground: 'FFB86B' },
                { token: 'keyword', foreground: 'C792EA' },
              ],
              colors: {
                'editor.background': '#13161D',
                'editorGutter.background': '#0F1117',
              }
            })
            monaco.editor.setTheme('xmlforge-dark')
          }}
        />
      </div>
    </div>
  )
}
