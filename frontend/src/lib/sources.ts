const labels: Record<string, string> = {
  weworkremotely: 'We Work Remotely',
  remoteok: 'RemoteOK',
  remotive: 'Remotive',
  linkedin_email: 'LinkedIn alert',
  extension: 'Browser extension',
  manual: 'Added manually',
}

export function sourceLabel(source: string): string {
  return labels[source] ?? source
}
