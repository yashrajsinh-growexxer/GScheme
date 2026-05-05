"use client"

import { motion } from "framer-motion"
import { ExternalLink, FileText, CheckCircle2, Users, Calendar, DollarSign, ClipboardList, Globe, Info, Shield } from "lucide-react"
import type { SchemeCompareData } from "@/lib/api"
import { cn } from "@/lib/utils"

interface ComparisonGridProps {
  schemes: (SchemeCompareData | null)[]
}

interface RowConfig {
  label: string
  key: string
  icon: React.ReactNode
  render?: (value: unknown, scheme: SchemeCompareData) => React.ReactNode
}

const ROWS: RowConfig[] = [
  {
    label: "State / Region",
    key: "state",
    icon: <Globe className="h-4 w-4" />,
  },
  {
    label: "Category",
    key: "category",
    icon: <Info className="h-4 w-4" />,
  },
  {
    label: "Details",
    key: "details",
    icon: <FileText className="h-4 w-4" />,
    render: (value) => {
      const text = value as string
      if (!text || text === "N/A") return <NaCell />
      return <FormattedText text={text} />
    },
  },
  {
    label: "Eligibility",
    key: "eligibility",
    icon: <CheckCircle2 className="h-4 w-4" />,
    render: (value) => {
      const text = value as string
      if (!text || text === "N/A") return <NaCell />
      return <FormattedText text={text} />
    },
  },
  {
    label: "Benefits",
    key: "benefits",
    icon: <CheckCircle2 className="h-4 w-4" />,
    render: (value) => {
      const text = value as string
      if (!text || text === "N/A") return <NaCell />
      return <FormattedText text={text} />
    },
  },
  {
    label: "Income Cap",
    key: "income_cap",
    icon: <DollarSign className="h-4 w-4" />,
  },
  {
    label: "Age Limits",
    key: "age_limits",
    icon: <Calendar className="h-4 w-4" />,
  },
  {
    label: "Gender",
    key: "gender_tags",
    icon: <Users className="h-4 w-4" />,
    render: (value) => {
      const tags = value as string[]
      if (!tags || tags.length === 0) return <NaCell />
      return (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-700 capitalize"
            >
              {tag}
            </span>
          ))}
        </div>
      )
    },
  },
  {
    label: "Caste Category",
    key: "caste_tags",
    icon: <Shield className="h-4 w-4" />,
    render: (value) => {
      const tags = value as string[]
      if (!tags || tags.length === 0) return <NaCell />
      return (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-700 uppercase"
            >
              {tag}
            </span>
          ))}
        </div>
      )
    },
  },
  {
    label: "Documents Required",
    key: "documents_required",
    icon: <ClipboardList className="h-4 w-4" />,
    render: (value) => {
      const docs = value as string[]
      if (!docs || docs.length === 0) return <NaCell />
      return (
        <ul className="list-disc space-y-2 pl-5 text-sm">
          {docs.map((doc, i) => (
            <li key={i} className="leading-relaxed whitespace-pre-wrap break-words">
              {doc}
            </li>
          ))}
        </ul>
      )
    },
  },
  {
    label: "Application Mode",
    key: "application_mode",
    icon: <Globe className="h-4 w-4" />,
    render: (value) => {
      const mode = value as string
      if (!mode || mode === "N/A") return <NaCell />
      const colorMap: Record<string, string> = {
        "Online": "bg-primary/10 text-primary",
        "Offline": "bg-accent text-accent-foreground",
        "Online & Offline": "bg-blue-500/10 text-blue-700",
      }
      return (
        <span className={cn("inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold", colorMap[mode] || "bg-muted text-muted-foreground")}>
          {mode}
        </span>
      )
    },
  },
  {
    label: "Application Process",
    key: "application_process",
    icon: <FileText className="h-4 w-4" />,
    render: (value) => {
      const text = value as string
      if (!text || text === "N/A") return <NaCell />
      return <FormattedText text={text} />
    },
  },
  {
    label: "Official URL",
    key: "url",
    icon: <ExternalLink className="h-4 w-4" />,
    render: (value) => {
      const url = value as string
      if (!url || url === "N/A") return <NaCell />
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline break-all"
        >
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          View Scheme
        </a>
      )
    },
  },
]

function NaCell() {
  return (
    <span className="text-sm text-muted-foreground/60 italic">N/A</span>
  )
}

function FormattedText({ text }: { text: string }) {
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  if (lines.length === 0) {
    return <NaCell />
  }

  const bulletLike = lines.every((line) =>
    /^([•*-]|[0-9]+[.)]|[A-Za-z][.)]|note\s*\d*:|step\s*\d*:)/i.test(line),
  )

  if (bulletLike) {
    return (
      <ul className="list-disc space-y-2 pl-5 text-sm">
        {lines.map((line, index) => (
          <li key={index} className="leading-relaxed whitespace-pre-wrap break-words">
            {line.replace(/^([•*-]|[0-9]+[.)]|[A-Za-z][.)])\s*/i, "")}
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="space-y-2 text-sm">
      {lines.map((line, index) => (
        <p key={index} className="leading-relaxed whitespace-pre-wrap break-words">
          {line}
        </p>
      ))}
    </div>
  )
}

function CellValue({ row, scheme }: { row: RowConfig; scheme: SchemeCompareData }) {
  const value = scheme[row.key as keyof SchemeCompareData] as unknown

  if (row.render) {
    return <>{row.render(value, scheme)}</>
  }

  const strValue = typeof value === "string" ? value : JSON.stringify(value)
  if (!strValue || strValue === "N/A" || strValue === '""') {
    return <NaCell />
  }

  return <p className="text-sm whitespace-pre-wrap break-words">{strValue}</p>
}

export function ComparisonGrid({ schemes }: ComparisonGridProps) {
  const activeSchemes = schemes.filter(Boolean) as SchemeCompareData[]

  if (activeSchemes.length === 0) {
    return null
  }

  const colCount = activeSchemes.length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="mt-8 overflow-x-auto"
    >
      <div className="min-w-[760px] rounded-xl border bg-card shadow-sm overflow-hidden">
        {/* Table header row */}
        <div
          className="grid border-b bg-muted/30"
          style={{ gridTemplateColumns: `220px repeat(${colCount}, minmax(240px, 1fr))` }}
        >
          <div className="sticky left-0 z-10 border-r bg-muted/30 p-4 text-sm font-semibold text-muted-foreground">
            Attribute
          </div>
          {activeSchemes.map((scheme) => (
            <div key={scheme.scheme_id} className="border-r p-4 last:border-r-0">
              <h3 className="truncate text-sm font-semibold text-foreground" title={scheme.name}>
                {scheme.name}
              </h3>
            </div>
          ))}
        </div>

        {/* Data rows */}
        {ROWS.map((row, rowIdx) => (
          <div
            key={row.key}
            className={cn(
              "grid border-b last:border-b-0",
              rowIdx % 2 === 0 ? "bg-background" : "bg-muted/10"
            )}
            style={{ gridTemplateColumns: `220px repeat(${colCount}, minmax(240px, 1fr))` }}
          >
            {/* Label cell */}
            <div
              className={cn(
                "sticky left-0 z-[1] flex items-start gap-2 border-r p-4 text-muted-foreground",
                rowIdx % 2 === 0 ? "bg-background" : "bg-muted/10"
              )}
            >
              <span className="mt-0.5 shrink-0">{row.icon}</span>
              <span className="text-sm font-medium">{row.label}</span>
            </div>

            {/* Value cells */}
            {activeSchemes.map((scheme) => (
              <div
                key={`${scheme.scheme_id}-${row.key}`}
                className="min-w-0 border-r p-4 last:border-r-0"
              >
                <CellValue row={row} scheme={scheme} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </motion.div>
  )
}
