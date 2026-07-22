import './Loader.css'

export function Loader({ size=20 }){
  return <span className="loader" style={{width:size, height:size}} />
}
