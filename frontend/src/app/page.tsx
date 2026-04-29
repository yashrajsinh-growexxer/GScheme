"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Search, ArrowRight, ShieldCheck, Zap, Library, GitCompareArrows } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"

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
    <div className="flex-1 flex flex-col items-center justify-center pt-20 pb-16">
      <div className="container px-4 md:px-6 flex flex-col items-center text-center max-w-4xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl text-foreground">
            Discover Government Schemes{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-500">
              Powered by AI
            </span>
          </h1>
          <p className="mt-6 text-xl text-muted-foreground max-w-2xl mx-auto">
            Navigating government benefits has never been easier. Search by name or let our AI find what you are eligible for in seconds.
          </p>
        </motion.div>

        {/* Search Bar on Landing Page */}
        <motion.div 
          className="w-full max-w-2xl mt-10 relative"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <form onSubmit={handleSearch} className="relative flex items-center w-full">
            <div className="absolute left-4 text-muted-foreground">
              <VoiceRecorder mode="translit" onTranscript={(text) => setQuery(prev => prev + text)} />
            </div>
            <Input
              type="text"
              placeholder="Search for a scheme (e.g., PM Kisan, Mudra Yojana)..."
              className="h-14 pl-12 pr-14 text-lg rounded-full shadow-lg border-muted/50 focus-visible:ring-primary/30"
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
        </motion.div>

        <motion.div 
          className="flex flex-col sm:flex-row gap-4 mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Button 
            size="lg" 
            className="rounded-full text-base px-8 h-12 shadow-lg hover:shadow-xl transition-all"
            onClick={() => router.push("/eligibility")}
          >
            Find Schemes for You
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
          <Button 
            size="lg" 
            variant="outline"
            className="rounded-full text-base px-8 h-12 border-2 hover:bg-secondary"
            onClick={() => router.push("/compare")}
          >
            <GitCompareArrows className="mr-2 h-5 w-5" />
            Compare Schemes
          </Button>
        </motion.div>

        {/* Stats & Features */}
        <motion.div 
          className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full mt-24"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className="flex flex-col items-center p-6 bg-card rounded-2xl shadow-sm border">
            <div className="p-3 bg-primary/10 rounded-full mb-4">
              <Library className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-2xl font-bold">4,566+</h3>
            <p className="text-muted-foreground text-center mt-2">Central & State Schemes Indexed</p>
          </div>
          <div className="flex flex-col items-center p-6 bg-card rounded-2xl shadow-sm border">
            <div className="p-3 bg-purple-500/10 rounded-full mb-4">
              <Zap className="h-8 w-8 text-purple-500" />
            </div>
            <h3 className="text-2xl font-bold">Instant</h3>
            <p className="text-muted-foreground text-center mt-2">AI-powered Chatbot assistance</p>
          </div>
          <div className="flex flex-col items-center p-6 bg-card rounded-2xl shadow-sm border">
            <div className="p-3 bg-emerald-500/10 rounded-full mb-4">
              <ShieldCheck className="h-8 w-8 text-emerald-500" />
            </div>
            <h3 className="text-2xl font-bold">15+</h3>
            <p className="text-muted-foreground text-center mt-2">Categories Covered (Health, Education, etc.)</p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
