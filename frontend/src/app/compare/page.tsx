"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { GitCompareArrows, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { SchemeSelector } from "@/components/compare/SchemeSelector"
import { ComparisonGrid } from "@/components/compare/ComparisonGrid"
import type { SchemeCompareData } from "@/lib/api"

export default function ComparePage() {
  const [schemes, setSchemes] = useState<(SchemeCompareData | null)[]>([null, null])

  const filledCount = schemes.filter(Boolean).length
  const showThird = filledCount >= 2 && schemes.length < 3

  const handleSelect = (index: number, data: SchemeCompareData) => {
    setSchemes((prev) => {
      const next = [...prev]
      next[index] = data
      return next
    })
  }

  const handleRemove = (index: number) => {
    setSchemes((prev) => {
      const next = [...prev]
      next[index] = null
      // If removing from the first two slots and we have a 3rd, collapse
      if (next.length === 3 && !next[2]) {
        next.pop()
      }
      return next
    })
  }

  const handleAddThird = () => {
    if (schemes.length < 3) {
      setSchemes((prev) => [...prev, null])
    }
  }

  const handleReset = () => {
    setSchemes([null, null])
  }

  const activeSchemes = schemes.filter(Boolean) as SchemeCompareData[]

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl flex-1">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary/20 to-purple-500/20">
              <GitCompareArrows className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Compare Schemes</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Select up to 3 schemes to compare side by side
              </p>
            </div>
          </div>
          {filledCount > 0 && (
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
          )}
        </div>
      </motion.div>

      {/* Selector cards */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="flex gap-4"
      >
        {schemes.map((scheme, index) => (
          <SchemeSelector
            key={index}
            index={index}
            selected={scheme}
            onSelect={(data) => handleSelect(index, data)}
            onRemove={() => handleRemove(index)}
          />
        ))}

        {/* Add 3rd scheme button */}
        {showThird && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            type="button"
            onClick={handleAddThird}
            className="flex-1 min-w-0 rounded-xl border-2 border-dashed border-muted hover:border-primary/50 hover:bg-accent/50 transition-all min-h-[120px] flex flex-col items-center justify-center gap-2 cursor-pointer"
          >
            <div className="p-2 rounded-full bg-muted">
              <GitCompareArrows className="h-5 w-5 text-muted-foreground" />
            </div>
            <span className="text-xs font-medium text-muted-foreground">
              + Add 3rd Scheme
            </span>
          </motion.button>
        )}
      </motion.div>

      {/* Comparison grid */}
      {activeSchemes.length >= 2 && (
        <ComparisonGrid schemes={schemes} />
      )}

      {/* Empty state hint */}
      {activeSchemes.length < 2 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mt-16 text-center"
        >
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
            <GitCompareArrows className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-muted-foreground">
            Select at least 2 schemes to compare
          </h3>
          <p className="text-sm text-muted-foreground/70 mt-1 max-w-md mx-auto">
            Search for government schemes by name using the selectors above. 
            The comparison table will appear once you have selected two or more schemes.
          </p>
        </motion.div>
      )}
    </div>
  )
}
