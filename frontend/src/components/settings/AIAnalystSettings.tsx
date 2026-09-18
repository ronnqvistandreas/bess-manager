import React, { useState } from 'react';
import { SectionCard, toggle } from './FormHelpers';
import api from '../../lib/api';

export interface AIAnalystProviderForm {
  apiKey: string;
  model: string;
  thinkingLevel?: 'low' | 'high';
}

export interface AIAnalystForm {
  provider: 'anthropic' | 'google';
  enabled: boolean;
  anthropic: AIAnalystProviderForm;
  google: AIAnalystProviderForm;
}

export const EMPTY_AI_ANALYST_FORM: AIAnalystForm = {
  provider: 'anthropic',
  enabled: true,
  anthropic: {
    apiKey: '',
    model: 'claude-sonnet-4-20250514',
  },
  google: {
    apiKey: '',
    model: 'gemini-3.8-flash',
    thinkingLevel: 'low',
  },
};

interface Props {
  form: AIAnalystForm;
  onChange: (f: AIAnalystForm) => void;
}

export function AIAnalystSettings({ form, onChange }: Props) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post('/api/ai/chat/test', form);
      setTestResult({ ok: res.data.ok, message: res.data.message });
    } catch {
      setTestResult({ ok: false, message: 'Could not reach backend.' });
    } finally {
      setTesting(false);
    }
  };

  const providerLabel = form.provider === 'google' ? 'Google Gemini' : 'Claude';

  return (
    <div className="space-y-3">
      <SectionCard
        title="AI Analyst"
        description="Connect to Claude or Google Gemini for in-app battery analysis. API keys are stored locally on your Home Assistant instance and never sent to the browser."
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Active Provider</span>
            <select
              value={form.provider}
              onChange={e => onChange({ ...form, provider: e.target.value as AIAnalystForm['provider'] })}
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="anthropic">Claude (Anthropic)</option>
              <option value="google">Google Gemini</option>
            </select>
          </label>

          {toggle('Enable AI Analyst', form.enabled, v => onChange({ ...form, enabled: v }))}
        </div>
      </SectionCard>

      <SectionCard
        title="Claude API"
        description="Anthropic Claude models for fast or deep analysis."
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">API Key</span>
            <input
              type="password"
              value={form.anthropic.apiKey}
              onChange={e => onChange({ ...form, anthropic: { ...form.anthropic, apiKey: e.target.value } })}
              placeholder="sk-ant-..."
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Get your key at <span className="font-mono">console.anthropic.com</span>
            </p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Model</span>
            <select
              value={form.anthropic.model}
              onChange={e => onChange({ ...form, anthropic: { ...form.anthropic, model: e.target.value } })}
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="claude-sonnet-4-20250514">Claude Sonnet 4 (fast, recommended)</option>
              <option value="claude-opus-4-20250514">Claude Opus 4 (deeper analysis, slower)</option>
            </select>
          </label>
        </div>
      </SectionCard>

      <SectionCard
        title="Google Gemini API"
        description="Google Gemini models with configurable thinking depth."
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">API Key</span>
            <input
              type="password"
              value={form.google.apiKey}
              onChange={e => onChange({ ...form, google: { ...form.google, apiKey: e.target.value } })}
              placeholder="AIza..."
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Get your key at <span className="font-mono">aistudio.google.com</span>
            </p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Thinking Level</span>
            <select
              value={form.google.thinkingLevel ?? 'low'}
              onChange={e => onChange({
                ...form,
                google: {
                  ...form.google,
                  model: 'gemini-3.8-flash',
                  thinkingLevel: e.target.value as 'low' | 'high',
                },
              })}
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="low">Fast (low thinking, recommended)</option>
              <option value="high">Deeper analysis (high thinking)</option>
            </select>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Both options use <span className="font-mono">gemini-3.8-flash</span>
            </p>
          </label>
        </div>
      </SectionCard>

      <div className="flex items-center gap-3 px-1">
        <button
          onClick={testConnection}
          disabled={testing}
          className="px-4 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-xs disabled:opacity-40 flex items-center gap-1.5"
        >
          {testing
            ? <div className="h-3 w-3 border-2 border-gray-500 rounded-full border-t-transparent animate-spin" />
            : null}
          <span>Test Connection ({providerLabel})</span>
        </button>
        {testResult && (
          <span className={`text-xs flex items-center gap-1 ${testResult.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            <span className={`inline-block h-2 w-2 rounded-full ${testResult.ok ? 'bg-green-500' : 'bg-red-500'}`} />
            {testResult.message}
          </span>
        )}
      </div>
    </div>
  );
}
