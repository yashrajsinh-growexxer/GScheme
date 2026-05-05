"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import {
  Search,
  ArrowRight,
  ShieldCheck,
  Library,
  GitCompareArrows,
  Sparkles,
  UserRound,
  FileSearch,
  ListChecks,
  MapPinned,
  MessageSquareText,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"

const userPaths = [
  {
    title: "Search by Scheme",
    description: "Look up a known scheme or search by keywords like scholarship, pension, or business loan.",
    href: "/search",
    icon: FileSearch,
  },
  {
    title: "Check Eligibility",
    description: "Answer a few profile questions and get schemes that better match your situation.",
    href: "/eligibility",
    icon: UserRound,
  },
  {
    title: "Compare Options",
    description: "Place schemes side by side to review benefits, eligibility, documents, and application steps.",
    href: "/compare",
    icon: GitCompareArrows,
  },
]

const howItWorks = [
  {
    title: "Tell us what you need",
    description: "Start with a scheme name, a benefit type, or your basic profile details.",
    icon: MessageSquareText,
  },
  {
    title: "Refine the match",
    description: "Use filters for state, category, age, gender, caste, and profession where needed.",
    icon: ListChecks,
  },
  {
    title: "Review next steps",
    description: "Open a scheme to understand benefits, eligibility, required documents, and where to apply.",
    icon: MapPinned,
  },
]

const popularSearches = ["PM Kisan", "Student scholarship", "Women welfare", "Startup loan"]

export default function Home() {
  const router = useRouter()
  const [query, setQuery] = useState("")

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query)}`)
    }
  }

  return (
    <div className="flex-1 bg-background">
      <section className="container mx-auto px-4 py-12 md:px-6 lg:py-16">
        <motion.div
          className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_440px]"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary">
              <Sparkles className="h-4 w-4" />
              AI-assisted scheme discovery
            </div>
            <h1 className="max-w-3xl text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl md:text-6xl">
              Find government schemes you may be eligible for
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">
              Search 4,500+ central and state schemes by name, profile, category, or eligibility.
              QSkim helps you move from confusing policy pages to clearer options in one place.
            </p>

            <div className="mt-8 w-full max-w-2xl">
              <form onSubmit={handleSearch} className="relative flex items-center w-full">
                <div className="absolute left-4 text-muted-foreground">
                  <VoiceRecorder mode="translit" onTranscript={(text) => setQuery(prev => prev + text)} />
                </div>
                <Input
                  type="text"
                  placeholder="Search for a scheme, benefit, or category..."
                  className="h-14 rounded-full border-muted/70 bg-card pl-12 pr-14 text-base shadow-lg focus-visible:ring-primary/30 sm:text-lg"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <Button
                  type="submit"
                  size="icon"
                  className="absolute right-2 h-10 w-10 rounded-full bg-primary hover:bg-primary/90"
                >
                  <Search className="h-5 w-5" />
                </Button>
              </form>

              <div className="mt-4 flex flex-wrap gap-2">
                {popularSearches.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setQuery(item)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-sm font-medium text-muted-foreground transition hover:border-primary/40 hover:text-primary"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-8 flex flex-col gap-4 sm:flex-row">
              <Button
                size="lg"
                className="h-12 rounded-full px-8 text-base shadow-lg transition-all hover:shadow-xl"
                onClick={() => router.push("/eligibility")}
              >
                Find Schemes for You
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="h-12 rounded-full border-2 px-8 text-base hover:bg-secondary"
                onClick={() => router.push("/compare")}
              >
                <GitCompareArrows className="mr-2 h-5 w-5" />
                Compare Schemes
              </Button>
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 translate-x-3 translate-y-3 rounded-3xl bg-primary/10" />
            <div className="relative rounded-3xl border border-border bg-card p-6 shadow-xl">
              <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
                <div>
                  <p className="text-sm font-semibold text-primary">Recommended Match</p>
                  <h2 className="mt-1 text-xl font-bold text-foreground">Education Support Scheme</h2>
                </div>
                <div className="rounded-full bg-accent px-3 py-1 text-sm font-semibold text-accent-foreground">
                  92% fit
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl bg-secondary p-4">
                  <p className="text-sm font-semibold text-foreground">Why it matches</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    Student profile, education category, state preference, and age range align with this scheme.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-border p-4">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">Benefit</p>
                    <p className="mt-2 text-sm font-semibold text-foreground">Scholarship aid</p>
                  </div>
                  <div className="rounded-2xl border border-border p-4">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">Coverage</p>
                    <p className="mt-2 text-sm font-semibold text-foreground">State + Central</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-4">
                  <ShieldCheck className="h-5 w-5 shrink-0 text-primary" />
                  <p className="text-sm text-muted-foreground">
                    Check official eligibility and documents before applying.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div 
          className="mt-14 grid gap-4 md:grid-cols-3"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {userPaths.map((path) => {
            const Icon = path.icon
            return (
              <button
                key={path.title}
                type="button"
                onClick={() => router.push(path.href)}
                className="group rounded-2xl border border-border bg-card p-6 text-left shadow-sm transition hover:-translate-y-1 hover:border-primary/30 hover:shadow-lg"
              >
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Icon className="h-6 w-6" />
                </div>
                <h2 className="text-xl font-bold text-foreground">{path.title}</h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{path.description}</p>
                <div className="mt-5 inline-flex items-center text-sm font-semibold text-primary">
                  Open
                  <ArrowRight className="ml-2 h-4 w-4 transition group-hover:translate-x-1" />
                </div>
              </button>
            )
          })}
        </motion.div>
      </section>

      <section className="border-y border-border bg-card/60">
        <div className="container mx-auto px-4 py-12 md:px-6">
          <div className="grid gap-8 md:grid-cols-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-primary/80">
                How it works
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground">
                From question to shortlist
              </h2>
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                Start broad, then use profile details and filters to get closer to schemes that are worth reviewing.
              </p>
            </div>
            <div className="grid gap-4 md:col-span-2">
              {howItWorks.map((step, index) => {
                const Icon = step.icon
                return (
                  <div
                    key={step.title}
                    className="flex gap-4 rounded-2xl border border-border bg-background p-5 shadow-sm"
                  >
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      {index + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Icon className="h-5 w-5 text-primary" />
                        <h3 className="font-bold text-foreground">{step.title}</h3>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.description}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-12 md:px-6">
        <motion.div
          className="grid grid-cols-1 gap-5 md:grid-cols-3"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className="flex flex-col items-center rounded-2xl border bg-card p-6 text-center shadow-sm">
            <div className="mb-4 rounded-full bg-primary/10 p-3">
              <Library className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-2xl font-bold">4,566+</h3>
            <p className="mt-2 text-muted-foreground">Central & State Schemes Indexed</p>
          </div>
          <div className="flex flex-col items-center rounded-2xl border bg-card p-6 text-center shadow-sm">
            <div className="mb-4 rounded-full bg-accent p-3">
              <ShieldCheck className="h-8 w-8 text-accent-foreground" />
            </div>
            <h3 className="text-2xl font-bold">15+</h3>
            <p className="mt-2 text-muted-foreground">Categories Covered</p>
          </div>
          <div className="flex flex-col items-center rounded-2xl border bg-card p-6 text-center shadow-sm">
            <div className="mb-4 rounded-full bg-primary/10 p-3">
              <Sparkles className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-2xl font-bold">AI</h3>
            <p className="mt-2 text-muted-foreground">Search, Discovery & Comparison Help</p>
          </div>
        </motion.div>
      </section>
    </div>
  )
}
