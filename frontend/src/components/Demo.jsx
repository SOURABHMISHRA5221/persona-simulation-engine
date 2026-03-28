import React, { useState, useEffect, useRef } from 'react';

export default function Demo() {
  const [isRunning, setIsRunning] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState(0);

  // Form State
  const [campaign, setCampaign] = useState("Should we add a dark mode?");
  const [actionSet, setActionSet] = useState("Vote (Standard approval)");
  const [agents, setAgents] = useState(5);
  const [hours, setHours] = useState(24);

  const [executiveSummary, setExecutiveSummary] = useState("");

  // Ingest panel state
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestLogs, setIngestLogs] = useState([]);
  const [ingestDone, setIngestDone] = useState(false);
  const [ingestProgress, setIngestProgress] = useState(0);
  const ingestSourceRef = useRef(null);
  const ingestLogsEndRef = useRef(null);

  const logsEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Track accumulated summary so we don't depend on stale closure in onmessage
  const summaryAccumulator = useRef("");

  const handleIngest = () => {
    if (ingestSourceRef.current) ingestSourceRef.current.close();
    setIsIngesting(true);
    setIngestDone(false);
    setIngestLogs([]);
    setIngestProgress(0);

    const sse = new EventSource('/api/ingest-demo');
    ingestSourceRef.current = sse;

    sse.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.done) {
        sse.close();
        setIsIngesting(false);
        setIngestDone(true);
        setIngestProgress(100);
        return;
      }
      if (data.ingested && data.total) {
        setIngestProgress(Math.round((data.ingested / data.total) * 90));
      }
      setIngestLogs(prev => [...prev, { text: data.text, error: data.error || false }]);
    };

    sse.onerror = () => {
      sse.close();
      setIsIngesting(false);
      setIngestLogs(prev => [...prev, { text: 'Connection lost — check that graphiti_service is running on :8000.', error: true }]);
    };
  };

  useEffect(() => {
    ingestLogsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [ingestLogs]);

  const handleStart = () => {
    if (eventSourceRef.current) eventSourceRef.current.close();
    
    setIsRunning(true);
    setShowResults(false);
    setLogs([]);
    setProgress(5);
    setExecutiveSummary("");
    summaryAccumulator.current = "";
    
    // Connect to SSE API
    const url = new URL('/api/simulate', window.location.origin);
    url.searchParams.append('campaign', campaign);
    url.searchParams.append('agents', agents);
    url.searchParams.append('hours', hours);
    url.searchParams.append('action_set', actionSet);
    
    const sse = new EventSource(url);
    eventSourceRef.current = sse;
    
    let isSummarizing = false;
    
    sse.onmessage = (e) => {
       const data = JSON.parse(e.data);
       if (data.done) {
          sse.close();
          setIsRunning(false);
          setShowResults(true);
          setProgress(100);
          setExecutiveSummary(summaryAccumulator.current);
          return;
       }
       
       const rawText = data.text;
       
       // Handle streaming the Executive Summary text
       if (isSummarizing) {
           if (!rawText.startsWith("=")) {
               summaryAccumulator.current += " " + rawText;
           }
           return;
       }
       
       if (rawText.includes("AI EXECUTIVE SUMMARY")) {
           isSummarizing = true;
           setLogs(prev => [...prev, { type: 'system', text: 'Generating AI Executive Summary...' }]);
           return;
       }

       setLogs(prev => {
           const lines = [...prev];
           const lastIdx = Object.hasOwn(lines, lines.length - 1) ? lines.length - 1 : null;
           
           // Agent Name match: [username | Role | tier]
           if (rawText.startsWith('[') && rawText.includes('|')) {
               lines.push({ type: 'agent_pending', name: rawText, action: '', text: '' });
               return lines;
           }
           
           if (lastIdx !== null && lines[lastIdx].type === 'agent_pending') {
               if (rawText.startsWith('Action:')) {
                   lines[lastIdx].action = rawText.replace('Action:', '').trim().replace(/[^a-zA-Z]/g, '');
                   return lines;
               }
           }
           
           if (lastIdx !== null && lines[lastIdx].type === 'agent_pending' && lines[lastIdx].action !== '') {
               // Append extra lines correctly
               lines[lastIdx].text += (lines[lastIdx].text ? " " : "") + rawText;
               // Wait! Is it finished? The engine quotes the text. We will assume it's one block.
               // Let's just switch the type so the UI renders it
               lines[lastIdx].type = 'agent';
               return lines;
           }
           
           if (lastIdx !== null && lines[lastIdx].type === 'agent') {
               // In case agent text is multiple lines
               // If it's a new system line, we stop appending. 
               // main.py emits blank lines between agents usually, but we stripped them in SSE
               if (!rawText.startsWith('BREAKDOWN') && !rawText.startsWith('=')) {
                   lines[lastIdx].text += " " + rawText;
                   return lines;
               }
           }
           
           // Generic
           lines.push({ type: 'system', text: rawText });
           
           // Faux progress increment
           setProgress(p => Math.min(95, p + 2));
           
           return lines;
       });
    };
    
    sse.onerror = (err) => {
       console.error("SSE Error:", err);
       sse.close();
       setIsRunning(false);
       setLogs(prev => [...prev, { type: 'system', text: 'Error: Connection lost or simulation crashed.' }]);
    };
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    }
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="container" style={{ padding: '2rem 2rem 6rem' }}>
      <div style={{ marginBottom: '4rem' }}>
        <h1 style={{ fontSize: '3rem', color: 'var(--text-main)', letterSpacing: '-0.02em', marginBottom: '0.5rem', fontWeight: 700 }}>Interactive Sandbox</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.25rem' }}>Configure parameters and watch the engine synthesize real responses live.</p>
      </div>

      {/* ── Step 1: Ingest Demo Data ── */}
      <div style={{ marginBottom: '3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--primary)', color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.9rem', flexShrink: 0 }}>1</div>
          <div>
            <h3 style={{ margin: 0, color: 'var(--text-main)', fontWeight: 600 }}>Seed the Knowledge Graph</h3>
            <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.95rem' }}>Ingest 5 diverse demo users (20 events) into the graph so the simulation runs on real behavioral personas.</p>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '2rem', background: 'var(--surface-container-high, #18181A)' }}>
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {/* User cards */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', flex: 1 }}>
              {[
                { id: 'demo_alex',  role: 'Software Engineer', loc: 'San Francisco', tier: 'premium', color: '#4ade80' },
                { id: 'demo_yuki',  role: 'Product Manager',   loc: 'Tokyo',         tier: 'premium', color: '#4ade80' },
                { id: 'demo_marco', role: 'Small Biz Owner',   loc: 'London',        tier: 'basic',   color: '#facc15' },
                { id: 'demo_priya', role: 'Student',           loc: 'Austin',        tier: 'free',    color: '#9ca3af' },
                { id: 'demo_clara', role: 'Teacher',           loc: 'Chicago',       tier: 'free',    color: '#9ca3af' },
              ].map(u => (
                <div key={u.id} style={{ background: '#121214', border: '1px solid #333', borderRadius: '8px', padding: '0.75rem 1rem', minWidth: 130 }}>
                  <div style={{ color: u.color, fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.2rem' }}>{u.tier.toUpperCase()}</div>
                  <div style={{ color: 'var(--text-main)', fontSize: '0.85rem', fontWeight: 600 }}>{u.role}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{u.loc}</div>
                </div>
              ))}
            </div>

            {/* Button */}
            <button
              onClick={handleIngest}
              disabled={isIngesting}
              style={{
                padding: '0.9rem 2rem', fontSize: '1rem', fontWeight: 700,
                background: ingestDone ? '#1a3a1a' : isIngesting ? 'var(--surface-highest)' : 'var(--primary)',
                color: ingestDone ? '#4ade80' : isIngesting ? 'var(--text-muted)' : '#000',
                border: ingestDone ? '1px solid #4ade80' : 'none',
                borderRadius: '8px', cursor: isIngesting ? 'not-allowed' : 'pointer',
                boxShadow: (!isIngesting && !ingestDone) ? '0 0 20px rgba(143,245,255,0.3)' : 'none',
                transition: 'all 0.3s ease', whiteSpace: 'nowrap', alignSelf: 'center',
              }}
            >
              {ingestDone ? '✓ Data Seeded' : isIngesting ? `Ingesting... ${ingestProgress}%` : 'Ingest Demo Data'}
            </button>
          </div>

          {/* Ingest log */}
          {ingestLogs.length > 0 && (
            <div style={{ marginTop: '1.5rem', background: '#0d0d0f', border: '1px solid #2a2a2c', borderRadius: '8px', padding: '1rem', maxHeight: '180px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.82rem' }}>
              {ingestLogs.map((log, i) => (
                <div key={i} style={{ color: log.error ? '#ff716c' : log.text.startsWith('  ✓') ? '#4ade80' : '#aaa', lineHeight: '1.7' }}>
                  {log.text}
                </div>
              ))}
              <div ref={ingestLogsEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* ── Step 2: Run Simulation ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--primary)', color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.9rem', flexShrink: 0 }}>2</div>
        <div>
          <h3 style={{ margin: 0, color: 'var(--text-main)', fontWeight: 600 }}>Run the Simulation</h3>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.95rem' }}>Choose a campaign and watch your digital twins vote in real time.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
        {/* Left Column: Configuration */}
        <div className="glass-panel" style={{ padding: '2.5rem', height: 'fit-content', background: 'var(--surface-container-high, #18181A)' }}>
           <h3 style={{ fontSize: '1.5rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-ghost)', paddingBottom: '1rem', color: 'var(--text-main)', fontWeight: 600 }}>Configuration</h3>
           
           <div style={{ marginBottom: '2rem' }}>
             <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Proposed Campaign</label>
             <input type="text" value={campaign} onChange={e => setCampaign(e.target.value)} style={{ width: '100%', padding: '1rem', background: 'var(--bg-color)', border: '1px solid var(--border-ghost)', color: 'var(--text-main)', borderRadius: '8px', fontSize: '1rem', outline: 'none', transition: 'border 0.2s' }} />
           </div>

           <div style={{ marginBottom: '2rem' }}>
             <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Action Set</label>
             <select value={actionSet} onChange={e => setActionSet(e.target.value)} style={{ width: '100%', padding: '1rem', background: 'var(--bg-color)', border: '1px solid var(--border-ghost)', color: 'var(--text-main)', borderRadius: '8px', fontSize: '1rem', outline: 'none', appearance: 'none' }}>
               <option>Vote (Standard approval)</option>
               <option>Sentiment Scale (1-10)</option>
               <option>Feature Adoption Probability</option>
             </select>
           </div>
           
           <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '3rem' }}>
             <div>
               <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Agents</label>
               <input type="number" value={agents} onChange={e => setAgents(parseInt(e.target.value))} style={{ width: '100%', padding: '1rem', background: 'var(--bg-color)', border: '1px solid var(--border-ghost)', color: 'var(--text-main)', borderRadius: '8px', fontSize: '1rem', outline: 'none' }} />
             </div>
             <div>
               <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Hours</label>
               <input type="number" value={hours} onChange={e => setHours(parseInt(e.target.value))} style={{ width: '100%', padding: '1rem', background: 'var(--bg-color)', border: '1px solid var(--border-ghost)', color: 'var(--text-main)', borderRadius: '8px', fontSize: '1rem', outline: 'none' }} />
             </div>
           </div>

           <button 
             onClick={handleStart}
             disabled={isRunning}
             style={{ 
               width: '100%', padding: '1.2rem', fontSize: '1.15rem', fontWeight: 700, 
               background: isRunning ? 'var(--surface-highest)' : 'var(--primary)', 
               color: isRunning ? 'var(--text-muted)' : '#000', 
               border: 'none',
               borderRadius: '8px', cursor: isRunning ? 'not-allowed' : 'pointer',
               boxShadow: isRunning ? 'none' : '0 0 30px rgba(143, 245, 255, 0.4)',
               transition: 'all 0.3s ease'
             }}
           >
             {isRunning ? `Running Cloud Sim... ${progress}%` : 'Run Live Cloud Simulation'}
           </button>
        </div>

        {/* Center/Right Column: Live Feed & Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', gridColumn: 'span 2' }}>
           
           {/* Terminal Window */}
           <div className="glass-panel" style={{ padding: '0', fontFamily: 'monospace', height: '400px', background: '#121214', borderRadius: '12px', overflow: 'hidden', border: '1px solid #333', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 40px rgba(0,0,0,0.5)' }}>
             <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.5rem', background: '#1a1a1c', borderBottom: '1px solid #333' }}>
               <div style={{ display: 'flex', gap: '0.5rem' }}>
                 <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
                 <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
                 <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
               </div>
               <div style={{ color: '#666', fontSize: '0.75rem', letterSpacing: '0.1em', fontWeight: 'bold' }}>LIVE AGENT FEED</div>
             </div>
             
             <div style={{ padding: '1.5rem', fontSize: '0.9rem', lineHeight: '1.6', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column' }}>
               {logs.length === 0 && !isRunning && (
                 <div style={{ color: '#555', fontStyle: 'italic', margin: 'auto' }}>Awaiting configuration...</div>
               )}
               {logs.map((log, i) => {
                 if (!log) return null;
                 return (
                 <div key={i} style={{ marginBottom: '1rem', animation: 'fadeIn 0.3s ease' }}>
                   {log.type === 'system' && <div style={{ color: '#888' }}><span style={{ color: '#4ade80', marginRight: '8px' }}>$</span>{log.text}</div>}
                   {log.type === 'info' && <div style={{ color: 'var(--primary)', padding: '0.5rem 0', borderBottom: '1px dashed #3A3A3C', borderTop: '1px dashed #3A3A3C', margin: '1rem 0', fontWeight: 'bold' }}>{log.text}</div>}
                   {(log.type === 'agent' || log.type === 'agent_pending') && (
                     <div style={{ background: '#1C1C1E', padding: '1rem', borderRadius: '8px', borderLeft: `3px solid ${log.action === 'LIKE' ? '#4ade80' : log.action === 'DISLIKE' ? '#ff716c' : '#888'}` }}>
                       <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                         <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>{log.name}</span>
                         {log.action && <span style={{ color: log.action === 'LIKE' ? '#4ade80' : log.action === 'DISLIKE' ? '#ff716c' : '#888', fontWeight: 'bold', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px' }}>{log.action}</span>}
                       </div>
                       <div style={{ color: '#ccc', fontStyle: 'italic' }}>{log.text}</div>
                     </div>
                   )}
                 </div>
                 );
               })}
               {isRunning && (
                 <div style={{ color: '#888', fontStyle: 'italic', marginTop: '1rem' }}>
                   <span style={{ display: 'inline-block', width: '8px', height: '14px', background: 'var(--primary)', verticalAlign: 'middle', marginRight: '8px', animation: 'blink 1s step-end infinite' }}></span>
                 </div>
               )}
               <div ref={logsEndRef} style={{ height: '1px' }} />
             </div>
           </div>

           {/* Results Dashboard */}
           {showResults && (
             <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem', animation: 'fadeIn 0.5s ease' }}>
               <div className="glass-panel" style={{ padding: '2.5rem', border: '1px solid var(--primary)', position: 'relative', overflow: 'hidden', background: '#0a1a1a' }}>
                 <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '4px', background: 'var(--primary)', boxShadow: '0 0 20px var(--primary)' }} />
                 <h4 style={{ color: 'var(--primary)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '1.25rem', fontWeight: 700 }}>
                   <span style={{ fontSize: '1.5rem' }}>🤖</span> LIVE AI EXECUTIVE SUMMARY
                 </h4>
                 <p style={{ color: 'var(--text-main)', fontSize: '1.05rem', lineHeight: '1.8', marginBottom: '1.5rem' }}>
                   {executiveSummary || "No summary generated. Check engine logs."}
                 </p>
               </div>
             </div>
           )}

        </div>
      </div>
    </div>
  );
}
