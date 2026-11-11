import React, { useState } from 'react';
import { SectionCard, toggle } from './FormHelpers';
import api from '../../lib/api';

export interface AIAnalystProviderForm {
  apiKey: string;
  model: string;
  thinkingLevel?: 'low' | 'high';
}

export interface CopilotModelOption {
  id: string;
  name: string;
  billingMultiplier: number | null;
  contextWindowTokens: number | null;
  reasoningEfforts: string[];
  defaultReasoningEffort: string | null;
}

export interface AIAnalystForm {
  provider: 'anthropic' | 'google' | 'copilot';
  enabled: boolean;
  anthropic: AIAnalystProviderForm;
  google: AIAnalystProviderForm;
  copilot: {
    githubToken: string;
    model: string;
    reasoningEffort: string;
  };
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
  copilot: {
    githubToken: '',
    model: 'auto',
    reasoningEffort: 'low',
  },
};

interface Props {
  form: AIAnalystForm;
  onChange: (f: AIAnalystForm) => void;
}

export function AIAnalystSettings({ form, onChange }: Props) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [copilotModels, setCopilotModels] = useState<CopilotModelOption[]>([]);

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post('/api/ai/chat/test', form);
      setTestResult({ ok: res.data.ok, message: res.data.message });
      if (form.provider === 'copilot' && res.data.ok && res.data.models) {
        const models = res.data.models as CopilotModelOption[];
        setCopilotModels(models);
        const selected = form.copilot.model;
        const model = models.find(option => option.id === selected);
        const defaultModel = selected === 'auto' ? res.data.defaultModel : selected;
        const chosen = models.find(option => option.id === defaultModel);
        onChange({
          ...form,
          copilot: {
            ...form.copilot,
            model: defaultModel,
            reasoningEffort: model?.reasoningEfforts.includes(form.copilot.reasoningEffort)
              ? form.copilot.reasoningEffort
              : chosen?.defaultReasoningEffort ?? 'low',
          },
        });
      }
    } catch {
      setTestResult({ ok: false, message: 'Could not reach backend.' });
    } finally {
      setTesting(false);
    }
  };

  const providerLabel = form.provider === 'google'
    ? 'Google Gemini'
    : form.provider === 'copilot' ? 'GitHub Copilot' : 'Claude';
  const selectedCopilotModel = copilotModels.find(
    model => model.id === form.copilot.model,
  );
  const reasoningEfforts = selectedCopilotModel?.reasoningEfforts ?? [];

  return (
    <div className="space-y-3">
      <SectionCard
        title="AI Analyst"
        description="Connect to Claude, Google Gemini, or GitHub Copilot for in-app battery analysis. Credentials are stored locally on your Home Assistant instance."
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
              <option value="copilot">GitHub Copilot</option>
            </select>
          </label>

          {toggle('Enable AI Analyst', form.enabled, v => onChange({ ...form, enabled: v }))}
        </div>
      </SectionCard>

      <SectionCard
        title="GitHub Copilot"
        description="Use your Copilot subscription through the official GitHub Copilot SDK."
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Fine-grained personal access token</span>
            <input
              type="password"
              value={form.copilot.githubToken}
              onChange={e => onChange({
                ...form,
                copilot: { ...form.copilot, githubToken: e.target.value },
              })}
              placeholder="github_pat_..."
              autoComplete="new-password"
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Create a fine-grained token with the <span className="font-mono">Copilot Requests</span> permission in{' '}
              <a
                href="https://github.com/settings/personal-access-tokens"
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                GitHub settings
              </a>
              . Classic <span className="font-mono">ghp_</span> tokens are not supported.
            </p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Model</span>
            <select
              value={form.copilot.model}
              onChange={e => {
                const model = copilotModels.find(option => option.id === e.target.value);
                onChange({
                  ...form,
                  copilot: {
                    ...form.copilot,
                    model: e.target.value,
                    reasoningEffort: model?.defaultReasoningEffort ?? 'low',
                  },
                });
              }}
              className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="auto">Auto (used when no zero-cost model is available)</option>
              {form.copilot.model !== 'auto' && !copilotModels.some(model => model.id === form.copilot.model) && (
                <option value={form.copilot.model}>{form.copilot.model}</option>
              )}
              {copilotModels.map(model => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.billingMultiplier === 0
                    ? '0× premium requests'
                    : model.billingMultiplier === null
                      ? 'premium request cost unavailable'
                      : `${model.billingMultiplier}× premium requests`})
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Use Test Connection to load the models available to your account. Premium-request usage depends on the selected model and your Copilot plan.
            </p>
          </label>

          {reasoningEfforts.length > 0 && (
            <label className="block">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Reasoning Effort</span>
              <select
                value={form.copilot.reasoningEffort}
                onChange={e => onChange({
                  ...form,
                  copilot: { ...form.copilot, reasoningEffort: e.target.value },
                })}
                className="mt-1 block w-full rounded-lg border bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {reasoningEfforts.map(effort => (
                  <option key={effort} value={effort}>{effort}</option>
                ))}
              </select>
            </label>
          )}
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
