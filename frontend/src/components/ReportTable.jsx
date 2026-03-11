export default function ReportTable({ result }) {
  const { metadata, rows } = result

  if (!rows || rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-5xl mb-4">🔍</div>
        <h3 className="font-display font-bold text-xl text-text-primary mb-2">
          Aucun résultat
        </h3>
        <p className="text-text-secondary text-sm max-w-sm">
          Aucune donnée ne correspond aux critères de ce rapport dans Mercator.
        </p>
      </div>
    )
  }

  const columns = metadata.columns

  return (
    <div className="flex flex-col gap-4">
      {/* Stats bar */}
      <div className="flex items-center gap-6 text-sm">
        <Stat label="Total" value={metadata.total_items} color="#00d4ff" />
        <Stat label="Affichés" value={metadata.returned_items} color="#10b981" />
        <Stat label="Filtres" value={metadata.filters_applied} color="#7c3aed" />
        <div className="ml-auto text-xs font-mono text-text-muted">
          Généré le {new Date(metadata.generated_at).toLocaleString('fr-FR')}
        </div>
      </div>

      {/* Table container */}
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border bg-bg-secondary">
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-4 py-3 text-left text-xs font-mono font-semibold
                               text-text-secondary uppercase tracking-widest whitespace-nowrap"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className="border-b border-border last:border-0 transition-colors
                             hover:bg-bg-hover group"
                  style={{
                    animationDelay: `${Math.min(i * 30, 300)}ms`,
                  }}
                >
                  {columns.map((col) => (
                    <td key={col} className="px-4 py-3 text-text-primary">
                      <CellValue value={row.data[col]} column={col} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="text-lg font-display font-bold"
        style={{ color }}
      >
        {value}
      </span>
      <span className="text-text-muted text-xs">{label}</span>
    </div>
  )
}

function CellValue({ value, column }) {
  if (value === null || value === undefined) {
    return <span className="text-text-muted font-mono text-xs">—</span>
  }

  // Booléens
  if (typeof value === 'boolean') {
    return value
      ? <Badge color="#10b981" bg="#10b98120">Oui</Badge>
      : <Badge color="#ef444460" bg="#ef444410">Non</Badge>
  }

  // Niveaux de sécurité CIAT (1-4)
  const securityCols = ['C', 'I', 'A', 'T', 'Confidentialité', 'Intégrité', 'Disponibilité', 'Traçabilité']
  if (securityCols.includes(column) && typeof value === 'number') {
    const colors = { 1: '#10b981', 2: '#f59e0b', 3: '#ef4444', 4: '#7c3aed' }
    const labels = { 1: 'Faible', 2: 'Moyen', 3: 'Élevé', 4: 'Critique' }
    return (
      <div className="flex items-center gap-2">
        <div className="flex gap-0.5">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="w-2 h-5 rounded-sm transition-opacity"
              style={{
                backgroundColor: n <= value ? colors[value] : '#1e1e2a',
                opacity: n <= value ? 1 : 0.3,
              }}
            />
          ))}
        </div>
        <span className="text-xs font-mono" style={{ color: colors[value] }}>
          {labels[value]}
        </span>
      </div>
    )
  }

  // Externe (0/1 string)
  if (column === 'Externe') {
    return value === '1' || value === true
      ? <Badge color="#f59e0b" bg="#f59e0b15">Externe</Badge>
      : <Badge color="#10b981" bg="#10b98115">Interne</Badge>
  }

  // RTO / RPO (heures)
  const timeCols = ['RTO (h)', 'RPO (h)', 'MTD (h)', 'MTDL (h)']
  if (timeCols.includes(column) && typeof value === 'number') {
    const urgent = value <= 4
    return (
      <span
        className="font-mono font-semibold text-sm"
        style={{ color: urgent ? '#ef4444' : '#00d4ff' }}
      >
        {value}h
      </span>
    )
  }

  // Bloc applicatif
  if (column === 'Bloc Applicatif') {
    if (value === 'Non classé') {
      return <span className="text-text-muted italic text-xs">{value}</span>
    }
    return (
      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-accent-violet/15 text-accent-violet border border-accent-violet/30">
        {value}
      </span>
    )
  }

  // Lien
  if (typeof value === 'string' && value.startsWith('http')) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent-cyan hover:underline text-xs font-mono truncate max-w-[200px] block"
      >
        {value}
      </a>
    )
  }

  return <span className="text-text-primary">{String(value)}</span>
}

function Badge({ color, bg, children }) {
  return (
    <span
      className="text-xs font-medium px-2 py-0.5 rounded-full border"
      style={{ color, backgroundColor: bg, borderColor: `${color}44` }}
    >
      {children}
    </span>
  )
}