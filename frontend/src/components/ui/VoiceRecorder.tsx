"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import { Mic, Square, Loader2 } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { transcribeAudio } from "@/lib/api"
import { cn } from "@/lib/utils"

interface VoiceRecorderProps {
  onTranscript: (text: string) => void
  disabled?: boolean
  mode?: "transcribe" | "translate" | "translit" | "verbatim" | "codemix"
}

export function VoiceRecorder({
  onTranscript,
  disabled = false,
  mode = "transcribe",
}: VoiceRecorderProps) {
  const [state, setState] = useState<"idle" | "recording" | "processing">("idle")
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const errorTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current)
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  const startRecording = useCallback(async () => {
    setError(null)

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      streamRef.current = stream

      // Try webm/opus first, fall back to webm, then any available
      let mimeType = "audio/webm;codecs=opus"
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "audio/webm"
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = ""
        }
      }

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      recorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null

        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }

        if (chunksRef.current.length === 0) {
          setState("idle")
          return
        }

        setState("processing")

        const audioBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        })

        try {
          const result = await transcribeAudio(audioBlob, mode)
          if (result.transcript) {
            onTranscript(result.transcript)
          } else {
            setError("No speech detected")
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : "Transcription failed"
          setError(message)
        } finally {
          setState("idle")
          setDuration(0)
        }
      }

      mediaRecorderRef.current = recorder
      recorder.start(250)
      setState("recording")
      setDuration(0)

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1)
      }, 1000)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Microphone access denied"
      setError(message)
      setState("idle")
    }
  }, [mode, onTranscript])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop()
    }
  }, [])

  const handleClick = () => {
    if (disabled) return
    if (state === "idle") {
      startRecording()
    } else if (state === "recording") {
      stopRecording()
    }
  }

  const formatDuration = (s: number) =>
    `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`

  return (
    <>
      {/* Mic button */}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || state === "processing"}
        className={cn(
          "relative flex items-center justify-center transition-all duration-200",
          state === "recording"
            ? "text-red-500"
            : "text-muted-foreground hover:text-primary",
          (disabled || state === "processing") && "opacity-50 cursor-not-allowed"
        )}
        title={state === "idle" ? "Click to speak" : state === "recording" ? "Click to stop" : "Processing..."}
      >
        {state === "processing" ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : state === "recording" ? (
          <>
            {/* Pulsing ring */}
            <span className="absolute inline-flex h-7 w-7 rounded-full bg-red-400/30 animate-ping" />
            <Mic className="h-5 w-5 relative z-10" />
          </>
        ) : (
          <Mic className="h-5 w-5 cursor-pointer" />
        )}
      </button>

      {/* Recording overlay / modal */}
      <AnimatePresence>
        {state === "recording" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <motion.div
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.85, opacity: 0 }}
              className="flex flex-col items-center gap-6 rounded-2xl border bg-card p-10 shadow-2xl max-w-sm w-full mx-4"
            >
              {/* Animated concentric circles */}
              <div className="relative flex items-center justify-center w-28 h-28">
                <span className="absolute w-28 h-28 rounded-full bg-red-500/10 animate-ping" style={{ animationDuration: "1.5s" }} />
                <span className="absolute w-20 h-20 rounded-full bg-red-500/15 animate-ping" style={{ animationDuration: "2s" }} />
                <span className="absolute w-14 h-14 rounded-full bg-red-500/20 animate-pulse" />
                <div className="relative z-10 flex items-center justify-center w-12 h-12 rounded-full bg-red-500 text-white shadow-lg">
                  <Mic className="h-6 w-6" />
                </div>
              </div>

              {/* Label */}
              <div className="text-center">
                <p className="text-lg font-semibold text-foreground">🎙️ Listening...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {mode === "translit" ? "Speak the scheme name clearly" : "Speak now in any language"}
                </p>
              </div>

              {/* Timer */}
              <div className="font-mono text-2xl font-bold text-red-500 tabular-nums">
                {formatDuration(duration)}
              </div>

              {/* Stop button */}
              <button
                type="button"
                onClick={stopRecording}
                className="flex items-center gap-2 px-6 py-3 rounded-full bg-red-500 text-white font-medium hover:bg-red-600 transition-colors shadow-lg hover:shadow-xl"
              >
                <Square className="h-4 w-4 fill-current" />
                Stop Recording
              </button>
            </motion.div>
          </motion.div>
        )}

        {state === "processing" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.85, opacity: 0 }}
              className="flex flex-col items-center gap-4 rounded-2xl border bg-card p-8 shadow-2xl"
            >
              <Loader2 className="h-10 w-10 animate-spin text-primary" />
              <p className="text-lg font-semibold">Transcribing...</p>
              <p className="text-sm text-muted-foreground">Converting speech to text</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[110] bg-destructive text-destructive-foreground px-4 py-2 rounded-lg shadow-lg text-sm font-medium"
            onAnimationComplete={() => {
              if (errorTimeoutRef.current) clearTimeout(errorTimeoutRef.current)
              errorTimeoutRef.current = setTimeout(() => setError(null), 3000)
            }}
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
