export default function ConfidenceBar({ value }) {
  const color = value > 0.75 ? 'var(--flag)' : value < 0.35 ? 'var(--clear)' : 'var(--review)'
  return (
    <div className="confbar" title={`confidence ${value}`}>
      <i style={{ width: `${Math.round(value * 100)}%`, background: color }} />
    </div>
  )
}
