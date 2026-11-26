import { useState } from 'react'
import { Segmented } from '../../ui/controls'
import { SearchPanel } from '../search/SearchPanel'
import { QAPanel, type AskRequest } from './QAPanel'

const MODES = [
  ['answer', 'Answer'],
  ['passages', 'Find passages'],
] as const

type Mode = (typeof MODES)[number][0]

/** Ask: grounded answers, or plain passage search, behind one segmented toggle. Both keep their state. */
export function AskView({ request }: { request: AskRequest | null }) {
  const [mode, setMode] = useState<Mode>('answer')
  const [seen, setSeen] = useState(request?.id)
  if (request && request.id !== seen) {
    setSeen(request.id)
    setMode('answer')
  }
  const toggle = <Segmented label="Ask mode" options={MODES} value={mode} onChange={setMode} />
  return (
    <div className="view">
      <div hidden={mode !== 'answer'}>
        <QAPanel toolbar={toggle} request={request} />
      </div>
      <div hidden={mode !== 'passages'}>
        <SearchPanel toolbar={toggle} />
      </div>
    </div>
  )
}
