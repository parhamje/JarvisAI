import { useState, useEffect, useRef } from 'react';

function App() {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState("Initializing...");
  const [mode, setMode] = useState<"dashboard" | "dev" | "hud">("dashboard");
  const [input, setInput] = useState("");

  useEffect(() => {
    const socket = new WebSocket('ws://127.0.0.1:8765');
    
    socket.onopen = () => {
      setConnected(true);
      setStatus("Gemini Live: Connected");
      setWs(socket);
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "LOG") {
          setLogs(prev => [...prev, data.payload.text].slice(-10));
        } else if (data.type === "STATUS") {
          setStatus(data.payload.text);
        } else if (data.type === "MODE") {
          setMode(data.payload.mode);
        }
      } catch (e) {
        console.error("Invalid WS message", e);
      }
    };
    
    socket.onclose = () => {
      setConnected(false);
      setStatus("Disconnected. Reconnecting...");
      setTimeout(() => setWs(null), 3000); // Trigger re-render to reconnect
    };
    
    return () => socket.close();
  }, [ws === null]);

  const sendCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !ws) return;
    ws.send(JSON.stringify({ type: "TEXT_COMMAND", payload: { text: input } }));
    setInput("");
  };

  return (
    <div className={`min-h-screen text-cyan-50 relative overflow-hidden transition-colors duration-1000 ${
      mode === 'dev' ? 'bg-slate-950/80' : 'bg-[#00040a]/80'
    }`}>
      
      {/* Background glowing effects */}
      <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full blur-[120px] opacity-20 pointer-events-none transition-colors duration-1000 ${
        mode === 'dev' ? 'bg-magenta-600' : 'bg-cyan-600'
      }`}></div>

      {/* Main Layout */}
      <div className="flex h-screen p-6 gap-6 relative z-10 font-sans">
        
        {/* Left Sidebar */}
        <div className={`w-64 rounded-2xl p-6 flex flex-col gap-4 backdrop-blur-xl border ${
          mode === 'dev' ? 'bg-slate-900/40 border-pink-500/30' : 'bg-[#000c14]/60 border-cyan-900/50'
        }`}>
          <div className="text-xl font-bold tracking-widest text-center mb-8 bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-600">
            J.A.R.V.I.S.
          </div>
          
          <nav className="flex flex-col gap-2">
            <button className="text-left px-4 py-3 rounded-lg bg-cyan-950/30 text-cyan-300 border border-cyan-800/50 hover:bg-cyan-900/50 transition-all">🎙️ Voice Live</button>
            <button className="text-left px-4 py-3 rounded-lg text-slate-400 hover:text-cyan-200 hover:bg-slate-800/50 transition-all">💻 System Control</button>
            <button className="text-left px-4 py-3 rounded-lg text-slate-400 hover:text-cyan-200 hover:bg-slate-800/50 transition-all">👁️ Vision Eye</button>
            <button className="text-left px-4 py-3 rounded-lg text-slate-400 hover:text-cyan-200 hover:bg-slate-800/50 transition-all">🌐 Web Agent</button>
            <button onClick={() => setMode(mode === 'dev' ? 'dashboard' : 'dev')} className={`text-left px-4 py-3 rounded-lg transition-all ${
              mode === 'dev' ? 'bg-pink-950/40 text-pink-400 border border-pink-500/50' : 'text-slate-400 hover:text-cyan-200 hover:bg-slate-800/50'
            }`}>🛠️ Dev Mode</button>
          </nav>
        </div>

        {/* Center Workspace */}
        <div className="flex-1 flex flex-col items-center justify-center relative">
          
          {mode === 'dev' ? (
            <div className="w-full max-w-3xl bg-slate-950/80 border border-pink-500/40 rounded-xl p-4 font-mono text-sm shadow-[0_0_30px_rgba(236,72,153,0.15)]">
               <div className="flex justify-between items-center mb-2 text-pink-400 border-b border-pink-900/50 pb-2">
                 <span>autonomous_agent.py</span>
                 <span className="animate-pulse">Active</span>
               </div>
               <div className="text-slate-300">
                 {logs.map((log, i) => (
                   <div key={i}>&gt; {log}</div>
                 ))}
               </div>
            </div>
          ) : (
            <div className="relative flex items-center justify-center">
              {/* Arc Reactor */}
              <div className="w-64 h-64 rounded-full border-4 border-cyan-800/50 flex items-center justify-center relative shadow-[0_0_50px_rgba(6,182,212,0.2)]">
                <div className="w-56 h-56 rounded-full border border-cyan-500/30 flex items-center justify-center relative">
                  <div className="w-40 h-40 rounded-full bg-cyan-950 flex items-center justify-center shadow-[inset_0_0_30px_rgba(6,182,212,0.5)]">
                     <span className="font-bold tracking-[0.2em] text-cyan-100 text-lg">JARVIS</span>
                  </div>
                  {/* Waveforms */}
                  {connected && (
                    <div className="absolute inset-0 rounded-full border-2 border-dashed border-cyan-400/50 animate-[spin_10s_linear_infinite]"></div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Chat Bar */}
          <div className="absolute bottom-10 w-full max-w-2xl">
             <form onSubmit={sendCommand} className="relative">
               <input 
                 type="text" 
                 value={input}
                 onChange={e => setInput(e.target.value)}
                 placeholder="⌨️ Type a message or command here..." 
                 className={`w-full bg-[#000e18]/80 backdrop-blur-md rounded-xl py-4 pl-6 pr-14 outline-none border transition-colors ${
                   mode === 'dev' ? 'border-pink-500/40 focus:border-pink-400 text-pink-100' : 'border-cyan-900/50 focus:border-cyan-400 text-cyan-100'
                 }`}
               />
               <button type="submit" className={`absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-lg ${
                 mode === 'dev' ? 'text-pink-400 hover:bg-pink-900/30' : 'text-cyan-400 hover:bg-cyan-900/30'
               }`}>
                  ➤
               </button>
             </form>
          </div>
        </div>

        {/* Right Panel */}
        <div className="w-72 flex flex-col gap-6">
           <div className="flex-1 rounded-2xl bg-[#000c14]/60 backdrop-blur-xl border border-cyan-900/50 p-5">
             <h3 className="text-xs font-bold text-cyan-600 tracking-wider mb-4">🧠 ACTIVE MEMORY</h3>
             <div className="flex flex-wrap gap-2">
                <span className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300">Python RAG</span>
                <span className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300">Docker Debug</span>
             </div>
           </div>
           
           <div className="h-48 rounded-2xl bg-[#000c14]/60 backdrop-blur-xl border border-cyan-900/50 p-5 flex flex-col">
             <h3 className="text-xs font-bold text-cyan-600 tracking-wider mb-2">🖥️ VISION PREVIEW</h3>
             <div className="flex-1 bg-black/50 rounded-lg border border-slate-800 flex items-center justify-center">
                <span className="text-xs text-slate-600">Screen Feed Offline</span>
             </div>
           </div>
        </div>

      </div>

      {/* Footer Status Bar */}
      <div className={`absolute bottom-0 w-full px-6 py-2 text-xs flex justify-between border-t backdrop-blur-md ${
        mode === 'dev' ? 'bg-pink-950/20 border-pink-900/30 text-pink-300/60' : 'bg-cyan-950/20 border-cyan-900/30 text-cyan-300/60'
      }`}>
        <div className="flex gap-4">
          <span>CPU: 14%</span>
          <span>GPU: 22%</span>
          <span>Vectors: 4.2k</span>
        </div>
        <div>{status}</div>
      </div>
      
    </div>
  )
}

export default App
