import React, { useState, useEffect } from 'react';

export default function VotingGraph() {
  const [data, setData] = useState([
    { label: 'LIKE', value: 0, color: 'var(--primary)' },
    { label: 'DISLIKE', value: 0, color: 'var(--error, #ff716c)' },
    { label: 'ABSTAIN', value: 0, color: 'var(--text-muted)' }
  ]);

  useEffect(() => {
    // Animate to target values after mount to create a filling effect
    const timer = setTimeout(() => {
      setData([
        { label: 'LIKE', value: 65, color: 'var(--primary)' },
        { label: 'DISLIKE', value: 25, color: '#ff716c' },
        { label: 'ABSTAIN', value: 10, color: 'var(--text-muted)' }
      ]);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="glass-panel" style={{ padding: '2rem', width: '100%', marginTop: '2rem', background: 'rgba(26, 25, 27, 0.4)' }}>
      <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', color: 'var(--text-main)' }}>Live Voting Sentiment Analysis</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {data.map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ width: '80px', fontWeight: 'bold', fontSize: '0.9rem', color: 'var(--text-muted)' }}>{item.label}</div>
            <div style={{ flex: 1, background: 'var(--surface-highest)', height: '12px', borderRadius: '6px', overflow: 'hidden' }}>
              <div style={{ 
                height: '100%', 
                width: `${item.value}%`, 
                background: item.color, 
                transition: 'width 2s cubic-bezier(0.22, 1, 0.36, 1)',
                boxShadow: item.value > 0 ? `0 0 10px ${item.color}` : 'none'
              }} />
            </div>
            <div style={{ width: '45px', textAlign: 'right', fontFamily: 'var(--font-display)', color: 'var(--text-main)' }}>
               {item.value}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
