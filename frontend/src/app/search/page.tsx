"use client"

import { useState, useEffect, Suspense, useCallback } from "react"
import { useSearchParams } from "next/navigation"
import { Search as SearchIcon, Loader2, ChevronLeft, ChevronRight } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { SchemeCard } from "@/components/ui/scheme-card"
import { Modal } from "@/components/ui/modal"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { searchSchemes, type Scheme } from "@/lib/api"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"
import { motion } from "framer-motion"

const SCHEMES_PER_PAGE = 10

function SearchContent() {
  const searchParams = useSearchParams()
  const initialQuery = searchParams.get("q") || ""
  
  const [query, setQuery] = useState(initialQuery)
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [resultsPage, setResultsPage] = useState(1)
  const [selectedScheme, setSelectedScheme] = useState<Scheme | null>(null)

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) return
    setIsLoading(true)
    setHasSearched(true)
    try {
      const results = await searchSchemes(searchQuery)
      setSchemes(results)
      setResultsPage(1)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (initialQuery) {
      const timer = window.setTimeout(() => {
        void performSearch(initialQuery)
      }, 0)
      return () => window.clearTimeout(timer)
    }
  }, [initialQuery, performSearch])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    performSearch(query)
  }

  const totalPages = Math.max(1, Math.ceil(schemes.length / SCHEMES_PER_PAGE))
  const safeResultsPage = Math.min(resultsPage, totalPages)
  const pageStart = (safeResultsPage - 1) * SCHEMES_PER_PAGE
  const pageEnd = Math.min(pageStart + SCHEMES_PER_PAGE, schemes.length)
  const visibleSchemes = schemes.slice(pageStart, pageEnd)

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl flex-1 flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-4">Search Schemes</h1>
        <form onSubmit={handleSearch} className="relative flex items-center w-full">
            <div className="absolute left-4 text-muted-foreground">
              <VoiceRecorder onTranscript={(text) => setQuery(prev => prev + text)} />
            </div>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by scheme name or keywords..."
            className="h-14 pl-12 pr-14 text-lg rounded-full shadow-sm border-muted focus-visible:ring-primary/50"
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

      <div className="flex-1">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin mb-4 text-primary" />
            <p>Searching knowledge base...</p>
          </div>
        ) : hasSearched ? (
          <div className="space-y-6">
            <div className="text-sm text-muted-foreground">
              Found {schemes.length} result{schemes.length === 1 ? "" : "s"} for &quot;{query}&quot;
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
                    transition={{ delay: i * 0.1 }}
                  >
                    <SchemeCard 
                      scheme={scheme} 
                      onClick={() => setSelectedScheme(scheme)} 
                    />
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="text-center py-20 border rounded-xl bg-card border-dashed">
                <p className="text-lg font-medium">No exact matches found</p>
                <p className="text-muted-foreground">Try adjusting your search terms or use the Eligibility Check to find schemes for you.</p>
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
            )}
          </div>
        ) : (
          <div className="text-center py-20 text-muted-foreground">
            Enter a query above to start searching.
          </div>
        )}
      </div>

      <Modal 
        isOpen={!!selectedScheme} 
        onClose={() => setSelectedScheme(null)}
        onBack={() => setSelectedScheme(null)}
        title={selectedScheme?.name || "Scheme Details"}
        className="h-[85vh] max-h-[800px]"
      >
        {selectedScheme && <ChatPanel scheme={selectedScheme} />}
      </Modal>
    </div>
  )
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center"><Loader2 className="animate-spin inline mr-2"/> Loading...</div>}>
      <SearchContent />
    </Suspense>
  )
}
