import { useState } from 'react'
import { FactReview } from '../components/resume/FactReview'
import { UploadPanel } from '../components/resume/UploadPanel'
import { VersionList } from '../components/resume/VersionList'

export function ResumePage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  return (
    <div className="resume-page">
      <h1>Master resume</h1>
      <UploadPanel onUploaded={setSelectedId} />
      <VersionList selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId && <FactReview key={selectedId} resumeId={selectedId} />}
    </div>
  )
}