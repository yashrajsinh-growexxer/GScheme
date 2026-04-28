"use client"

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { Scheme } from "@/lib/api"
import { ChevronRight } from "lucide-react"

export function SchemeCard({ scheme, onClick }: { scheme: Scheme; onClick: () => void }) {
  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 group transition-all"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start">
          <CardTitle className="text-xl group-hover:text-primary transition-colors">
            {scheme.name}
          </CardTitle>
          {scheme.matchScore && (
            <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 shrink-0 ml-2">
              {scheme.matchScore}% Match
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between mt-2">
          <div className="flex gap-2">
            <Badge variant="outline">{scheme.category}</Badge>
            <Badge variant="outline" className="bg-secondary">{scheme.state}</Badge>
          </div>
          <div className="text-muted-foreground group-hover:text-primary transition-colors flex items-center text-sm font-medium">
            Learn more
            <ChevronRight className="h-4 w-4 ml-1" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
