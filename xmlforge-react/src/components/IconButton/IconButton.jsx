import './IconButton.css'

export function IconButton({ children, variant='', className='', ...props }){
  return (
    <button className={`icon-btn ${variant} ${className}`} {...props}>
      {children}
    </button>
  )
}
