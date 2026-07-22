import { useRef, useEffect, useState } from 'react'
import './VSCodeEditor.css'

function escapeHtml(str){
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

function highlightXml(code){
  let html = escapeHtml(code)
  html = html.replace(/&lt;!--[\s\S]*?--&gt;/g, m=>`<span class="token-cmt">${m}</span>`)
  html = html.replace(/(&lt;\/?)([a-zA-Z0-9_:-]+)/g, '$1<span class="token-tag">$2</span>')
  // attr= 
  html = html.replace(/([a-zA-Z0-9_:.-]+)(\s*=\s*)/g, (m,name,eq)=>{
    if(name.includes('span')) return m
    return `<span class="token-attr">${name}</span>${eq}`
  })
  // double quoted values
  html = html.replace(/"([^"]*)"/g, (m,p1)=>`"<span class="token-val">${p1}</span>"`)
  // single quoted values - use char code to avoid parser issue
  html = html.replace(/&#39;([^&#]*)&#39;/g, (m,p1)=>`&#39;<span class="token-val">${p1}</span>&#39;`)
  // also handle regular single quotes that remain
  html = html.replace(/'([^']*)'/g, (m,p1)=>{
    if(m.includes('span')) return m
    return `'${'<span class="token-val">'+p1+'</span>'}'`
  })
  return html
}

function highlightSql(code){
  let html = escapeHtml(code)
  // keywords
  html = html.replace(/\b(CREATE|TABLE|PRIMARY|KEY|UNIQUE|NOT|NULL|AUTO_INCREMENT|DEFAULT|REFERENCES)\b/gi, m=>`<span class="token-kw">${m.toUpperCase()}</span>`)
  // types
  html = html.replace(/\b(INT|VARCHAR|TEXT|DATETIME|DECIMAL|BIGINT|BOOLEAN|TIMESTAMP)(\([^)]*\))?/gi, m=>`<span class="token-type">${m}</span>`)
  // numbers
  html = html.replace(/\b(\d+)\b/g, m=>`<span class="token-num">${m}</span>`)
  // table name after TABLE
  html = html.replace(/<span class="token-kw">TABLE<\/span>\s+([a-zA-Z0-9_]+)/g, '<span class="token-kw">TABLE</span> <span class="token-fn">$1</span>')
  return html
}

function getHighlighted(code, lang){
  if(lang==='xml') return highlightXml(code)
  if(lang==='sql') return highlightSql(code)
  return escapeHtml(code)
}

export function VSCodeEditor({
  title,
  value,
  onChange,
  language='xml',
  readOnly=false,
  onCopy,
  onDownload,
  onFullscreen,
  isFullscreen=false,
}){
  const textareaRef = useRef(null)
  const highlightRef = useRef(null)
  const gutterRef = useRef(null)
  const [lines, setLines] = useState(1)

  useEffect(()=>{
    setLines(value.split('\n').length || 1)
  },[value])

  const handleScroll = ()=>{
    if(!textareaRef.current) return
    const { scrollTop, scrollLeft } = textareaRef.current
    if(highlightRef.current){
      highlightRef.current.scrollTop = scrollTop
      highlightRef.current.scrollLeft = scrollLeft
    }
    if(gutterRef.current){
      gutterRef.current.scrollTop = scrollTop
    }
  }

  const highlighted = getHighlighted(value, language)

  return (
    <div className={`vs-editor ${isFullscreen?'vs-fullscreen':''} ${readOnly?'vs-readonly':''}`}>
      <div className="vs-header">
        <div className="vs-dots" aria-hidden>
          <span className="dot red" />
          <span className="dot yellow" />
          <span className="dot green" />
        </div>
        <div className="vs-title">{title}</div>
        <div className="vs-actions">
          <span className="vs-lang-badge">{language.toUpperCase()}</span>
          {readOnly && (
            <>
              <button className="vs-icon-btn" title="Copier" onClick={onCopy}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
              <button className="vs-icon-btn" title="Télécharger" onClick={onDownload}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
              </button>
              <button className="vs-icon-btn" title="Plein écran" onClick={onFullscreen}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
              </button>
            </>
          )}
        </div>
      </div>

      <div className="vs-body">
        <div className="vs-gutter" ref={gutterRef}>
          {Array.from({length:lines}, (_,i)=><div key={i} className="vs-line-num">{i+1}</div>)}
        </div>
        <div className="vs-content">
          <pre className="vs-highlight" ref={highlightRef} dangerouslySetInnerHTML={{__html: highlighted + '\n'}} />
          {!readOnly ? (
            <textarea
              ref={textareaRef}
              className="vs-textarea"
              value={value}
              onChange={e=>onChange?.(e.target.value)}
              onScroll={handleScroll}
              spellCheck={false}
              wrap="off"
            />
          ) : (
            <pre className="vs-pre-readonly">{value}</pre>
          )}
        </div>
      </div>
    </div>
  )
}
