import { useState } from 'react'
import { Segmented } from '../../ui/controls'
import { CloseButton, Overlay } from '../../ui/overlay'
import { ArxivSearch } from './ArxivSearch'
import { UploadForm } from './UploadForm'

const TABS = [
  ['arxiv', 'arXiv'],
  ['upload', 'Upload PDF'],
] as const

export function AddPapersModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('arxiv')
  return (
    <Overlay kind="modal" label="Add papers" onClose={onClose}>
      <div className="panel-head">
        <h2>Add papers</h2>
        <CloseButton onClick={onClose} />
      </div>
      <div>
        <Segmented label="Add from" options={TABS} value={tab} onChange={setTab} />
      </div>
      <div hidden={tab !== 'arxiv'}>
        <ArxivSearch onImported={onImported} autoFocus />
      </div>
      <div hidden={tab !== 'upload'}>
        <UploadForm onImported={onImported} />
      </div>
      <p className="faint small">Processed on this machine. Only arXiv downloads use the network.</p>
    </Overlay>
  )
}
