import './Skeleton.css'

export function Skeleton({ width='100%', height=16, radius=6, className='' }){
  return <div className={`skeleton ${className}`} style={{width, height, borderRadius: radius}} />
}

export function SkeletonCard(){
  return (
    <div className="skeleton-card">
      <Skeleton width={40} height={40} radius={10} />
      <div style={{flex:1, display:'flex', flexDirection:'column', gap:8}}>
        <Skeleton width="60%" height={14} />
        <Skeleton width="80%" height={12} />
      </div>
    </div>
  )
}

export function SkeletonTable({ rows=5 }){
  return (
    <div className="skeleton-table">
      {Array.from({length: rows}).map((_,i)=>(
        <div key={i} className="skeleton-row">
          <Skeleton width="20%" height={12} />
          <Skeleton width="15%" height={12} />
          <Skeleton width="10%" height={12} />
          <Skeleton width="10%" height={12} />
          <Skeleton width="20%" height={12} />
        </div>
      ))}
    </div>
  )
}
