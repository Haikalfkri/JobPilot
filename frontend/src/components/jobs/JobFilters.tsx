import { useState } from 'react'
import type { JobFilters as Filters } from '../../api/jobs'

type Props = { filters: Filters; onChange: (next: Filters) => void }

const SELECTS: { key: keyof Filters; label: string; options: [string, string][] }[] = [
  { key: 'work_arrangement', label: 'Work arrangement',
    options: [['remote', 'Remote'], ['hybrid', 'Hybrid'], ['onsite', 'On-site'], ['unknown', 'Not stated']] },
  { key: 'remote_eligibility', label: 'Who can apply',
    options: [['worldwide', 'Worldwide'], ['apac', 'APAC'], ['country_specific', 'Specific countries'],
      ['region_specific', 'Specific regions'], ['unknown', 'Not stated']] },
  { key: 'experience_level', label: 'Level',
    options: [['graduate', 'Graduate'], ['junior', 'Junior'], ['associate', 'Associate'], ['mid', 'Mid-level'],
      ['senior', 'Senior']] },
  { key: 'published_within_days', label: 'Published',
    options: [['1', 'Last 24 hours'], ['7', 'Last 7 days'], ['30', 'Last 30 days']] },
]

export function JobFilters({ filters, onChange }: Props) {
  const [text, setText] = useState(filters.q ?? '')
  const update = (key: keyof Filters, value: string) => onChange({ ...filters, [key]: value || undefined, page: undefined })

  return (
    <form className="filters" onSubmit={(event) => { event.preventDefault(); update('q', text.trim()) }}>
      <input type="search" aria-label="Search title or company" placeholder="Search title or company"
        value={text} onChange={(event) => setText(event.target.value)} />
      {SELECTS.map(({ key, label, options }) => (
        <select key={key} aria-label={label} value={filters[key] ?? ''} onChange={(event) => update(key, event.target.value)}>
          <option value="">{label}: any</option>
          {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
      ))}
      <button type="submit" className="btn">Search</button>
    </form>
  )
}