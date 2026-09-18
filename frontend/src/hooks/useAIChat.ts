import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../lib/api';

export interface ToolActivity {
  tool: string;
  input: Record<string, unknown>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolActivity?: ToolActivity[];
}

interface AIStatus {
  configured: boolean;
  enabled: boolean;
  provider: string;
  model: string;
  thinkingLevel?: string;
}

export function useAIChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [contextSummary, setContextSummary] = useState<string>('');
  const abortRef = useRef<AbortController | null>(null);
  const statusProviderRef = useRef<string | null>(null);

  const checkStatus = useCallback(async () => {
    try {
      const res = await api.get('/api/ai/chat/status');
      const newStatus = res.data as AIStatus;
      if (
        statusProviderRef.current !== null
        && statusProviderRef.current !== newStatus.provider
        && sessionId
      ) {
        setSessionId(null);
        setMessages([]);
        setContextSummary('');
      }
      statusProviderRef.current = newStatus.provider;
      setStatus(newStatus);
    } catch {
      setStatus({ configured: false, enabled: false, provider: 'anthropic', model: '' });
    }
  }, [sessionId]);

  useEffect(() => { checkStatus(); }, [checkStatus]);

  const startSession = useCallback(async () => {
    setError(null);
    try {
      const res = await api.post('/api/ai/chat/start');
      setSessionId(res.data.sessionId);
      setContextSummary(res.data.contextSummary);
      setMessages([]);
      return res.data.sessionId as string;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start session';
      setError(msg);
      return null;
    }
  }, []);

  const streamOnce = useCallback(async (sid: string, text: string) => {
    const baseUrl = api.defaults.baseURL || '';
    const response = await fetch(`${baseUrl}/api/ai/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: sid, message: text }),
      signal: abortRef.current?.signal,
    });

    if (!response.ok || !response.body) {
      setError('Failed to connect to AI service.');
      return 'failed';
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulated = '';
    let providerChanged = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === 'text_delta') {
            accumulated += event.text;
            const nextText = accumulated;
            setMessages(prev => {
              const next = [...prev];
              const lastIdx = next.length - 1;
              if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
                next[lastIdx] = { ...next[lastIdx], content: nextText };
              }
              return next;
            });
          } else if (event.type === 'tool_use') {
            const activity: ToolActivity = { tool: event.tool, input: event.input };
            setMessages(prev => {
              const next = [...prev];
              const lastIdx = next.length - 1;
              if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
                const existing = next[lastIdx].toolActivity || [];
                next[lastIdx] = { ...next[lastIdx], toolActivity: [...existing, activity] };
              }
              return next;
            });
          } else if (event.type === 'error') {
            if (event.error === 'provider_changed') {
              providerChanged = true;
            } else {
              setError(event.error);
            }
          }
        } catch {
          // Skip malformed SSE lines.
        }
      }
    }

    return providerChanged ? 'provider_changed' : 'ok';
  }, []);

  const sendMessage = useCallback(async (text: string, isRetry = false) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession();
      if (!sid) return;
    }

    setError(null);
    setIsStreaming(true);

    const userMsg: ChatMessage = { role: 'user', content: text };
    if (!isRetry) {
      setMessages(prev => [...prev, userMsg]);
    }

    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const result = await streamOnce(sid, text);
      if (result === 'provider_changed' && !isRetry) {
        setSessionId(null);
        setMessages(prev => prev.slice(0, -2));
        const newSid = await startSession();
        if (newSid) {
          await sendMessage(text, true);
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled — ignore.
      } else {
        setError('Connection to AI service lost.');
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [sessionId, startSession, streamOnce]);

  const refreshContext = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.post('/api/ai/chat/refresh', { sessionId });
      setContextSummary(res.data.contextSummary);
    } catch {
      setError('Failed to refresh context.');
    }
  }, [sessionId]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clearChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setError(null);
    setContextSummary('');
  }, []);

  return {
    messages,
    isStreaming,
    error,
    status,
    contextSummary,
    sendMessage,
    refreshContext,
    stopStreaming,
    clearChat,
    checkStatus,
  };
}
