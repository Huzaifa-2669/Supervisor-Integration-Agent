"""
HTML/React frontend served by FastAPI. Uses CDN React + Babel to keep the demo
self-contained while providing a richer UI than plain HTML.
"""
from __future__ import annotations

import json
from typing import List
from fastapi.responses import HTMLResponse

from .models import AgentMetadata


STYLES = """
          :root {
            --bg: #0f172a;
            --panel: #0b1220;
            --card: #111827;
            --accent: #22d3ee;
            --muted: #94a3b8;
            --text: #e2e8f0;
            --border: #1f2937;
            --success: #22c55e;
            --error: #ef4444;
            --glow: rgba(34,211,238,0.25);
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            background:
              radial-gradient(circle at 20% 20%, #1e293b, #0f172a 45%),
              radial-gradient(circle at 80% 0%, #0ea5e9, #0f172a 35%),
              var(--bg);
            color: var(--text);
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
          }
          .shell {
            max-width: 1400px;
            margin: 0 auto;
            padding: 56px 8px 110px;
            position: relative;
          }
          /* Ambient sparkles */
          .sparkle {
            position: absolute;
            width: 6px; height: 6px;
            border-radius: 50%;
            background: rgba(34,211,238,0.8);
            box-shadow: 0 0 12px var(--glow);
            animation: float 6s ease-in-out infinite;
            opacity: 0.7;
          }
          @keyframes float {
            0% { transform: translateY(0px) translateX(0px); opacity: 0.7; }
            50% { transform: translateY(-10px) translateX(6px); opacity: 1; }
            100% { transform: translateY(0px) translateX(0px); opacity: 0.7; }
          }

          .hero {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 28px;
          }
          .badge {
            display: inline-flex; gap: 8px; align-items: center;
            padding: 6px 10px; border-radius: 999px;
            background: rgba(34,211,238,0.1);
            color: var(--accent); font-weight: 600; font-size: 13px;
            border: 1px solid rgba(34,211,238,0.2);
          }
          .panel {
            background: rgba(11,18,32,0.9);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.35);
          }
          .chat {
            display: flex;
            flex-direction: column;
            gap: 16px;
          }
          .chat-feed {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            min-height: 75vh;
            max-height: 85vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
          }
          .msg {
            max-width: 82%;
            padding: 14px 16px;
            border-radius: 16px;
            background: var(--card);
            border: 1px solid var(--border);
            box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            white-space: pre-wrap;
          }
          .msg.user {
            align-self: flex-end;
            background: linear-gradient(120deg, #22d3ee33, #22c55e33);
            border-color: rgba(34,211,238,0.35);
          }
          .msg.assistant {
            align-self: flex-start;
          }
          .input-bar {
            display: grid;
            grid-template-columns: 1fr 200px;
            gap: 14px;
            align-items: start;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 12px 14px;
          }
          textarea {
            width: 100%;
            min-height: 150px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            color: var(--text);
            padding: 16px;
            resize: vertical;
            font-size: 15px;
            line-height: 1.6;
          }
          .controls {
            display: flex; align-items: center; gap: 14px; margin-top: 12px; flex-wrap: wrap;
          }
          .input-controls {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            color: var(--muted);
            font-size: 14px;
          }
          .switch { position: relative; display: inline-flex; align-items: center; gap: 10px; cursor: pointer; color: var(--muted); font-size: 14px; }
          .switch input { display: none; }
          .slider { position: relative; width: 44px; height: 24px; background: var(--card); border-radius: 12px; border: 1px solid var(--border); transition: background 120ms ease, border 120ms ease; }
          .slider::after { content: ''; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: var(--muted); transition: transform 160ms ease, background 160ms ease; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }
          .switch input:checked + .slider { background: linear-gradient(120deg, #22d3ee, #22c55e); border-color: rgba(34,211,238,0.35); }
          .switch input:checked + .slider::after { transform: translateX(20px); background: #0b1220; }
          .file-input { background: var(--panel); border: 1px solid var(--border); padding: 10px 12px; border-radius: 12px; color: var(--text); cursor: pointer; transition: border 120ms ease, transform 120ms ease; }
          .file-input:hover { border-color: var(--accent); transform: translateY(-1px); }
          .file-input::-webkit-file-upload-button { background: linear-gradient(120deg, #22d3ee, #22c55e); border: none; border-radius: 999px; padding: 8px 12px; color: #0b1220; font-weight: 700; cursor: pointer; }
          .file-meta { color: var(--muted); font-size: 13px; }
          .file-trigger { background: var(--panel); border: 1px solid var(--border); padding: 12px 14px; border-radius: 12px; color: var(--text); cursor: pointer; transition: border 120ms ease, transform 120ms ease; text-align: center; }
          .file-trigger:hover { border-color: var(--accent); transform: translateY(-1px); }
          button.primary {
            background: linear-gradient(120deg, #22d3ee, #22c55e);
            color: #0b1220;
            border: none;
            padding: 12px 18px;
            font-weight: 700;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease;
          }
          button.primary:hover { transform: translateY(-1px); box-shadow: 0 10px 30px rgba(34,211,238,0.25); filter: brightness(1.05); }
          button.primary:active { transform: translateY(0px); }
          .status { font-size: 14px; color: var(--muted); display: inline-flex; align-items: center; gap: 8px; }
          .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--glow); animation: pulse 1.2s ease-in-out infinite; }
          @keyframes pulse { 0% { transform: scale(1); opacity: .9; } 50% { transform: scale(1.35); opacity: 1; } 100% { transform: scale(1); opacity: .9; } }

          .section-title { display: flex; align-items: center; gap: 8px; margin: 18px 0 8px; font-weight: 700; color: #fff; }
          .small { color: var(--muted); font-size: 14px; }
          .result-box {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
            min-height: 60px;
            position: relative;
            line-height: 1.7;
            font-size: 15px;
            color: var(--text);
            max-height: 70vh;
            overflow-y: auto;
          }
          .result-box:not(:has(.markdown-content)) {
            white-space: pre-wrap;
          }
          .result-box::-webkit-scrollbar {
            width: 8px;
          }
          .result-box::-webkit-scrollbar-track {
            background: var(--card);
            border-radius: 4px;
          }
          .result-box::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
          }
          .result-box::-webkit-scrollbar-thumb:hover {
            background: var(--muted);
          }
          /* Markdown styling */
          .markdown-content {
            color: var(--text);
          }
          .markdown-content h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--accent);
            margin: 0 0 20px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--border);
          }
          .markdown-content h2 {
            font-size: 20px;
            font-weight: 600;
            color: #fff;
            margin: 24px 0 12px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border);
          }
          .markdown-content h3 {
            font-size: 18px;
            font-weight: 600;
            color: #fff;
            margin: 20px 0 10px 0;
          }
          .markdown-content ul, .markdown-content ol {
            margin: 12px 0;
            padding-left: 24px;
            line-height: 1.8;
          }
          .markdown-content li {
            margin-bottom: 8px;
          }
          .markdown-content p {
            margin: 12px 0;
            line-height: 1.7;
          }
          .markdown-content strong {
            color: var(--accent);
            font-weight: 600;
          }
          .markdown-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
          }
          .markdown-content th {
            background: var(--panel);
            padding: 10px;
            text-align: left;
            font-weight: 600;
            color: var(--accent);
            border-bottom: 2px solid var(--border);
          }
          .markdown-content td {
            padding: 10px;
            border-bottom: 1px solid var(--border);
          }
          .markdown-content tr:last-child td {
            border-bottom: none;
          }
          .markdown-content code {
            background: var(--card);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 0.9em;
            color: var(--accent);
          }
          .markdown-content pre {
            background: var(--card);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            overflow-x: auto;
            margin: 12px 0;
          }
          .markdown-content pre code {
            background: transparent;
            padding: 0;
          }
          .copy-btn {
            position: absolute; top: 10px; right: 10px;
            font-size: 12px; padding: 6px 10px; border-radius: 999px;
            border: 1px solid var(--border); background: var(--card); color: var(--text);
            cursor: pointer;
          }

          /* Orbit layout for agents */
          .orbit {
            position: relative;
            height: 420px;
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(17,24,39,0.8), rgba(17,24,39,0.5));
            border: 1px solid var(--border);
            overflow: auto; /* allow scrolling when agents overflow */
            scroll-padding: 12px;
          }
          .sun {
            position: absolute; left: 50%; top: 50%;
            transform: translate(-50%, -50%);
            background: radial-gradient(circle, #22d3ee 0%, #22c55e 60%);
            width: 120px; height: 120px; border-radius: 50%;
            box-shadow: 0 0 40px rgba(34,211,238,0.35);
            display: flex; align-items: center; justify-content: center;
            color: #0b1220; font-weight: 800;
          }
          .ring {
            position: absolute; left: 50%; top: 50%;
            transform: translate(-50%, -50%);
            border: 1px dashed rgba(148,163,184,0.25);
            border-radius: 50%;
            animation: rotate 24s linear infinite;
            pointer-events: none;
          }
          .ring.r1 { width: 220px; height: 220px; animation-duration: 26s; }
          .ring.r2 { width: 280px; height: 280px; animation-duration: 32s; }
          .ring.r3 { width: 340px; height: 340px; animation-duration: 40s; }
          @keyframes rotate { from { transform: translate(-50%, -50%) rotate(0deg); } to { transform: translate(-50%, -50%) rotate(360deg); } }

          .planet {
            position: absolute;
            padding: 8px 10px;
            border-radius: 12px;
            background: var(--card);
            border: 1px solid var(--border);
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            width: 180px;
            transition: transform 150ms ease, box-shadow 150ms ease;
            cursor: pointer;
          }
          .planet:hover { transform: translateY(-2px); box-shadow: 0 12px 34px rgba(0,0,0,0.4); }
          .planet h4 { margin: 0; font-size: 13px; color: #fff; text-align: center; }
          .planet p { display: none; }
          .pill { display: inline-flex; padding: 4px 10px; border-radius: 999px; background: rgba(34,211,238,0.12); color: var(--text); font-size: 12px; border: 1px solid rgba(34,211,238,0.2); margin-right: 6px; margin-top: 4px; }

          /* Debug dock */
          .dock {
            margin-top: 18px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
          }
          .dock-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px 12px; background: rgba(17,24,39,0.7); border-bottom: 1px solid var(--border);
          }
          .dock-content { padding: 12px; }
          .timeline {
            display: grid; gap: 10px;
          }
          .task-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
            margin-top: 12px;
          }
          .task-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 12px 32px rgba(0,0,0,0.35);
            display: grid;
            gap: 8px;
          }
          .task-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }
          .status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: rgba(34,211,238,0.15); border: 1px solid rgba(34,211,238,0.25); font-size: 12px; color: var(--text); }
          .status-pill.todo { background: rgba(148,163,184,0.15); border-color: rgba(148,163,184,0.25); }
          .status-pill.in_progress { background: rgba(34,197,94,0.12); border-color: rgba(34,197,94,0.25); }
          .status-pill.done { background: rgba(59,130,246,0.15); border-color: rgba(59,130,246,0.25); }
          .timeline-item {
            display: grid; grid-template-columns: 28px 1fr auto; gap: 10px;
            align-items: center; background: var(--card); border: 1px solid var(--border);
            padding: 10px; border-radius: 10px;
          }
          .dot { width: 10px; height: 10px; border-radius: 50%; }
          .dot.success { background: var(--success); box-shadow: 0 0 12px rgba(34,197,94,0.35); }
          .dot.error { background: var(--error); box-shadow: 0 0 12px rgba(239,68,68,0.35); }
          .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
          .json-box {
            background: #0d1524; padding: 10px; border-radius: 10px;
            border: 1px solid var(--border); overflow-x: auto;
          }

          footer { margin-top: 22px; color: var(--muted); font-size: 13px; text-align: center; }
"""

COMMON_REACT = """
          const { useState, useEffect, useMemo } = React;

          const Pill = ({ text }) => <span className="pill">{text}</span>;

          const PlanetCard = ({ agent, style }) => {
            const tooltip = `${agent.description || ''}` + (agent.intents?.length ? `\nIntents: ${agent.intents.join(', ')}` : '');
            return (
              <div className="planet" style={style} title={tooltip}>
                <h4>{agent.name}</h4>
              </div>
            );
          };

          const TimelineItem = ({ item, index }) => (
            <div className="timeline-item">
              <span className={`dot ${item.status === 'success' ? 'success' : 'error'}`}></span>
              <div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <strong>{item.name}</strong>
                  <span className="mono" style={{ color: 'var(--muted)' }}>{item.intent}</span>
                </div>
                {item.output && <div className="small" style={{ marginTop: 4, color: '#cbd5e1' }}>{String(item.output).slice(0, 160)}{String(item.output).length > 160 ? '…' : ''}</div>}
                {item.error && <div className="small" style={{ marginTop: 4, color: '#fca5a5' }}>{item.error}</div>}
              </div>
                  <span className="mono" style={{ color: 'var(--muted)' }}>#{index+1}</span>
                </div>
          );

          const TaskCard = ({ task }) => {
            const deadline = task.task_deadline || task.deadline || task.due_date || null;
            const status = (task.status || task.task_status || 'todo').toLowerCase().replace(' ', '_');
            const id = task.task_id || task._id || task.id || '—';
            const order = task.execution_order ?? task.order ?? null;
            const dependsOn = Array.isArray(task.depends_on) ? task.depends_on.filter(Boolean) : [];
            return (
              <div className="task-card">
                <div className="task-meta">
                  <span className={`status-pill ${status}`}>{status.replace('_', ' ')}</span>
                  <span className="mono">ID: {id}</span>
                  {order !== null && <span className="mono">Order: {order}</span>}
                  {deadline && <span className="mono">Due: {deadline}</span>}
                </div>
                <h3 style={{ margin: '0 0 4px' }}>{task.task_name || task.title || 'Untitled task'}</h3>
                <p className="small" style={{ margin: 0, color: '#cbd5e1' }}>{task.task_description || task.description || 'No description provided.'}</p>
                {dependsOn.length > 0 && (
                  <div className="task-meta">
                    <span>Depends on:</span>
                    {dependsOn.map(dep => <span key={dep} className="pill">Task {dep}</span>)}
                  </div>
                )}
              </div>
            );
          };
"""

def _render_page(title: str, script_body: str) -> HTMLResponse:
    html_content = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{title}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
        <style>{STYLES}</style>
      </head>
      <body>
        <div class="shell">
          <div id="root"></div>
          <!-- ambient sparkles -->
          <div class="sparkle" style="left: 6%; top: 20%; animation-delay: .2s;"></div>
          <div class="sparkle" style="left: 92%; top: 12%; animation-delay: .6s;"></div>
          <div class="sparkle" style="left: 14%; top: 78%; animation-delay: 1.1s;"></div>
          <div class="sparkle" style="left: 70%; top: 65%; animation-delay: .9s;"></div>
        </div>
        <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
        <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
        <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <script type="text/babel">
          {COMMON_REACT}
          {script_body}
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

def render_home() -> HTMLResponse:
    script = """
          const App = () => {
            const initialConv = window.localStorage.getItem('conversationId') || (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
            const [conversationId, setConversationId] = useState(initialConv);
            const [messages, setMessages] = useState([
              { role: 'assistant', content: 'Hi there! Ask a question and I will plan which agents to call.' }
            ]);
            const [input, setInput] = useState('Summarize our project status and flag any deadline risks.');
            const [debug, setDebug] = useState(false);
            const [agents, setAgents] = useState([]);
            const [usedAgents, setUsedAgents] = useState([]);
            const [intermediate, setIntermediate] = useState({});
            const [status, setStatus] = useState('');
            const [error, setError] = useState(null);
            const [openIntermediate, setOpenIntermediate] = useState(false);
            const [fileName, setFileName] = useState('');
            const [uploadedFiles, setUploadedFiles] = useState([]);
            const [isMeetingQuery, setIsMeetingQuery] = useState(false);
            const chatRef = React.useRef(null);
            const fileInputRef = React.useRef(null);

            useEffect(() => {
              if (chatRef.current) {
                chatRef.current.scrollTop = chatRef.current.scrollHeight;
              }
            }, [messages, status]);

            const renderMarkdown = (text) => {
              if (!text || typeof text !== 'string') return text;
              try {
                if (typeof marked !== 'undefined') {
                  const html = marked.parse(text);
                  return <div className="markdown-content" dangerouslySetInnerHTML={{ __html: html }} />;
                }
                return text;
              } catch {
                return text;
              }
            };

            useEffect(() => {
              fetch('/api/agents').then((r) => r.json()).then(setAgents).catch(() => setAgents([]));
              window.localStorage.setItem('conversationId', initialConv);
            }, []);

            useEffect(() => {
              const lowerInput = input.toLowerCase();
              const meetingKeywords = ['meeting', 'minutes', 'follow-up', 'followup', 'action item', 'transcript', 'standup'];
              const hasMeetingKeyword = meetingKeywords.some(keyword => lowerInput.includes(keyword));
              setIsMeetingQuery(hasMeetingKeyword);
            }, [input]);

            const resetConversation = () => {
              const next = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
              setConversationId(next);
              window.localStorage.setItem('conversationId', next);
              setMessages([{ role: 'assistant', content: 'New chat started. How can I help?' }]);
              setUsedAgents([]);
              setIntermediate({});
              setError(null);
              setFileName('');
              setUploadedFiles([]);
            };

            const handleSend = async () => {
              if (!input.trim()) return;
              const userMsg = { role: 'user', content: input };
              setMessages((prev) => [...prev, userMsg]);
              setInput('');
              setStatus('Working...');
              setError(null);
              setUsedAgents([]);
              setIntermediate({});

              const fileUploads = [...uploadedFiles];

              try {
                const requestBody = {
                  query: userMsg.content,
                  user_id: null,
                  conversation_id: conversationId,
                  options: { debug }
                };

                if (fileUploads.length > 0) {
                  requestBody.file_uploads = fileUploads;
                }

                const resp = await fetch('/api/query', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(requestBody)
                });
                const data = await resp.json();
                setStatus('');
                setUsedAgents(data.used_agents || []);
                setIntermediate(data.intermediate_results || {});
                setError(data.error);
                
                const files = [];
                if (data.intermediate_results) {
                  Object.values(data.intermediate_results).forEach(step => {
                    // Check for file_output in details (Hiring Agent style)
                    if (step.output && step.output.details && step.output.details.file_output) {
                      files.push(step.output.details.file_output);
                    }
                    // Check for file_output in details.summary (Report Generator style if different)
                    else if (step.output && step.output.details && step.output.details.summary && step.output.details.summary.file_output) {
                       files.push(step.output.details.summary.file_output);
                    }
                  });
                }

                setMessages((prev) => [...prev, { 
                  role: 'assistant', 
                  content: data.answer || 'No answer produced.',
                  files: files
                }]);
                setUploadedFiles([]);
                setFileName('');
                if (fileInputRef.current) fileInputRef.current.value = '';
              } catch (err) {
                setStatus('');
                setError({ message: 'Network error', type: 'network_error' });
                setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, I could not reach the server.' }]);
              }
            };

            const handleFileUpload = (e) => {
              const files = Array.from(e.target.files);
              if (!files.length) return;

              setStatus(`Reading ${files.length} file(s)...`);
              setFileName(files.length === 1 ? files[0].name : `${files.length} files attached`);

              const promises = files.map(file => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (event) => {
                  const dataUrl = event.target.result;
                  // Handle both data:URL and raw base64 if that ever happens (FileReader usually returns data:URL)
                  const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
                  
                  // Simple mime type detection fallback
                  let mimeType = file.type;
                  if (!mimeType) {
                     if (file.name.endsWith('.pdf')) mimeType = 'application/pdf';
                     else if (file.name.endsWith('.docx')) mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
                     else if (file.name.endsWith('.txt')) mimeType = 'text/plain';
                     else if (file.name.endsWith('.md')) mimeType = 'text/markdown';
                     else mimeType = 'application/octet-stream';
                  }

                  resolve({
                    base64_data: base64,
                    filename: file.name,
                    mime_type: mimeType
                  });
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
              }));

              Promise.all(promises)
                .then(newFiles => {
                  setUploadedFiles(newFiles);
                  
                  // Auto-populate input if empty, but don't overwrite if user is typing a job role
                  if (!input.trim() || input === 'Summarize our project status and flag any deadline risks.') {
                     if (newFiles.length === 1 && (newFiles[0].filename.endsWith('.mp3'))) {
                        setInput('Extract meeting minutes and action items from this audio recording');
                     } else {
                        // Generic prompt, user can overwrite for "process workflow"
                        setInput('Summarize the attached document(s)');
                     }
                  }
                  setStatus('');
                })
                .catch(err => {
                  console.error(err);
                  setStatus('');
                  setError({ message: 'Failed to read files', type: 'file_error' });
                  setFileName('');
                  setUploadedFiles([]);
                });
            };

            return (
              <div className="panel">
                <div className="hero" style={{ gap: 6, alignItems: 'flex-start' }}>
                  <div className="badge">Supervisor · Multi-Agent Orchestrator</div>
                  <div>
                    <h1 style={{ margin: '0 0 6px' }}>Chat with the supervisor.</h1>
                    <p className="small" style={{ maxWidth: 720 }}>A focused chat workspace: ask your question, attach files, inspect agent calls, and keep the flow moving.</p>
                  </div>
                </div>

                <div className="chat">
                  <div className="input-controls" style={{ justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                      <label className="switch">
                        <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} />
                        <span className="slider"></span>
                        <span>Show debug</span>
                      </label>
                      <span className="small" style={{ color: 'var(--muted)' }}>Tip: Keep requests concise; add context via file upload.</span>
                    </div>
                    {status && <span className="status"><span className="status-dot"></span>{status}</span>}
                  </div>

                  <div className="chat-feed" id="chat-feed" ref={chatRef}>
                    {messages.map((m, idx) => (
                      <div key={idx} className={`msg ${m.role}`}>
                        <strong style={{ display: 'block', marginBottom: 6, color: m.role === 'user' ? '#22d3ee' : '#cbd5e1' }}>{m.role === 'user' ? 'You' : 'Supervisor'}</strong>
                        {m.role === 'assistant' ? renderMarkdown(m.content) : m.content}
                        {m.files && m.files.length > 0 && (
                          <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
                            {m.files.map((f, i) => (
                              <div key={i} style={{ padding: '10px 14px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div style={{ fontSize: 20 }}>📄</div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{ fontWeight: 600, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.filename}</div>
                                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>Generated Document</div>
                                </div>
                                <a href={`data:${f.mime_type};base64,${f.data}`} download={f.filename} className="primary" style={{ padding: '6px 12px', textDecoration: 'none', fontSize: 13, display: 'inline-flex', alignItems: 'center' }}>Download</a>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                    {status && (
                      <div className="msg assistant" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <span className="status-dot"></span> Working on your request...
                      </div>
                    )}
                  </div>

                  <div className="input-bar">
                    <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your message..." rows={3} />
                    <div style={{ display: 'grid', gap: 8 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} accept=".txt,.md,.json,.csv,.log,.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={handleFileUpload} />
                        <button type="button" className="file-trigger" onClick={() => fileInputRef.current && fileInputRef.current.click()}>Attach file(s)</button>
                        {fileName && <span className="file-meta">Attached: {fileName}</span>}
                      </div>
                      <button className="primary" onClick={handleSend} style={{ padding: '12px 16px' }}>Send</button>
                      {error && <div className="small" style={{ color: '#f87171' }}>Error: {error.message}</div>}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 18 }}>
                  <a href="/agents" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none', marginRight: 12 }}>View all agents →</a>
                  <a href="/tasks" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}>View tasks →</a>
                </div>

                {debug && (
                  <div className="dock">
                    <div className="dock-header">
                      <strong>Debug</strong>
                      <span className="small">Planner calls & intermediate payloads</span>
                    </div>
                    <div className="dock-content">
                      <label className="section-title">Agent call timeline</label>
                      <div className="timeline">
                        {usedAgents.map((ua, idx) => <TimelineItem key={`${ua.name}-${ua.intent}-${idx}`} item={ua} index={idx} />)}
                        {usedAgents.length === 0 && <span className="small">No agents called yet.</span>}
                      </div>

                      <div style={{ marginTop: 14 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <label className="section-title" style={{ margin: 0 }}>Intermediate results</label>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <button className="primary" style={{ padding: '8px 12px', fontWeight: 600 }} onClick={() => setOpenIntermediate(v => !v)}>
                            {openIntermediate ? 'Hide payload' : 'Show payload'}
                          </button>
                        </div>
                        {openIntermediate && (
                          <pre className="mono json-box" style={{ marginTop: 10 }}>{JSON.stringify(intermediate, null, 2)}</pre>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                <footer>Powered by FastAPI · React · LLM planner · Worker registry</footer>
              </div>
            );
          };

          ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    """
    return _render_page("Supervisor Agent Demo", script)

def render_agents_page(agents: List[AgentMetadata]) -> HTMLResponse:
    agents_json = json.dumps([a.dict() for a in agents])
    script_template = """
          const initialAgents = __AGENTS_JSON__;
          const App = () => {
            const orbitPositions = React.useMemo(() => {
              const rings = [28, 36, 44, 52];
              const items = [];
              const count = Math.max(initialAgents.length, 8);
              initialAgents.forEach((agent, i) => {
                const ringIndex = i % rings.length;
                const angle = (i * (360 / count)) % 360;
                const r = rings[ringIndex];
                const x = 50 + Math.cos(angle * Math.PI/180) * r;
                const y = 50 + Math.sin(angle * Math.PI/180) * r;
                const clampedX = Math.min(94, Math.max(6, x));
                const clampedY = Math.min(94, Math.max(6, y));
                items.push({ agent, style: { left: `${clampedX}%`, top: `${clampedY}%` } });
              });
              return items;
            }, []);

            return (
              <div className="panel">
                <div className="hero">
                  <div className="badge">Registry</div>
                  <div>
                    <h1 style={{ margin: '4px 0 6px' }}>Available Worker Agents</h1>
                    <p className="small">Visualized in orbit around the supervisor. Hover to see details.</p>
                  </div>
                </div>
                <div className="orbit" style={{ height: 520 }}>
                  <div className="sun">Supervisor</div>
                  <div className="ring r1"></div>
                  <div className="ring r2"></div>
                  <div className="ring r3"></div>
                  {orbitPositions.map(({ agent, style }) => (
                    <PlanetCard key={agent.name} agent={agent} style={{ position: 'absolute', transform: 'translate(-50%, -50%)', ...style }} />
                  ))}
                </div>
                <footer style={{ marginTop: 40 }}>
                  <a href="/" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>← Back to Dashboard</a>
                </footer>
              </div>
            );
          };
          ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    """
    script = script_template.replace("__AGENTS_JSON__", agents_json)
    return _render_page("Agents - Supervisor", script)

def render_tasks_page() -> HTMLResponse:
    script = """
          const App = () => {
            const [tasks, setTasks] = useState([]);
            const [status, setStatus] = useState('Loading tasks...');
            const [error, setError] = useState(null);
            const [sortBy, setSortBy] = useState('execution_order');

            useEffect(() => {
              fetch('/api/tasks')
                .then(async (resp) => {
                  if (!resp.ok) {
                    const data = await resp.json().catch(() => ({}));
                    throw new Error(data.detail || 'Failed to load tasks');
                  }
                  return resp.json();
                })
                .then((data) => {
                  let incoming = [];
                  if (Array.isArray(data)) {
                    incoming = data;
                  } else if (Array.isArray(data.tasks)) {
                    incoming = data.tasks;
                  } else if (data.tasks && Array.isArray(data.tasks.tasks)) {
                    incoming = data.tasks.tasks;
                  }
                  setTasks(incoming);
                  setStatus('');
                })
                .catch((err) => {
                  setError(err.message);
                  setStatus('');
                });
            }, []);

            const sortedTasks = React.useMemo(() => {
              const copy = [...tasks];
              const numeric = (v) => {
                if (v === undefined || v === null) return Number.MAX_SAFE_INTEGER;
                const n = Number(v);
                return Number.isFinite(n) ? n : Number.MAX_SAFE_INTEGER;
              };
              const toDate = (v) => {
                if (!v) return new Date(8640000000000000); // far future
                const d = new Date(v);
                return isNaN(d.getTime()) ? new Date(8640000000000000) : d;
              };
              copy.sort((a, b) => {
                if (sortBy === 'id') {
                  const aid = numeric(a.task_id || a.id || a._id);
                  const bid = numeric(b.task_id || b.id || b._id);
                  return aid - bid;
                }
                if (sortBy === 'deadline') {
                  return toDate(a.task_deadline || a.deadline) - toDate(b.task_deadline || b.deadline);
                }
                // default execution order
                const ao = numeric(a.execution_order);
                const bo = numeric(b.execution_order);
                return ao - bo;
              });
              return copy;
            }, [tasks, sortBy]);

            return (
              <div className="panel">
                <div className="hero">
                  <div className="badge">Tasks</div>
                  <div>
                    <h1 style={{ margin: '4px 0 6px' }}>Knowledge Base Tasks</h1>
                    <p className="small">Live tasks pulled from the KnowledgeBaseBuilderAgent backend.</p>
                  </div>
                </div>

                <div className="controls" style={{ marginTop: 0 }}>
                  <label className="small">Sort:</label>
                  <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={{ background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 10, padding: '6px 10px' }}>
                    <option value="id">By ID</option>
                    <option value="deadline">By due date</option>
                    <option value="execution_order">By execution order</option>
                  </select>
                  {status && <span className="small">{status}</span>}
                  {error && <span className="small" style={{ color: '#f87171' }}>Error: {error}</span>}
                </div>

                {!status && !error && tasks.length === 0 && (
                  <div className="small">No tasks found.</div>
                )}

                <div className="task-grid">
                  {sortedTasks.map((task, idx) => <TaskCard key={task.task_id || task._id || idx} task={task} />)}
                </div>

                <footer style={{ marginTop: 30 }}>
                  <a href="/" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>← Back to Dashboard</a>
                </footer>
              </div>
            );
          };
          ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    """
    return _render_page("Tasks - Supervisor", script)

def render_query_page() -> HTMLResponse:
    script = """
          const App = () => {
            const [query, setQuery] = useState('');
            const [answer, setAnswer] = useState('');
            const [status, setStatus] = useState('');
            const [error, setError] = useState(null);

            const handleSubmit = async () => {
              if (!query.trim()) return;
              setStatus('Working...');
              setAnswer('');
              setError(null);
              try {
                const resp = await fetch('/api/query', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ query, user_id: null, options: { debug: false } })
                });
                const data = await resp.json();
                setStatus('');
                setAnswer(data.answer || '');
                setError(data.error);
              } catch (err) {
                setStatus('');
                setError({ message: 'Network error', type: 'network_error' });
              }
            };

            return (
              <div className="panel">
                <div className="hero">
                  <div className="badge">Query Interface</div>
                  <div>
                    <h1 style={{ margin: '4px 0 6px' }}>Submit a Request</h1>
                    <p className="small">Direct query interface without the full dashboard.</p>
                  </div>
                </div>

                <div>
                  <label className="section-title">Your request</label>
                  <textarea value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Type your question here..." />
                  <div className="controls">
                    <button className="primary" onClick={handleSubmit}>Submit</button>
                    {status && <span className="status"><span className="status-dot"></span>{status}</span>}
                  </div>
                </div>

                <div style={{ marginTop: 18 }}>
                  <label className="section-title">Answer</label>
                  <div className="result-box">
                    {answer || (status ? '…thinking…' : 'No answer yet.')}
                  </div>
                  {error && <div className="small" style={{ color: '#f87171', marginTop: 8 }}>Error: {error.message}</div>}
                </div>

                <footer style={{ marginTop: 40 }}>
                  <a href="/" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>← Back to Dashboard</a>
                </footer>
              </div>
            );
          };
          ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    """
    return _render_page("Query - Supervisor", script)
