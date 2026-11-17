const labels: Record<string, string> = {
  weworkremotely: 'We Work Remotely',
  remoteok: 'RemoteOK',
  remotive: 'Remotive',
}

export function sourceLabel(source: string): string {
  return labels[source] ?? source
}
