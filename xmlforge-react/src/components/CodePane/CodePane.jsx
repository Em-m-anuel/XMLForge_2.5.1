import './CodePane.css'

export function CodePane({ title, icon, children, actions }){
  return (
    <div className="code-pane">
      <div className="code-pane-head">
        {icon && <span className="code-pane-icon">{icon}</span>}
        <span>{title}</span>
        <div className="dots"><span className="d1"/><span className="d2"/><span className="d3"/></div>
      </div>
      <div className="code-pane-body">{children}</div>
      {actions && <div className="code-pane-actions">{actions}</div>}
    </div>
  )
}
