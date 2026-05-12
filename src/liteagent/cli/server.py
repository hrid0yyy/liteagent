import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ..tools.registry import registry

app = FastAPI(title="LiteAgent Tool Inspector")

@app.get("/api/tools")
async def get_tools():
    return registry.schemas

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
    <div class="max-w-6xl mx-auto">
        <header class="mb-12 flex items-center justify-between">
            <div>
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight">LiteAgent <span class="text-indigo-600">Tool Inspector</span></h1>
                <p class="mt-2 text-lg text-slate-600">Explore and verify the capabilities of your agent's tools.</p>
            </div>
            <div class="hidden md:block">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    <span class="w-2 h-2 mr-2 bg-green-500 rounded-full animate-pulse"></span>
                    Live
                </span>
            </div>
        </header>

        <div id="tools-container" class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- Loading skeleton -->
            <div class="animate-pulse bg-white rounded-2xl p-8 shadow-sm border border-slate-200 h-64"></div>
            <div class="animate-pulse bg-white rounded-2xl p-8 shadow-sm border border-slate-200 h-64"></div>
        </div>
    </div>

    <script>
        async function loadTools() {
            try {
                const res = await fetch('/api/tools');
                const tools = await res.json();
                const container = document.getElementById('tools-container');
                container.innerHTML = '';

                tools.forEach(tool => {
                    let paramsHtml = '';
                    const props = tool.parameters.properties;
                    const required = tool.parameters.required || [];

                    for (const [name, details] of Object.entries(props)) {
                        const isRequired = required.includes(name);
                        paramsHtml += `
                            <div class="p-4 bg-slate-50 rounded-xl border border-slate-100 group transition-all hover:border-indigo-200 hover:bg-white hover:shadow-sm">
                                <div class="flex items-center justify-between mb-2">
                                    <div class="flex items-center space-x-2">
                                        <span class="font-mono text-sm font-bold text-slate-900">${name}</span>
                                        ${isRequired ? '<span class="text-[10px] uppercase tracking-wider font-bold text-rose-500 bg-rose-50 px-1.5 py-0.5 rounded">Required</span>' : ''}
                                    </div>
                                    <span class="font-mono text-[11px] text-slate-500 bg-slate-200/50 px-2 py-0.5 rounded">${details.type}</span>
                                </div>
                                <p class="text-sm text-slate-600 leading-relaxed">${details.description || 'No description provided.'}</p>
                            </div>
                        `;
                    }
                    
                    container.innerHTML += `
                        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden transition-all hover:shadow-md hover:border-indigo-100 flex flex-col h-full">
                            <div class="p-8 flex-grow">
                                <div class="flex items-start justify-between mb-4">
                                    <h2 class="text-2xl font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">${tool.name}</h2>
                                    <div class="p-2 bg-indigo-50 rounded-lg">
                                        <svg class="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 11-4 0v1a1 1 0 01-1 1h-3a1 1 0 01-1-1v-3a1 1 0 011-1h1a2 2 0 100-4h-1a1 1 0 01-1-1V7a1 1 0 011-1h3a1 1 0 011 1V4z"></path></svg>
                                    </div>
                                </div>
                                <p class="text-slate-600 leading-relaxed mb-8">${tool.description || 'No description provided.'}</p>
                                
                                <div class="space-y-4">
                                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest">Parameters</h3>
                                    <div class="grid grid-cols-1 gap-3">
                                        ${paramsHtml || '<p class="text-sm text-slate-400 italic py-4">This tool has no parameters.</p>'}
                                    </div>
                                </div>
                            </div>
                            <div class="px-8 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                                <span class="text-xs font-medium text-slate-400">LiteAgent Internal v0.1</span>
                                <button class="text-xs font-bold text-indigo-600 hover:text-indigo-700 transition-colors uppercase tracking-wider">Expand Details &rarr;</button>
                            </div>
                        </div>
                    `;
                });
            } catch (err) {
                document.getElementById('tools-container').innerHTML = `
                    <div class="col-span-full p-12 bg-rose-50 border border-rose-100 rounded-2xl text-center">
                        <p class="text-rose-600 font-bold text-lg">Failed to load tools. Is the server running?</p>
                    </div>
                `;
            }
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
