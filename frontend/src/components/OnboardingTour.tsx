import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

// ─── Tour Step Definitions ───────────────────────────────────────────────

export interface TourStep {
  target: string | null // data-onboard attribute value, null = no target (welcome/end)
  title: string
  body: string
}

export const TOUR_STEPS: TourStep[] = [
  {
    target: null,
    title: 'Welkom bij Rippled!',
    body: 'We begeleiden je in 5 stappen door je persoonlijke commitment intelligence dashboard. Klik op \'Volgende\' om te beginnen.',
  },
  {
    target: 'active-tab',
    title: 'Actieve Commitments',
    body: 'Hier zie je de meest urgente commitments die nu je aandacht nodig hebben, gebaseerd op deadline en context.',
  },
  {
    target: 'commitments-tab',
    title: 'Alle Commitments',
    body: 'Een compleet overzicht van al je gedetecteerde commitments. Filter en sorteer om snel te vinden wat je zoekt.',
  },
  {
    target: 'detail-panel-area',
    title: 'Commitment Details & Acties',
    body: 'Selecteer een commitment om de details te zien, de bron te bekijken, en acties uit te voeren zoals Bevestigen, Afwijzen, of Archiveren.',
  },
  {
    target: 'action-buttons',
    title: 'Jouw Feedback is Cruciaal',
    body: 'Help de AI slimmer te worden door aan te geven welke commitments correct zijn (Bevestigen) of onjuist/niet-relevant (Afwijzen). Dit verbetert de detectie voor iedereen.',
  },
  {
    target: 'settings-button',
    title: 'Jouw Geconnecteerde Bronnen',
    body: 'Beheer hier je verbindingen met e-mail, Slack, en Read.ai. Voeg nieuwe bronnen toe of update bestaande instellingen.',
  },
  {
    target: null,
    title: 'Klaar om te Beginnen?',
    body: 'Je bent nu klaar om Rippled te gebruiken! We zijn benieuwd naar je feedback.',
  },
]

// ─── Spotlight Positioning ───────────────────────────────────────────────

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

function getTargetRect(target: string): Rect | null {
  const el = document.querySelector(`[data-onboard="${target}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { top: r.top, left: r.left, width: r.width, height: r.height }
}

type InfoboxPosition = 'bottom' | 'top' | 'left' | 'right'

function computeInfoboxPosition(rect: Rect): InfoboxPosition {
  const spaceBelow = window.innerHeight - (rect.top + rect.height)
  const spaceAbove = rect.top
  const spaceRight = window.innerWidth - (rect.left + rect.width)
  const spaceLeft = rect.left

  // Prefer bottom, then top, then right, then left
  if (spaceBelow >= 200) return 'bottom'
  if (spaceAbove >= 200) return 'top'
  if (spaceRight >= 320) return 'right'
  if (spaceLeft >= 320) return 'left'
  return 'bottom'
}

function infoboxStyle(rect: Rect, position: InfoboxPosition): React.CSSProperties {
  const pad = 12
  switch (position) {
    case 'bottom':
      return {
        top: rect.top + rect.height + pad,
        left: Math.max(16, Math.min(rect.left, window.innerWidth - 340)),
      }
    case 'top':
      return {
        bottom: window.innerHeight - rect.top + pad,
        left: Math.max(16, Math.min(rect.left, window.innerWidth - 340)),
      }
    case 'right':
      return {
        top: rect.top,
        left: rect.left + rect.width + pad,
      }
    case 'left':
      return {
        top: rect.top,
        right: window.innerWidth - rect.left + pad,
      }
  }
}

// ─── Component ───────────────────────────────────────────────────────────

export default function OnboardingTour() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [currentStep, setCurrentStep] = useState(0)
  const [active, setActive] = useState(false)
  const [targetRect, setTargetRect] = useState<Rect | null>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Activate tour when ?onboard=true
  useEffect(() => {
    if (searchParams.get('onboard') === 'true') {
      setActive(true)
      setCurrentStep(0)
    }
  }, [searchParams])

  // Update target rect on step change and window resize
  const updateRect = useCallback(() => {
    const step = TOUR_STEPS[currentStep]
    if (step?.target) {
      setTargetRect(getTargetRect(step.target))
    } else {
      setTargetRect(null)
    }
  }, [currentStep])

  useEffect(() => {
    if (!active) return
    updateRect()
    window.addEventListener('resize', updateRect)
    window.addEventListener('scroll', updateRect, true)
    return () => {
      window.removeEventListener('resize', updateRect)
      window.removeEventListener('scroll', updateRect, true)
    }
  }, [active, updateRect])

  const closeTour = useCallback(() => {
    setActive(false)
    // Remove onboard param from URL
    const next = new URLSearchParams(searchParams)
    next.delete('onboard')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const nextStep = useCallback(() => {
    if (currentStep >= TOUR_STEPS.length - 1) {
      closeTour()
    } else {
      setCurrentStep(currentStep + 1)
    }
  }, [currentStep, closeTour])

  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }, [currentStep])

  if (!active) return null

  const step = TOUR_STEPS[currentStep]
  const isWelcome = currentStep === 0
  const isEnd = currentStep === TOUR_STEPS.length - 1
  const hasTarget = step.target !== null && targetRect !== null
  const position = hasTarget ? computeInfoboxPosition(targetRect!) : 'bottom'

  // Spotlight cutout dimensions (with padding)
  const spotPad = 8
  const spot = hasTarget
    ? {
        top: targetRect!.top - spotPad,
        left: targetRect!.left - spotPad,
        width: targetRect!.width + spotPad * 2,
        height: targetRect!.height + spotPad * 2,
      }
    : null

  return (
    <div ref={overlayRef} className="fixed inset-0 z-[9999]" data-testid="onboarding-tour">
      {/* Overlay with spotlight cutout using CSS clip-path */}
      <div
        className="absolute inset-0 bg-black/50 transition-all duration-300"
        style={
          spot
            ? {
                clipPath: `polygon(
                  0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%,
                  ${spot.left}px ${spot.top}px,
                  ${spot.left}px ${spot.top + spot.height}px,
                  ${spot.left + spot.width}px ${spot.top + spot.height}px,
                  ${spot.left + spot.width}px ${spot.top}px,
                  ${spot.left}px ${spot.top}px
                )`,
              }
            : undefined
        }
        onClick={closeTour}
      />

      {/* Spotlight highlight border */}
      {spot && (
        <div
          className="absolute rounded-lg border-2 border-white/80 pointer-events-none transition-all duration-300"
          style={{
            top: spot.top,
            left: spot.left,
            width: spot.width,
            height: spot.height,
          }}
        />
      )}

      {/* Infobox */}
      <div
        className="absolute bg-white rounded-xl shadow-2xl p-5 w-[320px] max-w-[calc(100vw-32px)] transition-all duration-300"
        style={
          hasTarget
            ? infoboxStyle(targetRect!, position)
            : {
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
              }
        }
        data-testid="onboarding-infobox"
      >
        {/* Step indicator */}
        <div className="flex items-center gap-1 mb-3">
          {TOUR_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 rounded-full transition-all duration-200 ${
                i === currentStep
                  ? 'w-4 bg-[#191919]'
                  : i < currentStep
                  ? 'w-2 bg-[#191919]/40'
                  : 'w-2 bg-[#e8e8e6]'
              }`}
            />
          ))}
        </div>

        <h3 className="text-[15px] font-semibold text-[#191919] mb-1.5">{step.title}</h3>
        <p className="text-[13px] text-[#6b7280] leading-relaxed mb-4">{step.body}</p>

        <div className="flex items-center justify-between">
          <button
            onClick={closeTour}
            className="text-[12px] text-[#9ca3af] hover:text-[#191919] transition-colors"
          >
            Sluiten
          </button>
          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={prevStep}
                className="text-[12px] text-[#6b7280] hover:text-[#191919] px-3 py-1.5 rounded-md border border-[#e8e8e6] hover:border-[#d1d1cf] transition-colors"
              >
                Vorige
              </button>
            )}
            <button
              onClick={nextStep}
              className="bg-[#191919] text-white text-[12px] px-4 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors"
            >
              {isEnd ? 'Afronden' : 'Volgende'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
