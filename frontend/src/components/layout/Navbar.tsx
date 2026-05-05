"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { ArrowLeft, Menu } from "lucide-react"
import { QSkimLogo } from "@/components/brand/QSkimLogo"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function Navbar() {
  const router = useRouter()
  const pathname = usePathname()
  const showBack = pathname !== "/"

  return (
    <div className="sticky top-4 z-50 mx-auto w-full max-w-6xl px-4">
      <header className="flex h-16 items-center justify-between rounded-full border border-border/50 bg-background/80 px-4 shadow-sm backdrop-blur-md supports-[backdrop-filter]:bg-background/60 transition-all">
        <div className="flex items-center gap-4">
          {showBack && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => router.back()}
              className="shrink-0 rounded-full text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          )}
          <Link href="/" className="flex items-center ml-2">
            <QSkimLogo />
          </Link>
        </div>
        
        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-3">
          <nav className="flex items-center gap-1 rounded-full bg-muted/40 p-1 border border-border/30">
            <Link
              href="/search"
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-all hover:bg-background hover:text-foreground hover:shadow-sm",
                pathname.startsWith("/search")
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground"
              )}
            >
              Search
            </Link>
            <Link
              href="/compare"
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-all hover:bg-background hover:text-foreground hover:shadow-sm",
                pathname.startsWith("/compare")
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground"
              )}
            >
              Compare
            </Link>
          </nav>
          <div className="pl-1">
            <Link href="/eligibility">
              <Button className="rounded-full h-9 px-5">
                Check Eligibility
              </Button>
            </Link>
          </div>
        </div>

        {/* Mobile Navigation Toggle */}
        <div className="md:hidden flex items-center pr-2">
          <Button variant="ghost" size="icon" className="rounded-full text-muted-foreground">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle Menu</span>
          </Button>
        </div>
      </header>
    </div>
  )
}
