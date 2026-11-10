type CardListSkeletonProps = {
  count?: number
}

export function CardListSkeleton({ count = 3 }: CardListSkeletonProps) {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      {Array.from({ length: count }, (_unused, index) => (
        <div key={index} className="h-24 rounded-2xl bg-accent" />
      ))}
    </div>
  )
}
