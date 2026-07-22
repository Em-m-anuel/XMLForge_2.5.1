import './Input.css'

export function Input({
  label,
  id,
  icon,
  error,
  className='',
  ...props
}){
  return (
    <div className={`field ${className}`}>
      {label && <label htmlFor={id} className="field-label">{label}</label>}
      <div className={`field-input ${error ? 'field-input-error' : ''}`}>
        {icon && <span className="field-icon">{icon}</span>}
        <input id={id} {...props} />
      </div>
      {error && <span className="field-error">{error}</span>}
    </div>
  )
}

export function FormInput({ label, id, className='', ...props }){
  return (
    <div className={`field-block ${className}`}>
      {label && <label htmlFor={id} className="form-label">{label}</label>}
      <input id={id} className="form-input" {...props} />
    </div>
  )
}
