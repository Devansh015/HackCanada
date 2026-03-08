'use client'

import { useState, useRef, useEffect } from 'react'
import { useProfile } from '@/context/ProfileContext'
import { sendChatMessage } from '@/lib/api'
import type { ChatMessage } from '@/types/api'

interface ChatBotProps {
  onPanelToggle?: (open: boolean) => void
}

export default function ChatBot({ onPanelToggle }: ChatBotProps) {
  const { profile } = useProfile()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const hasMessages = messages.length > 0 || isTyping

  useEffect(() => {
    onPanelToggle?.(hasMessages)
  }, [hasMessages, onPanelToggle])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSend = async (text?: string) => {
    const message = text ?? input.trim()
    if (!message || !profile?.user_id || isTyping) return

    const userMsg: ChatMessage = { role: 'user', content: message }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)
    setSuggestions([])

    try {
      const history = [...messages, userMsg].slice(-10)
      const data = await sendChatMessage(profile.user_id, message, history)
      const assistantMsg: ChatMessage = { role: 'assistant', content: data.reply }
      setMessages(prev => [...prev, assistantMsg])
      if (data.suggestions?.length) setSuggestions(data.suggestions)
    } catch {
      const errorMsg: ChatMessage = { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsTyping(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* Right-side message panel */}
      <div
        className={`fixed top-0 right-0 z-40 w-[380px] h-full flex flex-col bg-black/70 backdrop-blur-xl border-l border-white/10 transition-transform duration-300 ${
          hasMessages ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold text-sm">CORTEX AI</h3>
            <p className="text-white/40 text-xs mt-0.5">Skills &amp; learning insights</p>
          </div>
          <button
            onClick={() => { setMessages([]); setSuggestions([]) }}
            className="text-white/30 hover:text-white/60 transition-colors"
            title="Clear chat"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600/80 text-white rounded-br-md'
                    : 'bg-white/10 text-white/90 rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white/10 px-4 py-3 rounded-2xl rounded-bl-md flex gap-1.5">
                <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        {suggestions.length > 0 && (
          <div className="px-4 pb-3 flex flex-wrap justify-center gap-1.5 border-t border-white/5 pt-3">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSend(s)}
                className="px-3 py-1.5 text-xs bg-white/10 hover:bg-white/20 border border-white/10 rounded-full text-white/70 hover:text-white transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Bottom-center chat bar */}
      <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-50 w-full max-w-[600px] px-4">
        <div className="flex items-center gap-2 bg-black/60 backdrop-blur-xl border border-white/15 rounded-2xl px-4 py-2.5 shadow-lg shadow-black/40">
          <svg className="w-5 h-5 text-white/30 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={profile ? 'Ask CORTEX about your skills...' : 'Upload a project first'}
            disabled={!profile || isTyping}
            className="flex-1 bg-transparent text-sm text-white placeholder-white/30 outline-none disabled:opacity-40"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || !profile || isTyping}
            className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/90 hover:bg-white text-black transition-colors disabled:opacity-20 disabled:hover:bg-white/90 shrink-0"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </>
  )
}
