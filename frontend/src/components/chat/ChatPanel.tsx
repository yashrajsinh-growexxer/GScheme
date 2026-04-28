"use client"

import { useState, useRef, useEffect } from "react"
import { Send, User, Bot, Loader2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { chatAboutScheme, type ChatMessage, type Scheme } from "@/lib/api"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"
import { cn } from "@/lib/utils"

export function ChatPanel({ scheme }: { scheme: Scheme }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const fetchRef = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Auto-fetch initial summary on mount
  useEffect(() => {
    if (fetchRef.current) return
    fetchRef.current = true
    
    const fetchInitialSummary = async () => {
      setIsLoading(true)
      
      // We add an empty assistant message to stream the response into
      setMessages([{ role: "assistant", content: "" }])
      
      try {
        await chatAboutScheme(
          scheme.id, 
          "Format the response in Markdown. Start with the authentic scheme name in bold. Then write **Summary:** followed by only a detailed 3-4 line summary of this scheme. Bold important main points and scheme-specific terms. Do not list full eligibility, benefits, documents, or application steps yet. End exactly with: **Do you want to know more about its eligibility, benefits, or application process?**", 
          [], 
          (chunk) => {
            setMessages(prev => {
              const newMsgs = [...prev]
              if (newMsgs.length > 0) {
                const lastIdx = newMsgs.length - 1
                newMsgs[lastIdx] = {
                  ...newMsgs[lastIdx],
                  content: newMsgs[lastIdx].content + chunk
                }
              }
              return newMsgs
            })
          }
        )
      } catch (err) {
        console.error(err)
        setMessages([{ role: "assistant", content: "Sorry, I encountered an error loading the scheme summary." }])
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchInitialSummary()
  }, [scheme.id])

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isLoading) return

    const userMsg: ChatMessage = { role: "user", content: input }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setIsLoading(true)

    // Add empty assistant message to stream into
    setMessages(prev => [...prev, { role: "assistant", content: "" }])

    try {
      await chatAboutScheme(scheme.id, userMsg.content, messages, (chunk) => {
        setMessages(prev => {
          const newMsgs = [...prev]
          if (newMsgs.length > 0) {
            const lastIdx = newMsgs.length - 1
            newMsgs[lastIdx] = {
              ...newMsgs[lastIdx],
              content: newMsgs[lastIdx].content + chunk
            }
          }
          return newMsgs
        })
      })
    } catch (err) {
       console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg bg-background/50">
      <div className="flex-1 space-y-6 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              "flex w-full",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div className={cn(
              "flex max-w-[85%] gap-3",
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            )}>
              <div className={cn(
                "flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center mt-1",
                msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400"
              )}>
                {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={cn(
                "px-5 py-4 rounded-2xl shadow-sm text-sm overflow-hidden",
                msg.role === "user" 
                  ? "bg-primary text-primary-foreground rounded-tr-none" 
                  : "bg-card border text-card-foreground rounded-tl-none prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:p-0 prose-strong:text-foreground prose-headings:text-foreground prose-a:text-primary"
              )}>
                {msg.role === "user" ? (
                  msg.content
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          </div>
        ))}
        {isLoading && messages.length > 0 && messages[messages.length - 1].content === "" && (
          <div className="flex justify-start">
            <div className="flex gap-3 max-w-[80%]">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mt-1">
                <Bot size={16} />
              </div>
              <div className="px-5 py-4 rounded-2xl bg-card border rounded-tl-none flex items-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t bg-card">
        <form onSubmit={handleSend} className="relative flex items-center">
           <div className="absolute left-3 text-muted-foreground">
              <VoiceRecorder onTranscript={(text) => setInput(prev => prev + text)} disabled={isLoading} />
            </div>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about eligibility, documents required, etc..."
            className="pr-12 pl-10 h-12 rounded-full border-muted/50 focus-visible:ring-primary/50 shadow-sm"
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isLoading}
            className="absolute right-1.5 h-9 w-9 rounded-full bg-primary hover:bg-primary/90"
          >
            <Send size={16} />
          </Button>
        </form>
      </div>
    </div>
  )
}
