import { useState } from 'react'
import ProfileEditor from '../components/ProfileEditor'
import GroqViewPanel from '../components/GroqViewPanel'
import ResumeDraftCard from '../components/ResumeDraftCard'
import { profileSample, resumeDraftSample } from '../data/profileSample'

export default function MyProfile() {
  const [lastSaved] = useState(profileSample.content)
  const [text, setText] = useState(lastSaved)
  const [addMessage, setAddMessage] = useState<string | null>(null)

  function handleAddDraft() {
    const draftText = resumeDraftSample.draft_content
    const nextText = text.trim() === '' ? draftText : `${text}\n\n${draftText}`

    if (nextText.length > 2000) {
      setAddMessage(
        'The draft does not fit in the profile text (2000 characters maximum). Shorten the text first.',
      )
      return
    }

    setText(nextText)
    setAddMessage(null)
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">My Profile</h1>

      <div className="mt-6 grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <ProfileEditor
            value={text}
            onChange={setText}
            updatedAt={profileSample.updated_at}
            message={addMessage}
          />
        </div>
        <GroqViewPanel
          view={profileSample.groq_view}
          redactions={profileSample.redactions}
          warnings={profileSample.warnings}
        />
      </div>

      <div className="mt-6">
        <ResumeDraftCard
          draft={resumeDraftSample}
          onAddDraft={handleAddDraft}
          addMessage={addMessage}
        />
      </div>
    </div>
  )
}
