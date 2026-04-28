"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowLeft, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  onBack?: () => void
  title?: string
  children: React.ReactNode
  className?: string
}

export function Modal({ isOpen, onClose, onBack, title = "Scheme Details", children, className }: ModalProps) {
  // Prevent scrolling when modal is open
  React.useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = "unset"
    }
    return () => {
      document.body.style.overflow = "unset"
    }
  }, [isOpen])

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 50, scale: 0.95 }}
            className={cn(
              "fixed left-[50%] top-[50%] z-50 flex max-h-[92vh] w-full max-w-4xl translate-x-[-50%] translate-y-[-50%] flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-xl",
              className
            )}
          >
            <div className="flex items-center justify-between gap-3 border-b p-4">
              <div className="flex min-w-0 items-center gap-3">
                {onBack && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={onBack}
                    className="shrink-0"
                  >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back
                  </Button>
                )}
                <h2 className="truncate text-lg font-semibold">{title}</h2>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onClose}
                >
                  Close
                </Button>
                <button
                  type="button"
                  aria-label="Close dialog"
                  onClick={onClose}
                  className="rounded-full p-2 hover:bg-accent hover:text-accent-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-4">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
