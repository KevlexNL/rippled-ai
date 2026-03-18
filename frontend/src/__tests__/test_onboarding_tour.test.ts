import { describe, it, expect } from 'vitest'
import { TOUR_STEPS } from '../components/OnboardingTour'

describe('OnboardingTour steps', () => {
  it('has 7 steps as specified in the WO', () => {
    expect(TOUR_STEPS).toHaveLength(7)
  })

  it('starts with a welcome step (no target)', () => {
    expect(TOUR_STEPS[0].target).toBeNull()
    expect(TOUR_STEPS[0].title).toBe('Welkom bij Rippled!')
  })

  it('ends with a completion step (no target)', () => {
    const last = TOUR_STEPS[TOUR_STEPS.length - 1]
    expect(last.target).toBeNull()
    expect(last.title).toBe('Klaar om te Beginnen?')
  })

  it('has targeted steps for active tab, commitments tab, detail panel, actions, and settings', () => {
    const targets = TOUR_STEPS.filter(s => s.target !== null).map(s => s.target)
    expect(targets).toContain('active-tab')
    expect(targets).toContain('commitments-tab')
    expect(targets).toContain('detail-panel-area')
    expect(targets).toContain('action-buttons')
    expect(targets).toContain('settings-button')
  })

  it('every step has a non-empty title and body', () => {
    for (const step of TOUR_STEPS) {
      expect(step.title.length).toBeGreaterThan(0)
      expect(step.body.length).toBeGreaterThan(0)
    }
  })
})
