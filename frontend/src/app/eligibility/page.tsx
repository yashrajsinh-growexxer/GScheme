"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, ChevronLeft, Loader2, Minus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SchemeCard } from "@/components/ui/scheme-card"
import { Modal } from "@/components/ui/modal"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { discoverSchemes, type Scheme } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  CASTE_OPTIONS,
  GENDER_OPTIONS,
  PROFILE_STATE_OPTIONS,
  PROFESSION_OPTIONS,
  SCHEME_CATEGORY_OPTIONS,
  toggleFilterValue,
} from "@/lib/scheme-filters"

const STEPS = [
  { id: "gender", title: "Gender", type: "radio", options: GENDER_OPTIONS.map((option) => option.label) },
  { id: "age", title: "Age", type: "number", placeholder: "e.g., 25" },
  { id: "state", title: "State", type: "select", options: PROFILE_STATE_OPTIONS.map((option) => option.label) },
  { id: "area", title: "Area", type: "radio", options: ["Urban", "Rural"] },
  { id: "caste", title: "Caste Category", type: "select", options: CASTE_OPTIONS.map((option) => option.label) },
  { id: "disability", title: "Disability", type: "radio", options: ["No", "Yes"] },
  { id: "profession", title: "Profession", type: "select", options: PROFESSION_OPTIONS.map((option) => option.label) },
]

const SCHEMES_PER_PAGE = 10

export default function EligibilityPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const [profile, setProfile] = useState<Record<string, string>>({})
  const [draftCategoryFilters, setDraftCategoryFilters] = useState<string[]>([])
  const [appliedCategoryFilters, setAppliedCategoryFilters] = useState<string[]>([])
  
  const [isDiscovering, setIsDiscovering] = useState(false)
  const [discoveryResult, setDiscoveryResult] = useState<{summary: string, schemes: Scheme[]} | null>(null)
  const [discoverError, setDiscoverError] = useState("")
  const [resultsPage, setResultsPage] = useState(1)
  const [selectedScheme, setSelectedScheme] = useState<Scheme | null>(null)

  const step = STEPS[currentStep]
  const value = profile[step.id] || ""
  const canProceed = value.toString().trim().length > 0

  const runDiscovery = async () => {
    setIsDiscovering(true)
    setDiscoverError("")
    try {
      const result = await discoverSchemes(profile)
      setDiscoveryResult(result)
      setDraftCategoryFilters([])
      setAppliedCategoryFilters([])
      setResultsPage(1)
    } catch (err) {
      console.error(err)
      setDiscoverError(err instanceof Error ? err.message : "Unable to discover schemes right now.")
    } finally {
      setIsDiscovering(false)
    }
  }

  const handleNext = async () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(prev => prev + 1)
    } else {
      await runDiscovery()
    }
  }

  const allSchemes = discoveryResult?.schemes || []
  const schemes = appliedCategoryFilters.length > 0
    ? allSchemes.filter((scheme) => {
        const normalizedCategory = scheme.category.trim().toLowerCase()
        return SCHEME_CATEGORY_OPTIONS.some(
          (option) =>
            appliedCategoryFilters.includes(option.value) &&
            option.label.toLowerCase() === normalizedCategory,
        )
      })
    : allSchemes
  const totalPages = Math.max(1, Math.ceil(schemes.length / SCHEMES_PER_PAGE))
  const safeResultsPage = Math.min(resultsPage, totalPages)
  const pageStart = (safeResultsPage - 1) * SCHEMES_PER_PAGE
  const pageEnd = Math.min(pageStart + SCHEMES_PER_PAGE, schemes.length)
  const visibleSchemes = schemes.slice(pageStart, pageEnd)

  const handleBack = () => {
    if (currentStep > 0) setCurrentStep(prev => prev - 1)
  }

  const handleApplyCategoryFilters = () => {
    setAppliedCategoryFilters(draftCategoryFilters)
    setResultsPage(1)
  }

  const handleResetCategoryFilters = () => {
    setDraftCategoryFilters([])
    setAppliedCategoryFilters([])
    setResultsPage(1)
  }

  // Render Form Step
  if (!isDiscovering && !discoveryResult) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-lg">
          <div className="mb-8">
            <div className="flex justify-between text-sm font-medium text-muted-foreground mb-2">
              <span>Step {currentStep + 1} of {STEPS.length}</span>
              <span>{Math.round(((currentStep + 1) / STEPS.length) * 100)}%</span>
            </div>
            <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
              <div 
                className="bg-primary h-full transition-all duration-300"
                style={{ width: (((currentStep + 1) / STEPS.length) * 100) + '%' }}
              />
            </div>
          </div>

          <CardWrapper>
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="min-h-[200px] flex flex-col justify-center"
              >
                <h2 className="text-2xl font-bold mb-6 text-center">What is your {step.title.toLowerCase()}?</h2>
                
                {step.type === "radio" && (
                  <div className="grid gap-3">
                    {step.options?.map(opt => (
                      <button
                        key={opt}
                        onClick={() => setProfile({...profile, [step.id]: opt})}
                        className={cn(
                          "w-full p-4 rounded-xl border-2 text-left transition-all",
                          value === opt 
                            ? "border-primary bg-primary/5 font-medium" 
                            : "border-muted hover:border-primary/50 hover:bg-accent"
                        )}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}

                {step.type === "select" && (
                  <div className="grid gap-3">
                    <select 
                      className="w-full p-4 rounded-xl border-2 border-muted bg-background focus:border-primary focus:ring-0 outline-none appearance-none"
                      value={value}
                      onChange={(e) => setProfile({...profile, [step.id]: e.target.value})}
                    >
                      <option value="" disabled>Select {step.title}...</option>
                      {step.options?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                )}

                {step.type === "number" && (
                  <div>
                    <Input 
                      type="number" 
                      placeholder={step.placeholder}
                      className="h-14 text-lg rounded-xl border-2 border-muted focus-visible:ring-0 focus-visible:border-primary text-center"
                      value={value}
                      onChange={(e) => setProfile({...profile, [step.id]: e.target.value})}
                      autoFocus
                    />
                  </div>
                )}
              </motion.div>
            </AnimatePresence>

            {discoverError && (
              <div className="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {discoverError}
              </div>
            )}

            <div className="flex justify-between mt-8 pt-6 border-t">
              <Button 
                variant="ghost" 
                onClick={handleBack} 
                disabled={currentStep === 0}
                className="text-muted-foreground"
              >
                <ChevronLeft className="mr-2 h-4 w-4" /> Back
              </Button>
              <Button 
                onClick={handleNext} 
                disabled={!canProceed}
                className="px-8 rounded-full"
              >
                {currentStep === STEPS.length - 1 ? "Discover Schemes" : "Next"}
                {currentStep !== STEPS.length - 1 && <ChevronRight className="ml-2 h-4 w-4" />}
              </Button>
            </div>
          </CardWrapper>
        </div>
      </div>
    )
  }

  // Render Loading State
  if (isDiscovering) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-4">
        <Loader2 className="h-12 w-12 animate-spin text-primary mb-6" />
        <h2 className="text-2xl font-bold">Analyzing your profile...</h2>
        <p className="text-muted-foreground mt-2 text-center max-w-md">
          Our AI is searching through hundreds of government databases to find the perfect schemes for you.
        </p>
      </div>
    )
  }

  // Render Results State
  return (
    <div className="container mx-auto max-w-7xl flex-1 px-4 py-8">
      <div className="mb-8 rounded-[28px] border border-border/70 bg-gradient-to-br from-card via-card to-emerald-50/40 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-primary/80">
              Find Schemes For You
            </p>
            <h1 className="mt-2 text-3xl font-bold text-foreground">Your recommended schemes</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Based on your profile, we found these matches. You can narrow them by scheme category from the left panel.
            </p>
          </div>
          <Button variant="outline" onClick={() => {
            setDiscoveryResult(null)
            setDiscoverError("")
            setCurrentStep(0)
            setProfile({})
            setDraftCategoryFilters([])
            setAppliedCategoryFilters([])
            setResultsPage(1)
          }}>
            Start Over
          </Button>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-[28px] border border-border/70 bg-card/95 p-5 shadow-sm backdrop-blur">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">Filter By</h2>
                <p className="text-sm text-muted-foreground">Narrow the recommended schemes by category.</p>
              </div>
              <button
                type="button"
                onClick={handleResetCategoryFilters}
                className="text-sm font-semibold text-emerald-600 transition hover:text-emerald-700"
              >
                Reset Filters
              </button>
            </div>

            <div className="border-b border-border/60 pb-4">
              <div className="flex items-center justify-between py-2 text-left">
                <span className="font-semibold text-foreground">Scheme Category</span>
                <Minus className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="grid max-h-80 gap-2 overflow-y-auto pr-1 pt-2">
                {SCHEME_CATEGORY_OPTIONS.map((option) => {
                  const checked = draftCategoryFilters.includes(option.value)
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
                        onChange={() => {
                          setDraftCategoryFilters((prev) => toggleFilterValue(prev, option.value))
                        }}
                      />
                      <span className="leading-5">{option.label}</span>
                    </label>
                  )
                })}
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 border-t border-border/70 pt-5">
              <Button onClick={handleApplyCategoryFilters} className="rounded-full">
                Apply Filters
              </Button>
              <p className="text-xs text-muted-foreground">
                {draftCategoryFilters.length > 0
                  ? `${draftCategoryFilters.length} categor${draftCategoryFilters.length === 1 ? "y" : "ies"} selected`
                  : "No category filter selected"}
              </p>
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          {discoverError && (
            <div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {discoverError}
            </div>
          )}

          <div className="mb-6 rounded-[24px] border border-border/70 bg-card px-5 py-4 shadow-sm">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Found {schemes.length} result{schemes.length === 1 ? "" : "s"} based on your profile
              </p>
              <p className="text-sm text-muted-foreground">
                {appliedCategoryFilters.length > 0
                  ? `${appliedCategoryFilters.length} applied categor${appliedCategoryFilters.length === 1 ? "y" : "ies"}`
                  : "Showing all recommended schemes"}
              </p>
            </div>
          </div>

          {schemes.length > 0 ? (
            <div className="grid gap-4">
              {visibleSchemes.map((scheme, i) => (
                <motion.div
                  key={`${scheme.id}-${i}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <SchemeCard scheme={scheme} onClick={() => setSelectedScheme(scheme)} />
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="rounded-[28px] border border-dashed bg-card px-6 py-20 text-center shadow-sm">
              <p className="text-lg font-medium">No schemes match the selected category filter</p>
              <p className="mt-2 text-muted-foreground">
                Try removing a category filter to see more recommendations.
              </p>
            </div>
          )}

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {schemes.length ? pageStart + 1 : 0}-{pageEnd} of {schemes.length} schemes
            </p>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setResultsPage(prev => Math.max(1, prev - 1))}
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
                  onClick={() => setResultsPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={safeResultsPage === totalPages}
                >
                  Next
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
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

function CardWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-card rounded-2xl shadow-xl border p-6 md:p-8">
      {children}
    </div>
  )
}