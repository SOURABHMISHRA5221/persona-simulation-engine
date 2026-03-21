import React from 'react';

export default function CallToAction() {
  return (
    <section className="section container" style={{ display: 'flex', justifyContent: 'center', padding: '6rem 2rem' }}>
      <div className="glass-panel" style={{ 
        padding: '6rem 4rem', 
        textAlign: 'center', 
        background: 'var(--surface-container-high, #18181A)',
        borderRadius: '24px',
        width: '100%',
        maxWidth: '1000px',
        boxShadow: '0 30px 60px rgba(0,0,0,0.4)',
        border: '1px solid var(--surface-highest)'
      }}>
        <h2 style={{ fontSize: '3.5rem', marginBottom: '1.5rem', color: 'var(--text-main)', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
          Ready to make <span style={{ color: 'var(--secondary)', fontStyle: 'italic' }}>data-driven</span><br/>product decisions?
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto 3rem', lineHeight: '1.6' }}>
          Join forward-thinking product teams using simulation-first development.<br/>
          Reduce churn by 30% before you even deploy the code.
        </p>
        <div style={{ display: 'flex', gap: '2rem', justifyContent: 'center', alignItems: 'center' }}>
          <button style={{ 
            background: '#ffffff', color: '#000000', 
            padding: '1rem 2rem', fontSize: '1.1rem', 
            fontWeight: 700, borderRadius: '8px',
            fontFamily: 'var(--font-body)' 
          }}>Read the Docs</button>
          <a href="#" style={{ color: 'var(--text-main)', textDecoration: 'underline', textUnderlineOffset: '6px', fontSize: '1.05rem', fontWeight: 500 }}>Book a Demo</a>
        </div>
      </div>
    </section>
  );
}
