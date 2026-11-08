import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { useRef } from 'react'
import { uploadResume } from '../../api/resumes'

type Props = { onUploaded: (resumeId: string) => void }

export function UploadPanel({ onUploaded }: Props) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = useMutation({
    mutationFn: uploadResume,
    onSuccess: (resume) => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      onUploaded(resume.id)
    },
  })

  return (
    <section className="panel">
      <h2>Upload a resume</h2>
      <p className="muted">PDF or DOCX, up to 5 MB. Each upload becomes a new version.</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        className="sr-only"
        id="resume-file"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) upload.mutate(file)
          event.target.value = '' // allow re-selecting the same file
        }}
      />
      <button type="button" className="btn btn-primary" disabled={upload.isPending}
        onClick={() => inputRef.current?.click()}>
        <Upload size={16} aria-hidden="true" />
        {upload.isPending ? 'Uploading…' : 'Choose file'}
      </button>
      {upload.isError && <p className="notice notice-error" role="alert">{upload.error.message}</p>}
      {upload.data?.duplicate_of_version != null && (
        <p className="notice notice-warn">
          This file is identical to version {upload.data.duplicate_of_version}. It was saved as a new version anyway.
        </p>
      )}
    </section>
  )
}