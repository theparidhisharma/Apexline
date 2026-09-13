import IncidentCard from '../components/IncidentCard.jsx'

const BANDS = [
  ['auto_flag', 'Auto-flag — confirm with one click'],
  ['needs_review', 'Needs review — the human’s call'],
  ['auto_clear', 'Auto-cleared — logged, still queryable'],
]

export default function ReviewQueue({ incidents, live, newestId, onOpen }) {
  return (
    <div>
      <h1 className="screen-title">Review queue</h1>
      {!live && incidents.length > 0 && (
        <div className="banner warn">SAMPLE DATA — backend not reachable. Start the API
        (uvicorn server.main:app --port 8000) to see real incidents.</div>
      )}
      {live && incidents.length === 0 && (
        <div className="banner">No incidents yet. Ingest a video (Ingest tab) — incidents
        stream in here live as the pipeline finds them.</div>
      )}
      <p className="screen-sub">
        Geometry triages every candidate; only clean V1/V2 crossings can auto-flag.
        Anything occluded, context-tagged, or inside its error band waits for you.
      </p>
      <div className="bands">
        {BANDS.map(([band, label]) => {
          const list = incidents.filter(i => i.band === band)
          return (
            <div key={band} className={`band-col band-${band}`}>
              <h3>{label.split(' — ')[0]} <span className="n">{list.length}</span></h3>
              <div className="list">
                {list.length === 0 && <div className="empty">No incidents in this band — coverage active</div>}
                {list.map(i => <IncidentCard key={i.id} inc={i} fresh={i.id === newestId} onOpen={onOpen} />)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
