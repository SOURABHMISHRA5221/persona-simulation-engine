import React from 'react';

export default function Features() {
  return (
    <section className="section container" style={{ padding: '6rem 2rem' }}>
      <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
        <p style={{ color: '#8ff5ff', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '1rem' }}>
          Core Engine Capabilities
        </p>
        <h2 style={{ fontSize: '3rem', color: 'var(--text-main)', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Built for Enterprise Scale
        </h2>
      </div>

      <div className="features-grid">
        {/* Card 1 */}
        <div className="card-1 glass-panel" style={{ padding: '3rem', position: 'relative', overflow: 'hidden', background: 'var(--surface-container-high, #18181A)' }}>
          <div style={{ color: '#4ade80', fontSize: '0.75rem', fontWeight: 'bold', letterSpacing: '0.05em', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4ade80' }} />
            REAL-TIME PROCESSING
          </div>
          <h3 style={{ fontSize: '2rem', marginBottom: '1.5rem', color: 'var(--text-main)', position: 'relative', zIndex: 1, fontWeight: 700 }}>Local LLM Support</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '420px', marginBottom: '2.5rem', position: 'relative', zIndex: 1, lineHeight: '1.6', fontSize: '1.05rem' }}>
            Run high-concurrency simulations using Ollama or Gemini 1.5 Pro local integrations. Keep your sensitive user graph data on-premise while maintaining sub-second agent reasoning.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
            {['Ollama', 'Llama 3.1', 'Gemma'].map(tag => (
              <div key={tag} style={{ background: '#222224', padding: '0.4rem 0.75rem', borderRadius: '4px', fontSize: '0.8rem', fontFamily: 'monospace', color: '#ccc' }}>{tag}</div>
            ))}
          </div>
          <div style={{ position: 'absolute', right: '-5%', top: '50%', transform: 'translateY(-50%)', opacity: 0.05, zIndex: 0 }}>
             <svg width="300" height="300" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
          </div>
        </div>

        {/* Card 2 */}
        <div className="card-2 glass-panel" style={{ padding: '3rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', background: 'var(--surface-container-high, #18181A)' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '16px', background: '#241a33', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '2rem', border: '1px solid #3d2a5a' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ac89ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          </div>
          <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: 'var(--text-main)', position: 'relative', zIndex: 1, fontWeight: 700 }}>Custom Action Sets</h3>
          <p style={{ color: 'var(--text-muted)', lineHeight: '1.6', fontSize: '0.95rem' }}>
            Define custom reactions tailored to your domain—from "Churn Risk" to "Feature Adoption" or "Community Sentiment".
          </p>
        </div>

        {/* Card 3 */}
        <div className="card-3 glass-panel" style={{ padding: '3rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', background: 'var(--surface-container-high, #18181A)' }}>
          <div>
            <h3 style={{ fontSize: '1.5rem', marginBottom: '2.5rem', color: 'var(--text-main)', fontWeight: 700 }}>Stochastic Hourly Activity</h3>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '100px', marginBottom: '2.5rem' }}>
              {[30, 50, 25, 80, 45, 15].map((h, i) => (
                 <div key={i} style={{ flex: 1, background: '#60a5fa', height: `${h}%`, opacity: 0.8, borderRadius: '2px 2px 0 0' }} />
              ))}
            </div>
          </div>
          <p style={{ color: 'var(--text-muted)', lineHeight: '1.6', fontSize: '0.95rem', margin: 0 }}>
            Mimics real-world time-based engagement patterns including peak traffic surges and off-hour maintenance behaviors.
          </p>
        </div>

        {/* Card 4 */}
        <div className="card-4 glass-panel" style={{ padding: '3rem', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', background: 'var(--surface-container-high, #18181A)' }}>
          <div style={{ position: 'relative', zIndex: 1, maxWidth: '280px' }}>
            <h3 style={{ fontSize: '1.8rem', marginBottom: '1rem', color: 'var(--text-main)', lineHeight: 1.2, fontWeight: 700 }}>Simulate 1M+<br/>Interactions</h3>
            <p style={{ color: 'var(--text-muted)', lineHeight: '1.6', fontSize: '0.95rem' }}>
              Our engine scales horizontally to handle millions of simultaneous agent cycles without data drift.
            </p>
          </div>
          <div style={{ position: 'absolute', right: '-10%', top: '50%', transform: 'translateY(-50%)', zIndex: 0, whiteSpace: 'nowrap' }}>
            <div style={{ fontSize: '8rem', fontFamily: 'var(--font-display)', fontWeight: 700, WebkitTextStroke: '2px rgba(255,255,255,0.06)', color: 'transparent', letterSpacing: '-0.05em' }}>
              1,000,000+
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
