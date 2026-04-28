"use client"

import { useState, useRef, useEffect } from "react"
import { Send, User, Bot, Loader2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { generalChatAboutSchemes, type ChatMessage, type Profile, type Scheme } from "@/lib/api"
import { VoiceRecorder } from "@/components/ui/VoiceRecorder"
import { cn } from "@/lib/utils"

export function GeneralChatPanel({ schemes, profile }: { schemes: Scheme[], profile: Profile }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Hello! I can answer any questions you have about the schemes recommended for you. What would you like to know?" }
  ])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

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
      await generalChatAboutSchemes(userMsg.content, messages, profile, schemes, (chunk) => {
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
    <div className="flex flex-col h-[500px] mt-12 bg-background border rounded-xl shadow-sm overflow-hidden">
      <div className="bg-muted px-4 py-3 border-b flex items-center gap-2">
        <Bot size={18} className="text-primary" />
        <h3 className="font-semibold text-sm">Chat about these recommendations</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
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
            placeholder="Ask about these schemes..."
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
