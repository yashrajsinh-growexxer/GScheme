import { cn } from "@/lib/utils"

interface QSkimLogoProps {
  compact?: boolean
  className?: string
}

export function QSkimLogo({ compact = false, className }: QSkimLogoProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
        >
          <circle cx="11" cy="11" r="6" />
          <path d="M20 20l-4.5-4.5" />
          <path d="M11 8v3" />
          <path d="M9.5 9.5h3" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-none flex flex-col justify-center">
          <span className="text-xl font-bold tracking-tight text-foreground">QSkim</span>
        </div>
      )}
    </div>
  )
}
