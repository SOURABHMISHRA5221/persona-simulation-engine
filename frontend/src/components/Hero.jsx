import React from 'react';

export default function Hero() {
  return (
    <section className="section container" style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) minmax(400px, 1fr)', gap: '4rem', alignItems: 'center', minHeight: '80vh' }}>
      <div>
        <h1 style={{ fontSize: '5rem', marginBottom: '1.5rem', letterSpacing: '-0.02em', lineHeight: 1.1, color: 'var(--text-main)' }}>
          Ship with <br/>
          <span style={{ color: 'var(--primary)', fontStyle: 'italic' }}>Confidence.</span><br/>
          Test with AI <br/>
          Personas.
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.25rem', marginBottom: '2.5rem', maxWidth: '500px' }}>
          Leverage your knowledge graph based on real User Event Activity data. Generate thousands of digital twins and simulate product decisions against them to see how changes impact your users.
        </p>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <a href="#demo" className="btn-primary" style={{ fontSize: '1.1rem', padding: '0.8rem 2rem', textDecoration: 'none', display: 'inline-block' }}>View Demo</a>
          <a href="https://github.com/SOURABHMISHRA5221/persona-simulation-engine" target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ fontSize: '1.1rem', padding: '0.8rem 2rem', background: '#1a1a1c', textDecoration: 'none', display: 'inline-block' }}>Check GitHub</a>
        </div>
      </div>
      
      <div className="glass-panel" style={{ padding: '0', fontFamily: 'monospace', minHeight: '300px', background: '#121214', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.5)', border: '1px solid #333' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: '#1a1a1c', borderBottom: '1px solid #333' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
          </div>
          <div style={{ color: '#666', fontSize: '0.75rem', letterSpacing: '0.05em' }}>SIMULATION ENGINE V4.0.2</div>
        </div>
        <div style={{ padding: '2rem 1.5rem', fontSize: '0.9rem', lineHeight: '1.8' }}>
          <div style={{ color: '#4ade80' }}><span style={{ color: '#888', marginRight: '0.5rem' }}>[14:02:11]</span> system: Initializing Knowledge Graph cluster...</div>
          <div style={{ color: '#8ff5ff', marginBottom: '1.5rem' }}><span style={{ color: '#888', marginRight: '0.5rem' }}>[14:02:12]</span> agents: 5,000 digital twins generated.</div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div><span style={{ color: '#8ff5ff' }}>maya_enterprise</span> {'->'} <span style={{ color: '#4ade80', fontWeight: 'bold' }}>LIKE</span></div>
            <div style={{ color: '#666' }}>Simulating Pricing Change...</div>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div><span style={{ color: '#8ff5ff' }}>leo_startup_founder</span> {'->'} <span style={{ color: '#ff716c', fontWeight: 'bold' }}>DISLIKE</span></div>
            <div style={{ color: '#666' }}>Friction @ Checkout +2%</div>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
            <div><span style={{ color: '#8ff5ff' }}>sarah_dev_ops</span> {'->'} <span style={{ color: '#4ade80', fontWeight: 'bold' }}>LIKE</span></div>
            <div style={{ color: '#666' }}>Feature: API-first toggle</div>
          </div>
          
          <div style={{ color: '#888', fontStyle: 'italic', display: 'flex', alignItems: 'center' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '14px', background: '#8ff5ff', marginRight: '8px', animation: 'blink 1s step-end infinite' }}></span>
            Awaiting predictive aggregate...
          </div>
        </div>
      </div>
    </section>
  );
}
