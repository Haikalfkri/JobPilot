import { useState } from 'react'
import type { JobFilters as Filters } from '../../api/jobs'

type Props = { filters: Filters; onChange: (next: Filters) => void }

const SELECTS: { key: keyof Filters; label: string; options: [string, string][] }[] = [
  { key: 'ordering', label: 'Sort',
    options: [['-published_at', 'Newest first'], ['-match_score', 'Best match first']] },
  { key: 'min_match_score', label: 'Match',
    options: [['50', '50% or better'], ['70', '70% or better'], ['85', '85% or better']] },
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
      <label className="check">
        <input type="checkbox" checked={filters.hide_ineligible === 'true'}
          onChange={(event) => update('hide_ineligible', event.target.checked ? 'true' : '')} />
        Hide jobs not open to me
      </label>
      <button type="submit" className="btn">Search</button>
    </form>
  )
}