import PageHeader from './PageHeader'

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <PageHeader title={title} />
      <p className="text-sm text-ink-muted">Coming soon.</p>
    </div>
  )
}
