import { useEffect, useState } from 'react'
import ProfileEditor from '../components/ProfileEditor'
import GroqViewPanel from '../components/GroqViewPanel'
import ResumeDraftCard from '../components/ResumeDraftCard'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { ProfileOut, ResumeDraftOut } from '../types'

export default function MyProfile() {
  const [profile, setProfile] = useState<ProfileOut | null>(null)
  const [text, setText] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<ResumeDraftOut | null>(null)
  const [draftBusy, setDraftBusy] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
  const [addMessage, setAddMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await api.get<ProfileOut>('/profile')
        if (cancelled) return
        setProfile(data)
        setText(data.content)
      } catch (error) {
        if (cancelled) return
        setLoadError(
          error instanceof ApiError && typeof error.detail === 'string'
            ? error.detail
            : 'Could not load the profile.',
        )
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [])

  async function handleSave() {
    if (saving) return
    setSaving(true)
    setSaveError(null)

    try {
      await api.put<unknown>('/profile', { content: text })
      const updated = await api.get<ProfileOut>('/profile')
      setProfile(updated)
      setText(updated.content)
    } catch (error) {
      if (error instanceof ApiError) {
        setSaveError(
          error.validation !== null
            ? error.validation.map((item) => item.msg).join(' ')
            : error.detail,
        )
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleCreateDraft(file: File) {
    if (draftBusy) return
    setDraftBusy(true)
    setDraftError(null)
    setDraft(null)
    setAddMessage(null)

    try {
      const result = await api.postRaw<ResumeDraftOut>(
        '/profile/resume/draft',
        file,
        'application/pdf',
      )
      setDraft(result)
    } catch (error) {
      if (error instanceof ApiError) {
        setDraftError(error.detail)
      }
    } finally {
      setDraftBusy(false)
    }
  }

  function handleAddDraft() {
    if (draft === null) return
    const draftText = draft.draft_content
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

  if (profile === null) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">My Profile</h1>
        {loadError && <p className="mt-2 text-sm text-red-600">{loadError}</p>}
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">My Profile</h1>

      <div className="mt-6 grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <ProfileEditor
            value={text}
            onChange={setText}
            updatedAt={profile.updated_at}
            message={saveError}
            onSave={handleSave}
            saving={saving}
          />
        </div>
        <GroqViewPanel
          view={profile.groq_view}
          redactions={profile.redactions}
          warnings={profile.warnings}
        />
      </div>

      <div className="mt-6">
        <ResumeDraftCard
          draft={draft}
          busy={draftBusy}
          error={draftError}
          onCreate={handleCreateDraft}
          onAddDraft={handleAddDraft}
          addMessage={addMessage}
        />
      </div>
    </div>
  )
}
