import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import type { DailySavingsRecord } from '../../types'

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      React.cloneElement(children, { width: 600, height: 300 }),
  }
})

const record: DailySavingsRecord = {
  date: '2026-10-05',
  gridOnlyCost: 50,
  solarOnlyCost: 40,
  optimizedCost: 43,
  totalSavings: 7,
  solarSavings: 10,
  batteryContribution: -3,
  predictedTotalSavings: 8,
  periodCount: 96,
  complete: true,
  finalizedAt: '2026-10-06T00:00:00',
}

vi.mock('../../hooks/useSavingsHistory', () => ({
  useSavingsHistory: () => ({
    data: { currency: 'SEK', records: [record], count: 1 },
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}))

import DailySavingsHistory from '../DailySavingsHistory'

const barRect = (container: HTMLElement, layerIndex: number) => {
  const layer = container.querySelectorAll('.recharts-bar')[layerIndex]
  const path = layer?.querySelector('.recharts-bar-rectangle path')
  if (!path) throw new Error(`no rendered bar in layer ${layerIndex}`)
  const y = Number(path.getAttribute('y'))
  const height = Number(path.getAttribute('height'))
  return { top: Math.min(y, y + height), bottom: Math.max(y, y + height) }
}

describe('DailySavingsHistory chart', () => {
  it('draws a negative battery contribution below zero instead of on top of solar', () => {
    const { container, getByText } = render(<DailySavingsHistory />)
    fireEvent.click(getByText('Daily Savings History'))

    const solar = barRect(container, 0)
    const battery = barRect(container, 1)

    expect(battery.top).toBeGreaterThanOrEqual(solar.bottom - 0.5)
  })
})
