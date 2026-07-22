import './Card.css'

export function Card({ children, className='', hover=true, ...props }){
  return (
    <div className={`card ${hover ? 'card-hoverable' : ''} ${className}`} {...props}>
      {children}
    </div>
  )
}
