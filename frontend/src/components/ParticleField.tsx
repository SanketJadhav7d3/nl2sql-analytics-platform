import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  baseAlpha: number
  twinklePhase: number
  twinkleSpeed: number
  layer: 0 | 1 | 2 // depth: 0 = far/dim/slow, 2 = near/bright/fast
}

const LAYER_CONFIG = [
  { speed: 0.04, radius: [0.5, 1], alpha: [0.25, 0.45] },
  { speed: 0.09, radius: [0.8, 1.6], alpha: [0.35, 0.6] },
  { speed: 0.16, radius: [1.2, 2.2], alpha: [0.5, 0.85] },
] as const

const PARTICLE_COLOR = '255, 255, 255'
const ACCENT_COLOR = '143, 155, 255' // matches --color-accent-glow, used for a small fraction of particles

function rand(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function makeParticle(width: number, height: number): Particle {
  const layer = (Math.floor(Math.random() * 3) as 0 | 1 | 2)
  const cfg = LAYER_CONFIG[layer]
  const angle = rand(0, Math.PI * 2)
  return {
    x: rand(0, width),
    y: rand(0, height),
    vx: Math.cos(angle) * cfg.speed,
    vy: Math.sin(angle) * cfg.speed * 0.6 - cfg.speed * 0.15, // gentle upward drift
    radius: rand(cfg.radius[0], cfg.radius[1]),
    baseAlpha: rand(cfg.alpha[0], cfg.alpha[1]),
    twinklePhase: rand(0, Math.PI * 2),
    twinkleSpeed: rand(0.4, 1.1),
    layer,
  }
}

export function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let width = 0
    let height = 0
    let dpr = Math.min(window.devicePixelRatio || 1, 2)
    let particles: Particle[] = []
    let mouseX = 0
    let mouseY = 0
    let targetOffsetX = 0
    let targetOffsetY = 0
    let offsetX = 0
    let offsetY = 0
    let raf = 0
    let lastTime = performance.now()

    function density() {
      // ~1 particle per 9000px^2, capped for very large screens
      return Math.min(220, Math.round((width * height) / 9000))
    }

    function resize() {
      width = window.innerWidth
      height = window.innerHeight
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas!.width = width * dpr
      canvas!.height = height * dpr
      canvas!.style.width = `${width}px`
      canvas!.style.height = `${height}px`
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)

      const target = density()
      if (particles.length < target) {
        const toAdd = target - particles.length
        for (let i = 0; i < toAdd; i++) particles.push(makeParticle(width, height))
      } else {
        particles.length = target
      }
    }

    function onMouseMove(e: MouseEvent) {
      mouseX = e.clientX
      mouseY = e.clientY
      targetOffsetX = ((mouseX / width) - 0.5) * -10
      targetOffsetY = ((mouseY / height) - 0.5) * -10
    }

    function drawStatic() {
      ctx!.clearRect(0, 0, width, height)
      for (const p of particles) {
        const color = p.layer === 2 && Math.random() < 0.12 ? ACCENT_COLOR : PARTICLE_COLOR
        ctx!.beginPath()
        ctx!.fillStyle = `rgba(${color}, ${p.baseAlpha})`
        ctx!.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
        ctx!.fill()
      }
    }

    function tick(now: number) {
      const dt = Math.min(now - lastTime, 50) / 16.67 // normalize to ~60fps steps
      lastTime = now

      offsetX += (targetOffsetX - offsetX) * 0.02
      offsetY += (targetOffsetY - offsetY) * 0.02

      ctx!.clearRect(0, 0, width, height)

      for (const p of particles) {
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.twinklePhase += p.twinkleSpeed * 0.02 * dt

        if (p.x < -10) p.x = width + 10
        if (p.x > width + 10) p.x = -10
        if (p.y < -10) p.y = height + 10
        if (p.y > height + 10) p.y = -10

        const twinkle = 0.75 + 0.25 * Math.sin(p.twinklePhase)
        const alpha = p.baseAlpha * twinkle
        const isAccent = p.layer === 2 && ((p.twinklePhase * 10) % 20 < 1)
        const color = isAccent ? ACCENT_COLOR : PARTICLE_COLOR
        const px = p.x + offsetX * (p.layer + 1) * 0.4
        const py = p.y + offsetY * (p.layer + 1) * 0.4

        ctx!.beginPath()
        ctx!.fillStyle = `rgba(${color}, ${alpha})`
        ctx!.arc(px, py, p.radius, 0, Math.PI * 2)
        ctx!.fill()
      }

      raf = requestAnimationFrame(tick)
    }

    function start() {
      if (raf) return
      lastTime = performance.now()
      raf = requestAnimationFrame(tick)
    }
    function stop() {
      if (raf) cancelAnimationFrame(raf)
      raf = 0
    }

    resize()
    window.addEventListener('resize', resize)
    drawStatic() // paint immediately so the canvas is never blank before the first rAF tick

    if (reduceMotion) {
      // static painted above is the final state
    } else {
      window.addEventListener('mousemove', onMouseMove)
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) stop()
        else start()
      })
      start()
    }

    return () => {
      stop()
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
    }
  }, [])

  return <canvas ref={canvasRef} className="particle-canvas" aria-hidden="true" />
}
