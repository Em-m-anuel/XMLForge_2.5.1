import './Button.css'

const variants = {
  default: 'btn-default',
  primary: 'btn-primary',
  danger: 'btn-danger',
  ghost: 'btn-ghost',
}

export function Button({
  children,
  variant = 'default',
  size = 'md',
  fullWidth = false,
  leftIcon,
  rightIcon,
  className = '',
  ...props
}){
  const vClass = variants[variant] || ''
  const sClass = size === 'sm' ? 'btn-sm' : ''
  const wClass = fullWidth ? 'btn-full' : ''
  return (
    <button
      className={`btn ${vClass} ${sClass} ${wClass} ${className}`}
      {...props}
    >
      {leftIcon && <span className="btn-icon">{leftIcon}</span>}
      {children}
      {rightIcon && <span className="btn-icon">{rightIcon}</span>}
    </button>
  )
}
