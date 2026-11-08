import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Pencil, Undo2, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import {
  createFact, FACT_CATEGORIES, listFacts, updateFact, type Fact, type FactCategory,
} from '../../api/resumes'

const CATEGORY_LABEL: Record<FactCategory, string> = {
  personal: 'Personal details', link: 'Links', summary: 'Summary', experience: 'Experience',
  education: 'Education', skill: 'Skills', project: 'Projects',
  certification: 'Certifications', language: 'Languages',
}

const addSchema = z.object({
  category: z.enum(FACT_CATEGORIES),
  content: z.string().trim().min(1, 'Enter the fact you want to add.').max(5000),
})
type AddForm = z.infer<typeof addSchema>

function FactRow({ fact, resumeId }: { fact: Fact; resumeId: string }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(fact.content)

  const mutation = useMutation({
    mutationFn: (data: Parameters<typeof updateFact>[1]) => updateFact(fact.id, data),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['facts', resumeId] })
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })

  return (
    <li className={`fact fact-${fact.verification_status}`}>
      {editing ? (
        <div className="fact-edit">
          <textarea value={draft} rows={3} aria-label="Edit fact" onChange={(e) => setDraft(e.target.value)} />
          <div className="fact-actions">
            <button type="button" className="btn btn-primary" disabled={!draft.trim() || mutation.isPending}
              onClick={() => mutation.mutate({ content: draft.trim() })}>Save and confirm</button>
            <button type="button" className="btn" onClick={() => { setEditing(false); setDraft(fact.content) }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="fact-body">
            <p className="fact-content">{fact.content}</p>
            <p className="muted fact-meta">
              {fact.verification_status === 'user_confirmed' && 'Confirmed'}
              {fact.verification_status === 'rejected' && 'Rejected'}
              {fact.verification_status === 'parser_suggested' && 'Suggested by parser'}
              {fact.source_location && ` · ${fact.source_location}`}
            </p>
          </div>
          <div className="fact-actions">
            {fact.verification_status !== 'user_confirmed' && (
              <button type="button" className="icon-btn" title="Confirm" aria-label="Confirm fact"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ verification_status: 'user_confirmed' })}>
                {fact.verification_status === 'rejected' ? <Undo2 size={16} /> : <Check size={16} />}
              </button>
            )}
            <button type="button" className="icon-btn" title="Edit" aria-label="Edit fact"
              onClick={() => setEditing(true)}><Pencil size={16} /></button>
            {fact.verification_status !== 'rejected' && (
              <button type="button" className="icon-btn" title="Reject" aria-label="Reject fact"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ verification_status: 'rejected' })}><X size={16} /></button>
            )}
          </div>
        </>
      )}
      {mutation.isError && <p className="notice notice-error" role="alert">{mutation.error.message}</p>}
    </li>
  )
}

function AddFactForm({ resumeId }: { resumeId: string }) {
  const queryClient = useQueryClient()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<AddForm>({
    resolver: zodResolver(addSchema),
    defaultValues: { category: 'skill', content: '' },
  })
  const add = useMutation({
    mutationFn: (data: AddForm) => createFact(resumeId, data),
    onSuccess: () => {
      reset({ category: 'skill', content: '' })
      queryClient.invalidateQueries({ queryKey: ['facts', resumeId] })
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })

  return (
    <form className="add-fact" onSubmit={handleSubmit((data) => add.mutate(data))}>
      <h3>Add a missing fact</h3>
      <select aria-label="Category" {...register('category')}>
        {FACT_CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
      </select>
      <input type="text" aria-label="Fact" placeholder="For example: AWS Cloud Practitioner" {...register('content')} />
      <button type="submit" className="btn" disabled={add.isPending}>Add fact</button>
      {errors.content && <p className="notice notice-error" role="alert">{errors.content.message}</p>}
      {add.isError && <p className="notice notice-error" role="alert">{add.error.message}</p>}
    </form>
  )
}

export function FactReview({ resumeId }: { resumeId: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['facts', resumeId],
    queryFn: () => listFacts(resumeId),
  })

  if (isPending) return <p className="muted">Loading facts…</p>
  if (isError) return <p className="notice notice-error" role="alert">{error.message}</p>

  return (
    <section>
      <h2>Review facts</h2>
      <p className="muted">
        Only facts you confirm can be used in tailored resumes. Editing a fact confirms it.
      </p>
      {data.length === 0 && (
        <p className="muted">No facts for this version yet. If parsing failed, use “Parse again” above.</p>
      )}
      {FACT_CATEGORIES.map((category) => {
        const facts = data.filter((f) => f.category === category)
        if (facts.length === 0) return null
        return (
          <div key={category} className="fact-group">
            <h3>{CATEGORY_LABEL[category]}</h3>
            <ul className="fact-list">
              {facts.map((fact) => <FactRow key={fact.id} fact={fact} resumeId={resumeId} />)}
            </ul>
          </div>
        )
      })}
      <AddFactForm resumeId={resumeId} />
    </section>
  )
}