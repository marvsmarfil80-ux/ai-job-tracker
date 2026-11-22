import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import ProfileEditor from '../components/ProfileEditor'
import GroqViewPanel from '../components/GroqViewPanel'
import ResumeDraftCard from '../components/ResumeDraftCard'
import SkeletonBlock from '../components/SkeletonBlock'
import ErrorState from '../components/ErrorState'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { ProfileOut, ResumeDraftOut } from '../types'

export default function MyProfile() {
  const [profile, setProfile] = useState<ProfileOut | null>(null)
  const [text, setText] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [justSaved, setJustSaved] = useState(false)
  const [draft, setDraft] = useState<ResumeDraftOut | null>(null)
  const [draftBusy, setDraftBusy] = useState(false)
  const [draftError, setDraftError] = useState<{ status: number; detail: string } | null>(
    null,
  )
  const [addMessage, setAddMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

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
  }, [reloadKey])

  function handleRetry() {
    setLoadError(null)
    setReloadKey((key) => key + 1)
  }

  async function handleSave() {
    if (saving) return
    setSaving(true)
    setSaveError(null)
    setJustSaved(false)

    try {
      await api.put<unknown>('/profile', { content: text })
    } catch (error) {
      if (error instanceof ApiError) {
        setSaveError(
          error.validation !== null
            ? error.validation.map((item) => item.msg).join(' ')
            : error.detail,
        )
      } else {
        setSaveError('Could not save the profile.')
      }
      setSaving(false)
      return
    }

    try {
      const updated = await api.get<ProfileOut>('/profile')
      setProfile(updated)
      setText(updated.content)
      setJustSaved(true)
    } catch {
      setSaveError('The profile was saved, but it could not be reloaded. Refresh the page.')
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
        setDraftError({ status: error.status, detail: error.detail })
      } else {
        setDraftError({ status: 0, detail: 'Could not create the draft.' })
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
    setJustSaved(false)
    setAddMessage(null)
  }

  const header = (
    <PageHeader
      eyebrow="Profile"
      title="My Profile"
      description="Edit your profile text and draft skills from a resume PDF."
    />
  )

  if (loadError !== null) {
    return (
      <div>
        {header}
        <div className="rounded-card border border-line bg-surface shadow-card">
          <ErrorState message={loadError} onRetry={handleRetry} />
        </div>
      </div>
    )
  }

  if (profile === null) {
    return (
      <div aria-busy="true">
        {header}

        <div className="grid grid-cols-1 gap-6 min-[1050px]:grid-cols-3">
          <div className="rounded-card border border-line bg-surface p-5 shadow-card min-[1050px]:col-span-2">
            <SkeletonBlock className="h-5 w-40" />
            <SkeletonBlock className="mt-4 h-64 w-full" />
            <SkeletonBlock className="mt-3 h-4 w-24" />
            <SkeletonBlock className="mt-4 h-8 w-24" />
          </div>
          <div className="rounded-card border border-line bg-surface p-5 shadow-card">
            <SkeletonBlock className="h-5 w-32" />
            <SkeletonBlock className="mt-4 h-4 w-full" />
            <SkeletonBlock className="mt-2 h-4 w-5/6" />
            <SkeletonBlock className="mt-2 h-4 w-4/6" />
            <SkeletonBlock className="mt-4 h-24 w-full" />
          </div>
        </div>

        <div className="mt-6 rounded-card border border-line bg-surface p-5 shadow-card">
          <SkeletonBlock className="h-5 w-36" />
          <SkeletonBlock className="mt-3 h-4 w-3/4" />
          <SkeletonBlock className="mt-4 h-9 w-64" />
        </div>
      </div>
    )
  }

  return (
    <div>
      {header}

      <div className="grid grid-cols-1 gap-6 min-[1050px]:grid-cols-3">
        <div className="min-[1050px]:col-span-2">
          <ProfileEditor
            value={text}
            onChange={(value) => {
              setText(value)
              setJustSaved(false)
            }}
            updatedAt={profile.updated_at}
            message={saveError}
            onSave={handleSave}
            saving={saving}
            dirty={text !== profile.content}
            showSaved={justSaved}
            showEmptyNotice={profile.content.trim() === ''}
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
          onClearError={() => setDraftError(null)}
          onAddDraft={handleAddDraft}
          addMessage={addMessage}
        />
      </div>
    </div>
  )
}
