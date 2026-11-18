type SkeletonBlockProps = {
  className?: string
}

export default function SkeletonBlock({ className = '' }: SkeletonBlockProps) {
  return <div className={`animate-pulse rounded-md bg-neutral-200 ${className}`} />
}
