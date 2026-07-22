import './Badge.css'

export function Badge({ children, variant='blue', dot, className='', ...props }){
  return (
    <span className={`badge badge-${variant} ${className}`} {...props}>
      {dot && <span className="badge-dot" style={{background:dot}} />}
      {children}
    </span>
  )
}
