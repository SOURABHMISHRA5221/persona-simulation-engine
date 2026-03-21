import React from 'react';
import Hero from './components/Hero';
import VotingGraph from './components/VotingGraph';
import Features from './components/Features';
import Architecture from './components/Architecture';
import CallToAction from './components/CallToAction';

import Demo from './components/Demo';

// Simple hash router hook
function useHash() {
  const [hash, setHash] = React.useState(() => window.location.hash);
  React.useEffect(() => {
    const onHashChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const isDemo = hash === '#demo';

  return (
    <div className="App">
      <header className="container" style={{ padding: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '3rem', alignItems: 'center' }}>
          <a href="#" style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem', letterSpacing: '0.05em', color: 'var(--text-main)', textTransform: 'uppercase', textDecoration: 'none' }}>
            Persona Simulation Engine
          </a>
          <nav style={{ display: 'flex', gap: '2rem' }}>
            <a href="https://github.com/SOURABHMISHRA5221/persona-simulation-engine" target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600, textDecoration: 'none' }}>GitHub</a>
            <a href="#" style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600, textDecoration: 'none' }}>Documentation</a>
          </nav>
        </div>
        <div>
          {isDemo ? (
            <a href="#" className="btn-secondary" style={{ padding: '0.6rem 1.5rem', fontWeight: 600, fontSize: '0.95rem', background: 'transparent', color: 'var(--text-main)', textDecoration: 'none' }}>Back to Home</a>
          ) : (
            <a href="#demo" className="btn-primary" style={{ padding: '0.6rem 1.5rem', fontWeight: 600, fontSize: '0.95rem', textDecoration: 'none', display: 'inline-block' }}>View Demo</a>
          )}
        </div>
      </header>
      
      <main>
        {isDemo ? (
          <Demo />
        ) : (
          <>
            <Hero />
            <Architecture />
            <Features />
            <CallToAction />
          </>
        )}
      </main>
      
      <footer className="container" style={{ padding: '6rem 2rem 4rem', borderTop: 'none' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '2rem' }}>
          <div>
            <div style={{ color: 'var(--primary)', fontWeight: 700, fontSize: '1.05rem', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>PERSONA</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', letterSpacing: '0.05em', textTransform: 'uppercase' }}>© 2024 KINETIC ETHER SIMULATION ENGINE.</div>
          </div>
          <div style={{ display: 'flex', gap: '2.5rem', flexWrap: 'wrap' }}>
            {['PRIVACY POLICY', 'TERMS OF SERVICE', 'STATUS', 'CONTACT'].map(link => (
              <a href="#" key={link} style={{ color: 'var(--text-muted)', fontSize: '0.75rem', letterSpacing: '0.05em', textTransform: 'uppercase', fontWeight: 600 }}>{link}</a>
            ))}
          </div>
        </div>
        <div style={{ textAlign: 'center', marginTop: '6rem', color: '#444', fontSize: '0.65rem', letterSpacing: '0.25em', textTransform: 'uppercase', fontFamily: 'var(--font-display)' }}>
          BUILT FOR THE NEON ARCHITECT.
        </div>
      </footer>
    </div>
  );
}
