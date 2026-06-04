"""Web Debug Module - Full backend call tracing with frontend log display.

This module provides:
1. DebugLogger - Centralized debug log collector
2. DebugMiddleware - HTTP request/response interceptor
3. SSE endpoint for real-time log streaming
4. Debug panel HTML for frontend display
"""

import asyncio
import json
import time
import traceback
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware


class DebugLogger:
    """Centralized debug log collector with ring buffer."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.entries: deque = deque(maxlen=max_entries)
        self.subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def log(
        self,
        category: str,
        action: str,
        detail: str = "",
        data: Any = None,
        level: str = "INFO",
        source: str = "",
    ):
        """Add a debug log entry."""
        entry = {
            "id": len(self.entries) + 1,
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "action": action,
            "detail": detail,
            "data": data,
            "level": level,
            "source": source,
        }

        async with self._lock:
            self.entries.append(entry)

            # Notify all subscribers
            for queue in self.subscribers:
                try:
                    await queue.put(entry)
                except Exception:
                    pass

        return entry

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to real-time log updates."""
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self.subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from log updates."""
        async with self._lock:
            if queue in self.subscribers:
                self.subscribers.remove(queue)

    def get_entries(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ) -> list:
        """Get recent log entries with optional filtering."""
        entries = list(self.entries)

        if category:
            entries = [e for e in entries if e["category"] == category]
        if level:
            entries = [e for e in entries if e["level"] == level]

        return entries[-limit:]

    def clear(self):
        """Clear all log entries."""
        self.entries.clear()


# Global debug logger instance
debug_logger = DebugLogger()


class DebugMiddleware(BaseHTTPMiddleware):
    """Middleware to intercept all HTTP requests and responses."""

    def __init__(self, app: FastAPI, logger: DebugLogger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip debug endpoints to avoid recursion
        if request.url.path.startswith("/api/debug"):
            return await call_next(request)

        # Log request
        request_id = int(time.time() * 1000)
        start_time = time.time()

        request_data = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else "unknown",
        }

        await self.logger.log(
            category="HTTP",
            action=f"{request.method} {request.url.path}",
            detail=f"Request from {request_data['client']}",
            data=request_data,
            level="DEBUG",
            source="middleware",
        )

        # Process request
        try:
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000

            # Log response
            response_data = {
                "status_code": response.status_code,
                "duration_ms": round(duration, 2),
                "headers": dict(response.headers),
            }

            await self.logger.log(
                category="HTTP",
                action=f"{request.method} {request.url.path}",
                detail=f"Response {response.status_code} in {duration:.1f}ms",
                data=response_data,
                level="INFO" if response.status_code < 400 else "ERROR",
                source="middleware",
            )

            return response

        except Exception as e:
            duration = (time.time() - start_time) * 1000

            await self.logger.log(
                category="HTTP",
                action=f"{request.method} {request.url.path}",
                detail=f"Error: {str(e)}",
                data={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "duration_ms": round(duration, 2),
                },
                level="ERROR",
                source="middleware",
            )
            raise


class FunctionTracer:
    """Decorator/context manager to trace function calls."""

    def __init__(self, logger: DebugLogger, category: str = "FUNC"):
        self.logger = logger
        self.category = category

    def trace(self, name: Optional[str] = None):
        """Decorator to trace function calls."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                func_name = name or f"{func.__module__}.{func.__qualname__}"
                start_time = time.time()

                await self.logger.log(
                    category=self.category,
                    action=f"CALL {func_name}",
                    detail=f"args={args}, kwargs={kwargs}",
                    level="DEBUG",
                    source=func_name,
                )

                try:
                    result = await func(*args, **kwargs)
                    duration = (time.time() - start_time) * 1000

                    await self.logger.log(
                        category=self.category,
                        action=f"RETURN {func_name}",
                        detail=f"completed in {duration:.1f}ms",
                        data={"result_type": type(result).__name__},
                        level="DEBUG",
                        source=func_name,
                    )

                    return result

                except Exception as e:
                    duration = (time.time() - start_time) * 1000

                    await self.logger.log(
                        category=self.category,
                        action=f"ERROR {func_name}",
                        detail=f"{type(e).__name__}: {str(e)}",
                        data={
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                            "duration_ms": round(duration, 2),
                        },
                        level="ERROR",
                        source=func_name,
                    )
                    raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                func_name = name or f"{func.__module__}.{func.__qualname__}"
                start_time = time.time()

                asyncio.create_task(self.logger.log(
                    category=self.category,
                    action=f"CALL {func_name}",
                    detail=f"args={args}, kwargs={kwargs}",
                    level="DEBUG",
                    source=func_name,
                ))

                try:
                    result = func(*args, **kwargs)
                    duration = (time.time() - start_time) * 1000

                    asyncio.create_task(self.logger.log(
                        category=self.category,
                        action=f"RETURN {func_name}",
                        detail=f"completed in {duration:.1f}ms",
                        data={"result_type": type(result).__name__},
                        level="DEBUG",
                        source=func_name,
                    ))

                    return result

                except Exception as e:
                    duration = (time.time() - start_time) * 1000

                    asyncio.create_task(self.logger.log(
                        category=self.category,
                        action=f"ERROR {func_name}",
                        detail=f"{type(e).__name__}: {str(e)}",
                        data={
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                            "duration_ms": round(duration, 2),
                        },
                        level="ERROR",
                        source=func_name,
                    ))
                    raise

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    async def log_call(
        self,
        action: str,
        detail: str = "",
        data: Any = None,
        level: str = "INFO",
        source: str = "",
    ):
        """Manually log a call."""
        await self.logger.log(
            category=self.category,
            action=action,
            detail=detail,
            data=data,
            level=level,
            source=source,
        )


def setup_debug_routes(app: FastAPI, logger: DebugLogger):
    """Setup debug API routes."""

    @app.get("/api/debug/logs", tags=["Debug"])
    async def api_debug_logs(
        limit: int = 100,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ):
        """Get debug log entries."""
        return {
            "entries": logger.get_entries(limit=limit, category=category, level=level),
            "total": len(logger.entries),
        }

    @app.get("/api/debug/logs/stream", tags=["Debug"])
    async def api_debug_logs_stream():
        """Stream debug logs via SSE."""
        queue = await logger.subscribe()

        async def event_generator():
            try:
                # Send initial entries
                entries = logger.get_entries(limit=50)
                yield f"data: {json.dumps({'type': 'init', 'entries': entries})}\n\n"

                # Stream new entries
                while True:
                    try:
                        entry = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps({'type': 'new', 'entry': entry})}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield f": keepalive {datetime.now().isoformat()}\n\n"
                    except Exception:
                        break
            finally:
                await logger.unsubscribe(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.delete("/api/debug/logs", tags=["Debug"])
    async def api_debug_logs_clear():
        """Clear all debug logs."""
        logger.clear()
        return {"success": True}

    @app.get("/api/debug/stats", tags=["Debug"])
    async def api_debug_stats():
        """Get debug logger statistics."""
        entries = list(logger.entries)
        categories = {}
        levels = {}

        for entry in entries:
            cat = entry.get("category", "unknown")
            lvl = entry.get("level", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            levels[lvl] = levels.get(lvl, 0) + 1

        return {
            "total_entries": len(entries),
            "categories": categories,
            "levels": levels,
            "subscribers": len(logger.subscribers),
            "max_entries": logger.max_entries,
        }


DEBUG_PANEL_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debug Panel - API Key Manager</title>
    <style>
        :root {
            --bg: #0a0e17;
            --surface: #111827;
            --border: #1f2937;
            --text: #e5e7eb;
            --dim: #9ca3af;
            --accent: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --debug: #8b5cf6;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
            background: var(--bg);
            color: var(--text);
            font-size: 13px;
            line-height: 1.5;
        }
        .container {
            max-width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 12px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 16px;
            font-weight: 600;
            color: var(--accent);
        }
        .controls {
            display: flex;
            gap: 8px;
        }
        .btn {
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .btn:hover {
            background: var(--border);
        }
        .btn.active {
            background: var(--accent);
            border-color: var(--accent);
        }
        .filters {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 8px 16px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        .filter-group {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .filter-group label {
            color: var(--dim);
            font-size: 11px;
            text-transform: uppercase;
        }
        .filter-btn {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--dim);
            padding: 2px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
        }
        .filter-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        .stats {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 8px 16px;
            display: flex;
            gap: 24px;
            font-size: 11px;
            color: var(--dim);
        }
        .stat {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .stat-value {
            color: var(--text);
            font-weight: 600;
        }
        .log-container {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }
        .log-entry {
            padding: 6px 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 12px;
            font-size: 12px;
            cursor: pointer;
        }
        .log-entry:hover {
            background: var(--surface);
        }
        .log-entry.expanded {
            background: var(--surface);
        }
        .log-time {
            color: var(--dim);
            white-space: nowrap;
            min-width: 85px;
        }
        .log-level {
            min-width: 50px;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 10px;
            padding: 2px 4px;
            border-radius: 2px;
            text-align: center;
        }
        .log-level.DEBUG { color: var(--debug); background: rgba(139, 92, 246, 0.1); }
        .log-level.INFO { color: var(--success); background: rgba(16, 185, 129, 0.1); }
        .log-level.WARNING { color: var(--warning); background: rgba(245, 158, 11, 0.1); }
        .log-level.ERROR { color: var(--error); background: rgba(239, 68, 68, 0.1); }
        .log-category {
            color: var(--accent);
            min-width: 60px;
            font-weight: 500;
        }
        .log-action {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .log-detail {
            color: var(--dim);
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .log-source {
            color: var(--dim);
            font-size: 10px;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .log-data {
            display: none;
            margin-top: 8px;
            padding: 8px;
            background: var(--bg);
            border-radius: 4px;
            font-size: 11px;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
        }
        .log-entry.expanded .log-data {
            display: block;
        }
        .status-bar {
            background: var(--surface);
            border-top: 1px solid var(--border);
            padding: 4px 16px;
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--dim);
        }
        .connected { color: var(--success); }
        .disconnected { color: var(--error); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Debug Panel</h1>
            <div class="controls">
                <button class="btn" id="btn-clear" onclick="clearLogs()">Clear</button>
                <button class="btn" id="btn-scroll" onclick="scrollToBottom()">↓ Bottom</button>
                <button class="btn active" id="btn-auto-scroll" onclick="toggleAutoScroll()">Auto-scroll</button>
            </div>
        </div>

        <div class="filters">
            <div class="filter-group">
                <label>Level:</label>
                <button class="filter-btn active" data-level="all" onclick="setLevelFilter('all')">All</button>
                <button class="filter-btn" data-level="DEBUG" onclick="setLevelFilter('DEBUG')">Debug</button>
                <button class="filter-btn" data-level="INFO" onclick="setLevelFilter('INFO')">Info</button>
                <button class="filter-btn" data-level="WARNING" onclick="setLevelFilter('WARNING')">Warn</button>
                <button class="filter-btn" data-level="ERROR" onclick="setLevelFilter('ERROR')">Error</button>
            </div>
            <div class="filter-group">
                <label>Category:</label>
                <button class="filter-btn active" data-category="all" onclick="setCategoryFilter('all')">All</button>
            </div>
        </div>

        <div class="stats">
            <div class="stat">
                <span>Total:</span>
                <span class="stat-value" id="stat-total">0</span>
            </div>
            <div class="stat">
                <span>Visible:</span>
                <span class="stat-value" id="stat-visible">0</span>
            </div>
            <div class="stat">
                <span>Errors:</span>
                <span class="stat-value" id="stat-errors">0</span>
            </div>
            <div class="stat">
                <span>Rate:</span>
                <span class="stat-value" id="stat-rate">0/s</span>
            </div>
        </div>

        <div class="log-container" id="log-container"></div>

        <div class="status-bar">
            <div>
                <span id="connection-status" class="disconnected">● Disconnected</span>
            </div>
            <div>
                <span id="last-update">Last update: --</span>
            </div>
        </div>
    </div>

    <script>
        const state = {
            entries: [],
            levelFilter: 'all',
            categoryFilter: 'all',
            autoScroll: true,
            connected: false,
            eventSource: null,
            categories: new Set(),
            entryCount: 0,
            errorCount: 0,
            lastMinuteEntries: [],
        };

        function formatTime(isoString) {
            const date = new Date(isoString);
            return date.toLocaleTimeString('zh-CN', { hour12: false });
        }

        function formatData(data) {
            if (!data) return '';
            try {
                return JSON.stringify(data, null, 2);
            } catch {
                return String(data);
            }
        }

        function shouldShow(entry) {
            if (state.levelFilter !== 'all' && entry.level !== state.levelFilter) return false;
            if (state.categoryFilter !== 'all' && entry.category !== state.categoryFilter) return false;
            return true;
        }

        function renderEntry(entry) {
            if (!shouldShow(entry)) return '';

            return `
                <div class="log-entry" data-id="${entry.id}" onclick="toggleExpand(this)">
                    <span class="log-time">${formatTime(entry.timestamp)}</span>
                    <span class="log-level ${entry.level}">${entry.level}</span>
                    <span class="log-category">${entry.category}</span>
                    <span class="log-action">${entry.action}</span>
                    <span class="log-detail">${entry.detail || ''}</span>
                    <span class="log-source">${entry.source || ''}</span>
                    <div class="log-data">${formatData(entry.data)}</div>
                </div>
            `;
        }

        function updateStats() {
            const now = Date.now();
            state.lastMinuteEntries = state.lastMinuteEntries.filter(t => now - t < 60000);

            document.getElementById('stat-total').textContent = state.entries.length;
            document.getElementById('stat-visible').textContent = document.querySelectorAll('.log-entry').length;
            document.getElementById('stat-errors').textContent = state.errorCount;
            document.getElementById('stat-rate').textContent = (state.lastMinuteEntries.length / 60).toFixed(1) + '/s';
        }

        function updateCategories() {
            const container = document.querySelector('.filter-group:last-child');
            const existingButtons = container.querySelectorAll('.filter-btn:not([data-category="all"])');
            existingButtons.forEach(btn => btn.remove());

            state.categories.forEach(cat => {
                const btn = document.createElement('button');
                btn.className = 'filter-btn';
                btn.dataset.category = cat;
                btn.textContent = cat;
                btn.onclick = () => setCategoryFilter(cat);
                container.appendChild(btn);
            });
        }

        function addEntry(entry) {
            state.entries.push(entry);
            state.entryCount++;
            state.lastMinuteEntries.push(Date.now());
            state.categories.add(entry.category);

            if (entry.level === 'ERROR') state.errorCount++;

            if (shouldShow(entry)) {
                const container = document.getElementById('log-container');
                container.insertAdjacentHTML('beforeend', renderEntry(entry));

                if (state.autoScroll) {
                    scrollToBottom();
                }
            }

            updateStats();
            updateCategories();
        }

        function toggleExpand(element) {
            element.classList.toggle('expanded');
        }

        function scrollToBottom() {
            const container = document.getElementById('log-container');
            container.scrollTop = container.scrollHeight;
        }

        function toggleAutoScroll() {
            state.autoScroll = !state.autoScroll;
            document.getElementById('btn-auto-scroll').classList.toggle('active', state.autoScroll);
        }

        function setLevelFilter(level) {
            state.levelFilter = level;
            document.querySelectorAll('[data-level]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.level === level);
            });
            renderAll();
        }

        function setCategoryFilter(category) {
            state.categoryFilter = category;
            document.querySelectorAll('[data-category]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.category === category);
            });
            renderAll();
        }

        function renderAll() {
            const container = document.getElementById('log-container');
            container.innerHTML = state.entries.map(renderAll).join('');
            updateStats();
        }

        async function clearLogs() {
            try {
                await fetch('/api/debug/logs', { method: 'DELETE' });
                state.entries = [];
                state.entryCount = 0;
                state.errorCount = 0;
                state.lastMinuteEntries = [];
                document.getElementById('log-container').innerHTML = '';
                updateStats();
            } catch (err) {
                console.error('Failed to clear logs:', err);
            }
        }

        function connectSSE() {
            if (state.eventSource) {
                state.eventSource.close();
            }

            state.eventSource = new EventSource('/api/debug/logs/stream');

            state.eventSource.onopen = () => {
                state.connected = true;
                document.getElementById('connection-status').className = 'connected';
                document.getElementById('connection-status').textContent = '● Connected';
            };

            state.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'init') {
                        state.entries = data.entries || [];
                        state.entries.forEach(entry => {
                            state.categories.add(entry.category);
                            if (entry.level === 'ERROR') state.errorCount++;
                        });
                        renderAll();
                    } else if (data.type === 'new') {
                        addEntry(data.entry);
                    }

                    document.getElementById('last-update').textContent = 
                        'Last update: ' + new Date().toLocaleTimeString('zh-CN');
                } catch (err) {
                    console.error('Failed to parse SSE data:', err);
                }
            };

            state.eventSource.onerror = () => {
                state.connected = false;
                document.getElementById('connection-status').className = 'disconnected';
                document.getElementById('connection-status').textContent = '● Disconnected';

                // Reconnect after delay
                setTimeout(connectSSE, 3000);
            };
        }

        // Initialize
        connectSSE();
    </script>
</body>
</html>
"""


def setup_debug_panel(app: FastAPI):
    """Setup debug panel HTML route."""

    @app.get("/debug", response_class=HTMLResponse, include_in_schema=False)
    async def debug_panel():
        """Serve the debug panel HTML."""
        return DEBUG_PANEL_HTML


def init_debug(app: FastAPI):
    """Initialize the debug system for a FastAPI app."""
    # Setup middleware
    app.add_middleware(DebugMiddleware, logger=debug_logger)

    # Setup routes
    setup_debug_routes(app, debug_logger)
    setup_debug_panel(app)

    return debug_logger
