import { ArrowRight, CloudRain, Droplets, Leaf } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const DATA_CHIPS = [
  { icon: Droplets, title: 'SMAP', sub: "Humidité du sol vue du ciel", state: 'Intégration prévue' },
  { icon: CloudRain, title: 'IMERG', sub: 'Pluies, au kilomètre près', state: 'Intégration prévue' },
  { icon: Leaf, title: 'EcoCrop', sub: 'Ce que votre terre peut porter', state: 'Catalogue disponible' },
]

const STEPS = [
  ['01', 'Dessinez votre terrain', 'Tracez la parcelle sur la carte satellite, ou importez votre fichier.', '/terrains/nouveau', 'labour'],
  ['02', 'Choisissez vos cultures', 'Blé, orge, pois chiche, fourrage : gardez ce qui est possible chez vous.', '/analyse/cultures', 'vert'],
  ['03', 'Dites ce qui compte', "L'eau, le revenu, la fertilité : c'est vous qui réglez les curseurs.", '/analyse/priorites', 'ble'],
  ['04', 'Comparez les rotations', 'Une recommandation claire, avec les raisons et les risques.', '/analyses', 'oliviers'],
]

const PLOTS = [
  { pts: '590,60 1120,170 1030,625 585,545', tx: 650, ty: 300, title: 'Parcelle A · blé dur', note: 'Récolte proche', cls: 'wheat' },
  { pts: '1050,200 1545,325 1480,700 1040,640', tx: 1075, ty: 470, title: 'Parcelle B · oliviers', note: 'Eau à surveiller', cls: 'warn' },
]

function AerialHero() {
  return (
    <div className="h-photo" aria-hidden="true">
      <img src="/images/champs-aerien.jpg" alt="" />
      <svg viewBox="0 0 1600 1008" preserveAspectRatio="xMidYMid slice">
        {PLOTS.map((p) => (
          <g key={p.title} className={`plot plot-${p.cls}`}>
            <polygon points={p.pts} />
            <rect x={p.tx - 14} y={p.ty - 36} width="330" height="74" rx="14" />
            <text x={p.tx + 6} y={p.ty - 6} className="plot-t">{p.title}</text>
            <text x={p.tx + 6} y={p.ty + 24} className="plot-n">{p.note}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

export default function Home() {
  const navigate = useNavigate()
  return (
    <div className="home">
      <section className="h-hero">
        <div className="h-copy">
          <h1>Que planter <em>après</em> le blé&nbsp;?</h1>
          <p className="lead">
            AgriSense regarde votre parcelle comme un satellite, puis vous parle comme un voisin
            qui s'y connaît : l'eau, le sol, le marché, et trois rotations expliquées.
          </p>
          <div className="h-cta">
            <button className="btn btn-terra btn-lg" onClick={() => navigate('/terrains/nouveau')}>
              Commencer <ArrowRight size={18} />
            </button>
            <button className="btn btn-quiet" onClick={() => navigate('/analyses')}>Voir un exemple</button>
          </div>
        </div>
        <AerialHero />
      </section>

      <section className="h-data">
        {DATA_CHIPS.map(({ icon: Icon, title, sub, state }) => (
          <div className="h-chip" key={title}>
            <span className="chip-icon"><Icon size={20} /></span>
            <span><strong>{title}</strong><small>{sub}</small><em>{state}</em></span>
          </div>
        ))}
      </section>

      <h2 className="section-h h-title">Quatre gestes, une décision</h2>
      <section className="h-steps">
        {STEPS.map(([n, title, text, to, img]) => (
          <button key={n} className="h-step" onClick={() => navigate(to)} style={{ '--img': `url(/images/card-${img}.jpg)` }}>
            <span className="h-step-num">{n}</span>
            <span className="h-step-body"><strong>{title}</strong><small>{text}</small></span>
          </button>
        ))}
      </section>
    </div>
  )
}