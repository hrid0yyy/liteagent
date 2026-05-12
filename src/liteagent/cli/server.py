import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi import Body
from ..tools.registry import registry

app = FastAPI(title="LiteAgent Tool Inspector")

@app.get("/api/tools")
async def get_tools():
    return registry.schemas

@app.post("/api/tools/execute")
async def execute_tool(data: dict = Body(...)):
    tool_name = data.get("tool_name")
    params = data.get("params", {})
    print(f"Execute request: tool={tool_name}, params={params}")
    if tool_name not in registry.tools:
        return {"error": f"Tool '{tool_name}' not found"}
    try:
        result = registry.tools[tool_name](**params)
        return {"result": result}
    except Exception as e:
        import traceback
        return {"error": str(e) + "\n" + traceback.format_exc()}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LiteAgent Tool Inspector</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap');
        body { font-family: 'Inter', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
    </style>
</head>
<body class="bg-slate-50 min-h-screen p-6 md:p-12">
    <div class="max-w-4xl mx-auto">
        <header class="mb-8 flex items-center justify-between">
            <div>
                <h1 class="text-3xl font-extrabold text-slate-900 tracking-tight">LiteAgent <span class="text-indigo-600">Tool Inspector</span></h1>
                <p class="mt-2 text-lg text-slate-600">Select a tool to view its parameters and sample inputs.</p>
            </div>
            <div class="hidden md:block">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    <span class="w-2 h-2 mr-2 bg-green-500 rounded-full animate-pulse"></span>
                    Live
                </span>
            </div>
        </header>

        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
            <label class="block text-sm font-semibold text-slate-700 mb-2">Select a Tool</label>
            <select id="tool-select" class="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all">
                <option value="">-- Choose a tool --</option>
            </select>
        </div>

        <div id="tool-details" class="hidden">
            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="p-8 border-b border-slate-100">
                    <h2 id="tool-name" class="text-2xl font-bold text-slate-900 mb-2"></h2>
                    <p id="tool-description" class="text-slate-600 leading-relaxed"></p>
                </div>
                
                <div class="p-8">
                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-6">Parameters</h3>
                    <div id="params-container" class="space-y-6"></div>
                    
                    <div class="mt-8 flex items-center gap-4">
                        <button id="run-btn" class="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            Run Tool
                        </button>
                        <div id="run-status" class="text-sm text-slate-500"></div>
                    </div>
                </div>
                
                <div id="result-container" class="hidden border-t border-slate-100">
                    <div class="p-8 bg-slate-50">
                        <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Output</h3>
                        <pre id="result-output" class="bg-slate-900 text-slate-100 p-6 rounded-xl text-sm font-mono overflow-x-auto whitespace-pre-wrap"></pre>
                    </div>
                </div>
            </div>
        </div>

        <div id="placeholder" class="text-center py-16">
            <div class="inline-flex items-center justify-center w-16 h-16 bg-slate-100 rounded-full mb-4">
                <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
            </div>
            <p class="text-slate-500 font-medium">Select a tool from the dropdown above</p>
        </div>
    </div>

    <script>
        let allTools = [];

        async function loadTools() {
            try {
                const res = await fetch('/api/tools');
                allTools = await res.json();
                
                const select = document.getElementById('tool-select');
                allTools.forEach(tool => {
                    const option = document.createElement('option');
                    option.value = tool.name;
                    option.textContent = tool.name;
                    select.appendChild(option);
                });
            } catch (err) {
                console.error('Failed to load tools:', err);
            }
        }

        document.getElementById('tool-select').addEventListener('change', function(e) {
            const selectedTool = e.target.value;
            const detailsDiv = document.getElementById('tool-details');
            const placeholder = document.getElementById('placeholder');
            
            if (!selectedTool) {
                detailsDiv.classList.add('hidden');
                placeholder.classList.remove('hidden');
                return;
            }
            
            const tool = allTools.find(t => t.name === selectedTool);
            if (!tool) return;
            
            placeholder.classList.add('hidden');
            detailsDiv.classList.remove('hidden');
            
            document.getElementById('tool-name').textContent = tool.name;
            document.getElementById('tool-description').textContent = tool.description || 'No description provided.';
            
            const paramsContainer = document.getElementById('params-container');
            const props = tool.parameters.properties;
            const required = tool.parameters.required || [];
            
            if (Object.keys(props).length === 0) {
                paramsContainer.innerHTML = '<p class="text-sm text-slate-400 italic py-4">This tool has no parameters.</p>';
                return;
            }
            
            paramsContainer.innerHTML = '';
            
            for (const [name, details] of Object.entries(props)) {
                const isRequired = required.includes(name);
                const sampleValue = details.sample || '';
                const inputType = details.type === 'integer' ? 'number' : 'text';
                
                const paramHtml = `
                    <div class="bg-slate-50 rounded-xl p-5 border border-slate-100">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center space-x-2">
                                <span class="font-mono text-sm font-bold text-slate-900">${name}</span>
                                ${isRequired ? '<span class="text-[10px] uppercase tracking-wider font-bold text-rose-500 bg-rose-50 px-1.5 py-0.5 rounded">Required</span>' : ''}
                            </div>
                            <span class="font-mono text-[11px] text-slate-500 bg-slate-200/50 px-2 py-0.5 rounded">${details.type}</span>
                        </div>
                        <p class="text-sm text-slate-600 mb-4">${details.description || 'No description provided.'}</p>
                        <div>
                            <label class="block text-xs font-semibold text-slate-500 mb-1.5">Sample Input</label>
                            <textarea data-param="${name}"
                                      class="param-input w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all placeholder-slate-300 resize-none"
                                      placeholder="Enter value...">${escapeHtml(sampleValue)}</textarea>
                        </div>
                    </div>
                `;
                paramsContainer.innerHTML += paramHtml;
            }
            
            document.querySelectorAll('.param-input').forEach(textarea => {
                textarea.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = (this.scrollHeight + 4) + 'px';
                });
                textarea.dispatchEvent(new Event('input'));
            });
            
            document.getElementById('run-btn').onclick = runTool;
        });

        async function runTool() {
            const toolName = document.getElementById('tool-select').value;
            if (!toolName) return;
            
            const inputs = document.querySelectorAll('#params-container textarea[data-param], #params-container input[data-param]');
            const params = {};
            
            inputs.forEach(input => {
                const paramName = input.dataset.param;
                const rawValue = input.value;
                let value = "";
                if (input.type === 'number') {
                    value = parseInt(rawValue) || 0;
                } else if (rawValue.startsWith('[') && rawValue.endsWith(']')) {
                    try {
                        value = JSON.parse(rawValue);
                    } catch (e) {
                        value = rawValue;
                    }
                } else {
                    value = rawValue;
                }
                params[paramName] = value;
            });
            
            console.log('Params sent:', params);
            
            const statusEl = document.getElementById('run-status');
            const resultContainer = document.getElementById('result-container');
            const resultOutput = document.getElementById('result-output');
            
            statusEl.textContent = 'Running...';
            statusEl.className = 'text-sm text-amber-600';
            
            try {
                const payload = {tool_name: toolName, params: params};
                console.log('Sending payload:', JSON.stringify(payload));
                
                const res = await fetch('/api/tools/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                console.log('Server response:', data);
                
                resultContainer.classList.remove('hidden');
                if (data.error) {
                    resultOutput.textContent = 'Error: ' + data.error;
                    resultOutput.className = 'bg-slate-900 text-rose-400 p-6 rounded-xl text-sm font-mono overflow-x-auto whitespace-pre-wrap';
                } else {
                    resultOutput.textContent = data.result;
                    resultOutput.className = 'bg-slate-900 text-emerald-400 p-6 rounded-xl text-sm font-mono overflow-x-auto whitespace-pre-wrap';
                }
                statusEl.textContent = 'Done';
                statusEl.className = 'text-sm text-emerald-600';
            } catch (err) {
                resultContainer.classList.remove('hidden');
                resultOutput.textContent = 'Error: ' + err.message;
                resultOutput.className = 'bg-slate-900 text-rose-400 p-6 rounded-xl text-sm font-mono overflow-x-auto whitespace-pre-wrap';
                statusEl.textContent = 'Failed';
                statusEl.className = 'text-sm text-rose-600';
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        loadTools();
    </script>
</body>
</html>
"""

async def start_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()
