import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import {
  ARRANGEMENTS, COMPONENT_KEYS, COMPONENT_LABEL, getPreferences, LEVELS, savePreferences,
  type Arrangement, type ComponentKey, type Level, type Preferences, type TargetLocation,
} from '../api/matching'

type Draft = {
  titles: string
  keywords: string
  countries: string
  arrangements: Arrangement[]
  levels: Level[]
  locations: TargetLocation[]
  weights: Record<ComponentKey, number>
  minScore: number
  windowDays: number
}

const lines = (text: string) => text.split('\n').map((t) => t.trim()).filter(Boolean)
const commas = (text: string) => text.split(',').map((t) => t.trim()).filter(Boolean)

function toDraft(p: Preferences): Draft {
  return {
    titles: p.job_titles.join('\n'), keywords: p.keywords.join(', '), countries: p.candidate_countries.join(', '),
    arrangements: p.work_arrangements, levels: p.experience_levels, locations: p.target_locations,
    weights: p.component_weights, minScore: p.minimum_match_score, windowDays: p.publication_window_days,
  }
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

function PreferencesForm({ initial }: { initial: Preferences }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>(() => toDraft(initial))
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }))

  const save = useMutation({
    mutationFn: () => savePreferences({
      job_titles: lines(draft.titles), keywords: commas(draft.keywords),
      candidate_countries: commas(draft.countries), work_arrangements: draft.arrangements,
      experience_levels: draft.levels, target_locations: draft.locations, component_weights: draft.weights,
      minimum_match_score: draft.minScore, publication_window_days: draft.windowDays,
    }),
    onSuccess: (saved) => {
      setDraft(toDraft(saved))
      queryClient.invalidateQueries({ queryKey: ['preferences'] })
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['jobs'] }), 6000)
    },
  })

  const weightTotal = COMPONENT_KEYS.reduce((sum, key) => sum + (draft.weights[key] || 0), 0)
  const updateLocation = (index: number, patch: Partial<TargetLocation>) =>
    set('locations', draft.locations.map((loc, i) => (i === index ? { ...loc, ...patch } : loc)))

  return (
    <form className="settings" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
      <section className="panel">
        <h2>What you are looking for</h2>
        <label className="field"><span>Target job titles (one per line)</span>
          <textarea rows={8} value={draft.titles} onChange={(e) => set('titles', e.target.value)} /></label>
        <label className="field"><span>Discovery keywords (comma-separated)</span>
          <input type="text" value={draft.keywords} onChange={(e) => set('keywords', e.target.value)} /></label>
        <fieldset><legend>Levels you want</legend>
          {LEVELS.map((level) => (
            <label key={level} className="check">
              <input type="checkbox" checked={draft.levels.includes(level)}
                onChange={() => set('levels', toggle(draft.levels, level))} /> {level}
            </label>
          ))}
        </fieldset>
      </section>

      <section className="panel">
        <h2>Where you can work</h2>
        <label className="field">
          <span>Countries where you can legally work (2-letter codes, comma-separated)</span>
          <input type="text" value={draft.countries} onChange={(e) => set('countries', e.target.value)} />
          <small className="muted">Remote eligibility is checked against these. It is never guessed from your resume or nationality.</small>
        </label>
        <fieldset><legend>Work arrangements you accept</legend>
          {ARRANGEMENTS.map((a) => (
            <label key={a} className="check">
              <input type="checkbox" checked={draft.arrangements.includes(a)}
                onChange={() => set('arrangements', toggle(draft.arrangements, a))} /> {a}
            </label>
          ))}
        </fieldset>
        <h3>Preferred locations</h3>
        {draft.locations.map((loc, index) => (
          <div key={index} className="location-row">
            <input type="text" aria-label="Label" placeholder="Label" value={loc.label}
              onChange={(e) => updateLocation(index, { label: e.target.value })} />
            <input type="text" aria-label="Country code" placeholder="ID" maxLength={2} value={loc.country_code ?? ''}
              onChange={(e) => updateLocation(index, { country_code: e.target.value.toUpperCase() || null })} />
            <input type="text" aria-label="City" placeholder="City (optional)" value={loc.city ?? ''}
              onChange={(e) => updateLocation(index, { city: e.target.value || null })} />
            {ARRANGEMENTS.map((a) => (
              <label key={a} className="check">
                <input type="checkbox" checked={loc.arrangements.includes(a)}
                  onChange={() => updateLocation(index, { arrangements: toggle(loc.arrangements, a) })} /> {a}
              </label>
            ))}
            <button type="button" className="icon-btn" aria-label="Remove location"
              onClick={() => set('locations', draft.locations.filter((_, i) => i !== index))}><Trash2 size={16} /></button>
          </div>
        ))}
        <button type="button" className="btn" onClick={() => set('locations', [...draft.locations,
          { label: '', country_code: null, city: null, arrangements: [...ARRANGEMENTS] }])}>
          <Plus size={16} aria-hidden="true" /> Add location
        </button>
      </section>

      <section className="panel">
        <h2>How scores are weighted</h2>
        <p className="muted">Weights are relative. A criterion that cannot be assessed for a job is left out instead of guessed.</p>
        <div className="weights">
          {COMPONENT_KEYS.map((key) => (
            <label key={key} className="field"><span>{COMPONENT_LABEL[key]} ({weightTotal ? Math.round((100 * (draft.weights[key] || 0)) / weightTotal) : 0}%)</span>
              <input type="number" min={0} max={100} value={draft.weights[key]}
                onChange={(e) => set('weights', { ...draft.weights, [key]: Number(e.target.value) })} /></label>
          ))}
        </div>
        <div className="weights">
          <label className="field"><span>Minimum match score</span>
            <input type="number" min={0} max={100} value={draft.minScore}
              onChange={(e) => set('minScore', Number(e.target.value))} /></label>
          <label className="field"><span>Only jobs published within (days)</span>
            <input type="number" min={1} max={365} value={draft.windowDays}
              onChange={(e) => set('windowDays', Number(e.target.value))} /></label>
        </div>
      </section>

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>Save preferences</button>
        {save.isSuccess && <span className="muted">Saved. Scores are being recalculated.</span>}
      </div>
      {save.isError && <p className="notice notice-error" role="alert">{save.error.message}</p>}
    </form>
  )
}

export function SettingsPage() {
  const { data, isPending, isError, error } = useQuery({ queryKey: ['preferences'], queryFn: getPreferences })
  return (
    <div className="page">
      <h1>Search preferences</h1>
      {isPending && <p className="muted">Loading…</p>}
      {isError && <p className="notice notice-error" role="alert">{error.message}</p>}
      {data && <PreferencesForm key={data.updated_at} initial={data} />}
    </div>
  )
}