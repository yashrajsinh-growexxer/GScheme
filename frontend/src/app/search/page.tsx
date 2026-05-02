"use client"

import { useState, useEffect, Suspense, useCallback } from "react"
import { useSearchParams } from "next/navigation"
import {
  Search as SearchIcon,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Minus,
  Plus,
} from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { SchemeCard } from "@/components/ui/scheme-card"
import { Modal } from "@/components/ui/modal"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { searchSchemes, type Scheme } from "@/lib/api"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import {
  AGE_RANGE_OPTIONS,
  CASTE_OPTIONS,
  countActiveSearchFilters,
  createEmptySearchFilters,
  GENDER_OPTIONS,
  SCHEME_CATEGORY_OPTIONS,
  SEARCH_STATE_OPTIONS,
  toggleFilterValue,
  type Option,
  type SearchFilters,
} from "@/lib/scheme-filters"

const SCHEMES_PER_PAGE = 10

const DEFAULT_OPEN_SECTIONS = {
  states: true,
  categories: true,
  age: true,
  gender: false,
  caste: false,
}

function SearchContent() {
  const searchParams = useSearchParams()
  const initialQuery = searchParams.get("q") || ""

  const [query, setQuery] = useState(initialQuery)
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery)
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [searchError, setSearchError] = useState("")
  const [resultsPage, setResultsPage] = useState(1)
  const [selectedScheme, setSelectedScheme] = useState<Scheme | null>(null)
  const [draftFilters, setDraftFilters] = useState<SearchFilters>(createEmptySearchFilters)
  const [appliedFilters, setAppliedFilters] = useState<SearchFilters>(createEmptySearchFilters)
  const [openSections, setOpenSections] = useState(DEFAULT_OPEN_SECTIONS)

  const performSearch = useCallback(async (searchQuery: string, filters: SearchFilters) => {
    if (!searchQuery.trim()) return
    setIsLoading(true)
    setHasSearched(true)
    setSearchError("")
    setSubmittedQuery(searchQuery)
    try {
      const results = await searchSchemes(searchQuery, filters)
      setSchemes(results)
      setAppliedFilters(filters)
      setResultsPage(1)
    } catch (error) {
      console.error(error)
      setSchemes([])
      setSearchError(error instanceof Error ? error.message : "Search failed")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (initialQuery) {
      const timer = window.setTimeout(() => {
        void performSearch(initialQuery, createEmptySearchFilters())
      }, 0)
      return () => window.clearTimeout(timer)
    }
  }, [initialQuery, performSearch])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    void performSearch(query, draftFilters)
  }

  const handleApplyFilters = () => {
    void performSearch(query, draftFilters)
  }

  const handleResetFilters = () => {
    const cleared = createEmptySearchFilters()
    setDraftFilters(cleared)
    setAppliedFilters(cleared)
    if (hasSearched && query.trim()) {
      void performSearch(query, cleared)
    }
  }

  const toggleSection = (section: keyof typeof DEFAULT_OPEN_SECTIONS) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  const totalPages = Math.max(1, Math.ceil(schemes.length / SCHEMES_PER_PAGE))
  const safeResultsPage = Math.min(resultsPage, totalPages)
  const pageStart = (safeResultsPage - 1) * SCHEMES_PER_PAGE
  const pageEnd = Math.min(pageStart + SCHEMES_PER_PAGE, schemes.length)
  const visibleSchemes = schemes.slice(pageStart, pageEnd)
  const activeFilterCount = countActiveSearchFilters(draftFilters)
  const appliedFilterCount = countActiveSearchFilters(appliedFilters)

  return (
    <div className="container mx-auto max-w-7xl flex-1 px-4 py-8">
      <div className="mb-8 rounded-[28px] border border-border/70 bg-gradient-to-br from-card via-card to-emerald-50/40 p-6 shadow-sm">
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-primary/80">
              Schemes By Name
            </p>
            <h1 className="mt-2 text-3xl font-bold text-foreground">Search schemes and refine the list</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Search by scheme title, then narrow the results with State/UT, category, age, gender,
              and caste.
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-white/80 px-4 py-3 text-sm text-muted-foreground shadow-sm">
            {activeFilterCount > 0 ? `${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"} selected` : "No filters selected"}
          </div>
        </div>

        <form onSubmit={handleSearch} className="relative flex items-center">
          <div className="absolute left-4 text-muted-foreground">
            <VoiceRecorder mode="translit" onTranscript={(text) => setQuery((prev) => prev + text)} />
          </div>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by scheme name or keywords..."
            className="h-14 rounded-full border-muted bg-background/90 pl-12 pr-14 text-lg shadow-sm focus-visible:ring-primary/50"
          />
          <Button
            type="submit"
            size="icon"
            className="absolute right-2 h-10 w-10 rounded-full bg-primary hover:bg-primary/90"
          >
            <SearchIcon className="h-5 w-5" />
          </Button>
        </form>
      </div>

      <div className="grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-[28px] border border-border/70 bg-card/95 p-5 shadow-sm backdrop-blur">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">Filter By</h2>
                <p className="text-sm text-muted-foreground">Refine the search once you have a scheme query.</p>
              </div>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-sm font-semibold text-emerald-600 transition hover:text-emerald-700"
              >
                Reset Filters
              </button>
            </div>

            <div className="space-y-2">
              <FilterSection
                title="State/UT"
                isOpen={openSections.states}
                onToggle={() => toggleSection("states")}
              >
                <CheckboxList
                  options={SEARCH_STATE_OPTIONS}
                  selected={draftFilters.states}
                  onToggle={(value) =>
                    setDraftFilters((prev) => ({
                      ...prev,
                      states: toggleFilterValue(prev.states, value),
                    }))
                  }
                  scrollable
                />
              </FilterSection>

              <FilterSection
                title="Scheme Category"
                isOpen={openSections.categories}
                onToggle={() => toggleSection("categories")}
              >
                <CheckboxList
                  options={SCHEME_CATEGORY_OPTIONS}
                  selected={draftFilters.categories}
                  onToggle={(value) =>
                    setDraftFilters((prev) => ({
                      ...prev,
                      categories: toggleFilterValue(prev.categories, value),
                    }))
                  }
                  scrollable
                />
              </FilterSection>

              <FilterSection title="Age" isOpen={openSections.age} onToggle={() => toggleSection("age")}>
                <SelectField
                  value={draftFilters.ageRange}
                  placeholder="Select age range"
                  options={AGE_RANGE_OPTIONS}
                  onChange={(value) => setDraftFilters((prev) => ({ ...prev, ageRange: value }))}
                />
              </FilterSection>

              <FilterSection title="Gender" isOpen={openSections.gender} onToggle={() => toggleSection("gender")}>
                <CheckboxList
                  options={GENDER_OPTIONS}
                  selected={draftFilters.genders}
                  onToggle={(value) =>
                    setDraftFilters((prev) => ({
                      ...prev,
                      genders: toggleFilterValue(prev.genders, value),
                    }))
                  }
                  columns={2}
                />
              </FilterSection>

              <FilterSection title="Caste" isOpen={openSections.caste} onToggle={() => toggleSection("caste")}>
                <CheckboxList
                  options={CASTE_OPTIONS}
                  selected={draftFilters.castes}
                  onToggle={(value) =>
                    setDraftFilters((prev) => ({
                      ...prev,
                      castes: toggleFilterValue(prev.castes, value),
                    }))
                  }
                  columns={2}
                />
              </FilterSection>

            </div>

            <div className="mt-6 flex flex-col gap-3 border-t border-border/70 pt-5">
              <Button onClick={handleApplyFilters} disabled={!query.trim() || isLoading} className="rounded-full">
                Apply Filters
              </Button>
              <p className="text-xs text-muted-foreground">
                State/UT, scheme category, gender, and caste allow multi-select.
              </p>
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center rounded-[28px] border border-border/70 bg-card py-24 text-muted-foreground shadow-sm">
              <Loader2 className="mb-4 h-8 w-8 animate-spin text-primary" />
              <p>Searching knowledge base...</p>
            </div>
          ) : hasSearched ? (
            <div className="space-y-6">
              <div className="rounded-[24px] border border-border/70 bg-card px-5 py-4 shadow-sm">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    Found {schemes.length} result{schemes.length === 1 ? "" : "s"} for &quot;{submittedQuery}&quot;
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {appliedFilterCount > 0 ? `${appliedFilterCount} applied filter${appliedFilterCount === 1 ? "" : "s"}` : "Showing all matching schemes"}
                  </p>
                </div>
                {searchError && (
                  <div className="mt-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    {searchError}
                  </div>
                )}
              </div>

              {schemes.length > 0 ? (
                <motion.div
                  className="grid gap-4"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  {visibleSchemes.map((scheme, i) => (
                    <motion.div
                      key={`${scheme.id}-${i}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.06 }}
                    >
                      <SchemeCard scheme={scheme} onClick={() => setSelectedScheme(scheme)} />
                    </motion.div>
                  ))}
                </motion.div>
              ) : (
                <div className="rounded-[28px] border border-dashed bg-card px-6 py-20 text-center shadow-sm">
                  <p className="text-lg font-medium">No exact matches found</p>
                  <p className="mt-2 text-muted-foreground">
                    Try adjusting the query, removing a filter, or using Search Schemes for You.
                  </p>
                </div>
              )}

              {schemes.length > 0 && (
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {pageStart + 1}-{pageEnd} of {schemes.length} schemes
                  </p>
                  {totalPages > 1 && (
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setResultsPage((prev) => Math.max(1, prev - 1))}
                        disabled={safeResultsPage === 1}
                      >
                        <ChevronLeft className="mr-1 h-4 w-4" />
                        Previous
                      </Button>
                      <span className="text-sm font-medium text-muted-foreground">
                        Page {safeResultsPage} of {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setResultsPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={safeResultsPage === totalPages}
                      >
                        Next
                        <ChevronRight className="ml-1 h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-[28px] border border-dashed bg-card px-6 py-24 text-center text-muted-foreground shadow-sm">
              Enter a query above to start searching. You can keep the filters empty, or set them first and
              search once.
            </div>
          )}
        </section>
      </div>

      <Modal
        isOpen={!!selectedScheme}
        onClose={() => setSelectedScheme(null)}
        title={selectedScheme?.name || "Scheme Details"}
        url={selectedScheme?.url}
        className="h-[85vh] max-h-[800px]"
      >
        {selectedScheme && <ChatPanel scheme={selectedScheme} />}
      </Modal>
    </div>
  )
}

function FilterSection({
  title,
  isOpen,
  onToggle,
  children,
}: {
  title: string
  isOpen: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="border-b border-border/60 pb-4 last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between py-2 text-left"
      >
        <span className="font-semibold text-foreground">{title}</span>
        {isOpen ? (
          <Minus className="h-4 w-4 text-emerald-600" />
        ) : (
          <Plus className="h-4 w-4 text-emerald-600" />
        )}
      </button>
      {isOpen && <div className="pt-2">{children}</div>}
    </div>
  )
}

function CheckboxList({
  options,
  selected,
  onToggle,
  columns = 1,
  scrollable = false,
}: {
  options: Option[]
  selected: string[]
  onToggle: (value: string) => void
  columns?: 1 | 2
  scrollable?: boolean
}) {
  return (
    <div
      className={cn(
        "grid gap-2",
        columns === 2 ? "sm:grid-cols-2" : "grid-cols-1",
        scrollable && "max-h-60 overflow-y-auto pr-1",
      )}
    >
      {options.map((option) => {
        const checked = selected.includes(option.value)
        return (
          <label
            key={option.value}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-2xl border px-3 py-2 text-sm transition",
              checked
                ? "border-primary/50 bg-primary/5"
                : "border-border/70 bg-background/70 hover:border-primary/30",
            )}
          >
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-border text-primary"
              checked={checked}
              onChange={() => onToggle(option.value)}
            />
            <span className="leading-5">{option.label}</span>
          </label>
        )
      })}
    </div>
  )
}

function SelectField({
  value,
  placeholder,
  options,
  onChange,
}: {
  value: string
  placeholder: string
  options: Option[]
  onChange: (value: string) => void
}) {
  return (
    <select
      className="w-full rounded-2xl border border-border/70 bg-background px-4 py-3 text-sm outline-none transition focus:border-primary"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center">
          <Loader2 className="mr-2 inline animate-spin" /> Loading...
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  )
}
