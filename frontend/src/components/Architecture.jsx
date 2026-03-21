import React from 'react';

const DatabaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
);

const UserPlusIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--secondary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
);

const NetworkIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--tertiary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
);

const DocumentIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
);

export default function Architecture() {
  const steps = [
    { icon: <DatabaseIcon />, title: "User Event Data", desc: "Graphiti Knowledge Graph integration ingest raw clickstreams and turns them into behavioral nodes." },
    { icon: <UserPlusIcon />, title: "Persona Generation", desc: "Digital twins with distinct traits are synthesized from historical interaction patterns." },
    { icon: <NetworkIcon />, title: "Multi-Agent Simulation", desc: "Test proposed changes against thousands of agents simultaneously in an isolated sandbox." },
    { icon: <DocumentIcon />, title: "Actionable Decisions", desc: "AI-written executive summaries distill complex agent behaviors into clear strategic paths." }
  ];

  return (
    <section className="section container" style={{ padding: '6rem 2rem', borderBottom: '1px solid var(--border-ghost)' }}>
      <div style={{ marginBottom: '4rem' }}>
        <h2 style={{ fontSize: '2.5rem', color: 'var(--text-main)', display: 'inline-block', borderBottom: '4px solid var(--primary)', paddingBottom: '0.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          The Simulation Pipeline
        </h2>
      </div>
      
      <div style={{ 
        display: 'flex', 
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'nowrap',
        overflowX: 'auto',
        overflowY: 'hidden',
        gap: '2rem',
        paddingBottom: '2rem'
      }}>
        {steps.map((step, i) => (
           <React.Fragment key={i}>
             <div style={{ flexShrink: 0, width: '250px', display: 'flex', flexDirection: 'column' }}>
               <div style={{ 
                 width: '56px', height: '56px', 
                 borderRadius: '12px', 
                 background: 'var(--surface-container-high, #201f21)', 
                 display: 'flex', alignItems: 'center', justifyContent: 'center',
                 marginBottom: '1.5rem',
                 border: '1px solid var(--border-ghost)',
                 boxShadow: '0 4px 10px rgba(0,0,0,0.3)'
               }}>
                 {step.icon}
               </div>
               
               <h3 style={{ fontSize: '1.25rem', marginBottom: '1rem', color: 'var(--text-main)', fontWeight: 600 }}>{step.title}</h3>
               <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: '1.6' }}>{step.desc}</p>
             </div>
             
             {i < steps.length - 1 && (
               <div style={{ 
                 color: 'var(--border-ghost)', 
                 fontSize: '1.5rem',
                 marginTop: '1.2rem',
                 display: 'flex',
                 alignItems: 'center',
                 animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                 animationDelay: `${i * 0.5}s`,
                 flexShrink: 0
               }}>
                 →
               </div>
             )}
           </React.Fragment>
        ))}
      </div>
    </section>
  );
}
