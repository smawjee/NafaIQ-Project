import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

const tickerItems = [
  { sym: 'OGDC', price: '142.50', chg: '+2.3%', up: true },
  { sym: 'HBL', price: '89.40', chg: '+1.2%', up: true },
  { sym: 'LUCK', price: '890.00', chg: '-0.45%', up: false },
  { sym: 'ENGRO', price: '312.45', chg: '+1.36%', up: true },
  { sym: 'FFC', price: '168.70', chg: '+1.08%', up: true },
]

function TickerCSS() {
  return (
    <style>{`
@keyframes ticker-marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
.ticker-track {
  animation: ticker-marquee 20s linear infinite;
}
`}</style>
  )
}

interface PhoneMockupProps {
  className?: string
  startDelay?: number
}

export function PhoneMockup({ className, startDelay = 0 }: PhoneMockupProps) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let start = performance.now()
    let raf: number
    const animate = (now: number) => {
      const t = (now - start) / 1000
      const y = Math.sin(t * 0.45 * Math.PI) * 7
      el.style.transform = `translateY(${y}px) rotate(8deg)`
      raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut", delay: startDelay }}
      className={className}
      style={{ perspective: 1200 }}
    >
      <TickerCSS />
      <div
        ref={ref}
        style={{
          width: 280, height: 580, borderRadius: 44,
          background: 'linear-gradient(160deg, #24243a 0%, #1a1a2e 40%, #14142a 100%)',
          boxShadow: '0 0 50px rgba(20,184,148,0.1), 0 0 100px rgba(20,184,148,0.04), 0 30px 80px rgba(0,0,0,0.6)',
          position: 'relative', overflow: 'hidden',
          margin: '0 auto',
          border: '1px solid rgba(50,50,70,0.3)',
        }}
      >
        <div style={{
          position: 'absolute', inset: 3, borderRadius: 40,
          background: '#0d0d14', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          fontFamily: 'Inter, sans-serif', color: '#e8e8f0',
          border: '1px solid rgba(30,30,45,0.5)',
        }}>
          <div style={{
            height: 24, flexShrink: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'space-between',
            padding: '0 20px',
          }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>9:41</span>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'rgba(255,255,255,0.25)' }} />
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'rgba(255,255,255,0.4)' }} />
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#14b894' }} />
            </div>
          </div>

          <div style={{
            height: 38, flexShrink: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'space-between',
            padding: '0 16px', background: '#11111a',
          }}>
            <div style={{ color: '#14b894', fontSize: 13, fontWeight: 700, letterSpacing: -0.2 }}>NafaIQ</div>
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M8 1.5a4.5 4.5 0 0 0-4.5 4.5v2l-1 2.5h11l-1-2.5V6A4.5 4.5 0 0 0 8 1.5zM6 11.5a2 2 0 0 0 4 0"
                fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="1.2" />
            </svg>
          </div>

          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            justifyContent: 'center', padding: '16px', background: '#11111a',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>Asalam-o-Alaikum, Usman</div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>
              Wed, Jul 1 · KSE-100 <span style={{ color: '#14b894' }}>+0.62%</span>
            </div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 14 }}>Net Worth</div>
            <div style={{
              fontSize: 22, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
              color: '#fff', letterSpacing: -1, marginTop: 2,
            }}>
              PKR 5,840,000
            </div>
            <svg width="248" height="30" viewBox="0 0 248 30" style={{ marginTop: 8, display: 'block' }}>
              <defs>
                <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#14b894" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#14b894" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0 24 Q15 26 31 22 Q46 18 62 20 Q77 22 93 16 Q108 10 124 14 Q139 18 155 10 Q170 4 186 7 Q201 10 217 5 Q232 2 248 4"
                fill="none" stroke="#14b894" strokeWidth="2" strokeLinecap="round" />
              <path d="M0 24 Q15 26 31 22 Q46 18 62 20 Q77 22 93 16 Q108 10 124 14 Q139 18 155 10 Q170 4 186 7 Q201 10 217 5 Q232 2 248 4 L248 30 L0 30 Z"
                fill="url(#sg)" />
            </svg>
          </div>

          <div style={{
            margin: '0 8px', padding: '12px', flexShrink: 0,
            background: '#16161f', borderRadius: 12,
            border: '1px solid rgba(255,255,255,0.03)',
          }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Portfolio Value</div>
            <div style={{
              fontSize: 18, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
              color: '#14b894', marginTop: 4,
            }}>PKR 4.25M</div>
            <div style={{ fontSize: 11, color: '#14b894', marginTop: 2 }}>+2.4% today</div>
          </div>

          <div style={{ display: 'flex', gap: 8, padding: '8px 8px 0', flexShrink: 0 }}>
            <div style={{
              flex: 1, padding: '10px 12px',
              background: '#16161f', borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.03)',
            }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>Spending</div>
              <div style={{
                fontSize: 15, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                color: '#fff', marginTop: 4,
              }}>PKR 185K</div>
              <div style={{ fontSize: 11, color: '#ef4444', marginTop: 2 }}>-8.2%</div>
            </div>
            <div style={{
              flex: 1, padding: '10px 12px',
              background: '#16161f', borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.03)',
            }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>P&L</div>
              <div style={{
                fontSize: 15, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                color: '#14b894', marginTop: 4,
              }}>+PKR 28.4K</div>
              <div style={{ fontSize: 11, color: '#14b894', marginTop: 2 }}>+0.68%</div>
            </div>
          </div>

          <div style={{ padding: '8px 16px', flexShrink: 0 }}>
            {[
              { sym: 'OGDC', price: '142.50', chg: '+2.3%', up: true },
              { sym: 'HBL', price: '142.50', chg: '+1.2%', up: true },
              { sym: 'LUCK', price: '890.00', chg: '-0.45%', up: false },
            ].map((item, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '5px 0',
                borderTop: i > 0 ? '1px solid rgba(255,255,255,0.04)' : 'none',
              }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#fff' }}>{item.sym}</span>
                <span style={{
                  fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
                  color: item.up ? '#14b894' : '#ef4444',
                }}>
                  {item.price} {item.chg}
                </span>
              </div>
            ))}
          </div>

          <div style={{
            height: 28, flexShrink: 0, overflow: 'hidden',
            background: '#08080c', display: 'flex', alignItems: 'center',
            borderTop: '1px solid rgba(42,42,58,0.3)',
          }}>
            <div className="ticker-track" style={{
              display: 'flex', gap: 24, whiteSpace: 'nowrap', width: 'max-content',
              paddingLeft: 12,
            }}>
              <div style={{ display: 'flex', gap: 24 }}>
                {tickerItems.map((item, i) => (
                  <span key={i} style={{
                    fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                    color: item.up ? '#14b894' : '#ef4444',
                  }}>
                    {item.sym} {item.price} {item.chg}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 24 }}>
                {tickerItems.map((item, i) => (
                  <span key={`d${i}`} style={{
                    fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                    color: item.up ? '#14b894' : '#ef4444',
                  }}>
                    {item.sym} {item.price} {item.chg}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{
          position: 'absolute', top: 0, left: '-30%', width: '60%', height: '100%',
          background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, transparent 50%)',
          transform: 'skewX(-20deg)', pointerEvents: 'none', borderRadius: 44,
        }} />
      </div>
    </motion.div>
  )
}
