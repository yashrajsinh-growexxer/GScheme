"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Search, Plus, X, Loader2 } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { searchSchemes, getSchemeCompareData, type Scheme, type SchemeCompareData } from "@/lib/api"
import { cn } from "@/lib/utils"

interface SchemeSelectorProps {
  onSelect: (data: SchemeCompareData) => void
  onRemove: () => void
  selected: SchemeCompareData | null
  index: number
}

export function SchemeSelector({ onSelect, onRemove, selected, index }: SchemeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Scheme[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced search
  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setResults([])
      return
    }
    setIsSearching(true)
    try {
      const schemes = await searchSchemes(searchQuery)
      setResults(schemes.slice(0, 8))
    } catch {
      setResults([])
    } finally {
      setIsSearching(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => performSearch(query), 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, performSearch])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleSelect = async (scheme: Scheme) => {
    setIsOpen(false)
    setQuery("")
    setResults([])
    setIsLoading(true)
    try {
      const data = await getSchemeCompareData(scheme.id)
      onSelect(data)
    } catch {
      // pass
    } finally {
      setIsLoading(false)
    }
  }

  // Empty / "Add" state
  if (!selected && !isLoading) {
    return (
      <div ref={dropdownRef} className="relative flex-1 min-w-0">
        <motion.div
          layout
          className={cn(
            "rounded-xl border-2 border-dashed transition-all min-h-[120px] flex flex-col items-center justify-center cursor-pointer",
            isOpen
              ? "border-primary bg-primary/5"
              : "border-muted hover:border-primary/50 hover:bg-accent/50"
          )}
          onClick={() => {
            setIsOpen(true)
            setTimeout(() => inputRef.current?.focus(), 100)
          }}
        >
          {!isOpen && (
            <div className="flex flex-col items-center gap-2 py-4">
              <div className="p-3 rounded-full bg-primary/10">
                <Plus className="h-6 w-6 text-primary" />
              </div>
              <span className="text-sm font-medium text-muted-foreground">
                Add Scheme {index + 1}
              </span>
            </div>
          )}

          {isOpen && (
            <div className="w-full p-3" onClick={(e) => e.stopPropagation()}>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search scheme name..."
                  className="w-full h-10 pl-9 pr-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
          )}
        </motion.div>

        {/* Search results dropdown */}
        <AnimatePresence>
          {isOpen && (query.trim().length >= 2 || isSearching) && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute top-full left-0 right-0 z-50 mt-1 rounded-xl border bg-card shadow-xl overflow-hidden max-h-[320px] overflow-y-auto"
            >
              {isSearching ? (
                <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Searching...</span>
                </div>
              ) : results.length > 0 ? (
                results.map((scheme, i) => (
                  <button
                    key={`${scheme.id}-${i}`}
                    type="button"
                    className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b last:border-b-0"
                    onClick={() => handleSelect(scheme)}
                  >
                    <p className="text-sm font-medium text-foreground truncate">{scheme.name}</p>
                    <div className="flex gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">{scheme.state}</span>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground">{scheme.category}</span>
                    </div>
                  </button>
                ))
              ) : query.trim().length >= 2 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No schemes found
                </div>
              ) : null}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 min-w-0 rounded-xl border-2 border-primary/30 bg-primary/5 min-h-[120px] flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  // Selected state
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex-1 min-w-0 rounded-xl border-2 border-primary/30 bg-gradient-to-b from-primary/5 to-transparent overflow-hidden"
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-sm text-foreground truncate" title={selected!.name}>
              {selected!.name}
            </h3>
            <div className="flex gap-2 mt-1.5">
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {selected!.state}
              </span>
              <span className="inline-flex items-center rounded-full bg-purple-500/10 px-2 py-0.5 text-xs font-medium text-purple-600">
                {selected!.category}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onRemove}
            className="shrink-0 p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
            title="Remove scheme"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </motion.div>
  )
}
