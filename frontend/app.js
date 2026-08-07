/**
 * VidMind AI — Frontend Logic
 * Handles processing, mode switching, content display, chat,
 * embedded YouTube player, and in-page timestamp seeking.
 */

// ─── State ───────────────────────────────────────────────────────────────────

const state = {
    videoId: null,
    summaryMd: null,
    notesMd: null,
    summaryLoaded: false,
    notesLoaded: false,
    history: [],
    processing: false,
    asking: false,
};

const API = '/api';
let ytPlayer = null;       // YouTube IFrame Player instance
let ytPlayerReady = false;  // Whether the player API is ready

// ─── YouTube IFrame API ──────────────────────────────────────────────────────

// This global callback is called by the YouTube IFrame API when it's ready.
function onYouTubeIframeAPIReady() {
    // API is loaded. Player is created later when we have a video ID.
}

/**
 * Create / replace the embedded YouTube player for the given video ID.
 */
function createPlayer(videoId) {
    ytPlayerReady = false;

    // Destroy existing player if any
    const container = document.getElementById('ytPlayer');
    container.innerHTML = '';

    ytPlayer = new YT.Player('ytPlayer', {
        videoId: videoId,
        playerVars: {
            autoplay: 0,
            modestbranding: 1,
            rel: 0,
            fs: 1,
        },
        events: {
            onReady: () => { ytPlayerReady = true; },
        },
    });
}

/**
 * Seek the embedded YouTube player to the given seconds.
 * Scrolls the player into view and starts playback.
 */
function seekVideo(seconds) {
    if (ytPlayer && ytPlayerReady) {
        ytPlayer.seekTo(seconds, true);
        ytPlayer.playVideo();
        // Scroll the player into view
        document.getElementById('videoEmbed').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ─── Markdown ────────────────────────────────────────────────────────────────

if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

function renderMd(md) {
    if (!md) return '';
    let html = typeof marked !== 'undefined' ? marked.parse(md) : md;

    // Convert ⏱ MM:SS or HH:MM:SS into clickable in-page timestamp links
    if (state.videoId) {
        html = html.replace(/⏱\s*(\d{1,2}):(\d{2})(?::(\d{2}))?/g, (_, p1, p2, p3) => {
            const secs = p3
                ? parseInt(p1) * 3600 + parseInt(p2) * 60 + parseInt(p3)
                : parseInt(p1) * 60 + parseInt(p2);
            const display = p3 ? `${p1}:${p2}:${p3}` : `${p1}:${p2}`;
            return `<span class="ts-link" onclick="seekVideo(${secs})">⏱ ${display}</span>`;
        });
    }

    // Also convert any remaining YouTube timestamp links to in-page seeks
    if (state.videoId) {
        html = html.replace(
            /<a\s+href="https?:\/\/(?:www\.)?youtube\.com\/watch\?v=[^"]*?&t=(\d+)s?"[^>]*>(.*?)<\/a>/g,
            (_, secs, text) => `<span class="ts-link" onclick="seekVideo(${secs})">${text}</span>`
        );
    }

    return html;
}

// ─── API Helpers ─────────────────────────────────────────────────────────────

async function apiPost(path, data = {}) {
    const res = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

async function apiGet(path) {
    const res = await fetch(API + path);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

// ─── Process Video ───────────────────────────────────────────────────────────

async function processVideo() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) return showError('Please paste a YouTube URL.');

    hideError();
    state.processing = true;
    setBtnLoading(true);

    // Show processing screen, hide landing
    document.getElementById('landing').style.display = 'none';
    document.getElementById('results').classList.remove('show');
    const screen = document.getElementById('processingScreen');
    screen.classList.add('show');

    // Start progress bar animation
    const fill = document.getElementById('progressFill');
    const bar = fill.parentElement;
    fill.style.width = '0%';
    bar.classList.remove('progress-bar--shimmer');

    // Animate progress bar: fast to 30%, then slow crawl to 85%, then shimmer
    await sleep(100);
    fill.style.width = '30%';
    const crawl = setInterval(() => {
        const current = parseFloat(fill.style.width);
        if (current < 85) {
            fill.style.width = (current + 0.5) + '%';
        } else {
            clearInterval(crawl);
            bar.classList.add('progress-bar--shimmer');
        }
    }, 300);

    try {
        const result = await apiPost('/video/process', { url });
        clearInterval(crawl);

        // Complete the bar
        bar.classList.remove('progress-bar--shimmer');
        fill.style.width = '100%';

        state.videoId = result.video_info.video_id;
        state.summaryLoaded = false;
        state.notesLoaded = false;
        state.history = [];

        await sleep(500);
        showResults(result.video_info);
        toast('Video processed — choose a mode above.');
    } catch (err) {
        clearInterval(crawl);
        bar.classList.remove('progress-bar--shimmer');
        fill.style.width = '0%';
        showError(err.message);
        screen.classList.remove('show');
        document.getElementById('landing').style.display = '';
    } finally {
        state.processing = false;
        setBtnLoading(false);
    }
}

function setBtnLoading(on) {
    const btn = document.getElementById('processBtn');
    const inp = document.getElementById('urlInput');
    btn.disabled = on;
    inp.disabled = on;
    btn.textContent = on ? 'Processing...' : 'Process →';
}

// ─── Results Display ─────────────────────────────────────────────────────────

function showResults(info) {
    document.getElementById('processingScreen').classList.remove('show');
    document.getElementById('results').classList.add('show');
    document.getElementById('newVideoBtn').style.display = '';

    // Create embedded YouTube player
    createPlayer(info.video_id);

    switchMode('summary');
}

// ─── Mode Switching ──────────────────────────────────────────────────────────

function switchMode(mode) {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('show'));
    const panel = mode === 'summary' ? 'panelSummary' : mode === 'notes' ? 'panelNotes' : 'panelAsk';
    document.getElementById(panel).classList.add('show');

    if (mode === 'summary' && !state.summaryLoaded) loadSummary();
    if (mode === 'notes' && !state.notesLoaded) loadNotes();
    if (mode === 'ask') document.getElementById('chatInput')?.focus();
}

// ─── Summary ─────────────────────────────────────────────────────────────────

async function loadSummary() {
    if (!state.videoId) return;
    const body = document.getElementById('summaryBody');
    body.innerHTML = loaderHtml('Generating summary...');

    try {
        const r = await apiGet(`/video/${state.videoId}/summary`);
        state.summaryMd = r.summary;
        state.summaryLoaded = true;
        body.innerHTML = renderMd(r.summary);
        if (r.cached) toast('Loaded cached summary.');
    } catch (e) {
        body.innerHTML = `<p style="color:var(--error)">Failed: ${e.message}</p>`;
    }
}

function copySummary() {
    if (state.summaryMd) { copy(state.summaryMd); toast('Summary copied!'); }
}

// ─── Notes ───────────────────────────────────────────────────────────────────

async function loadNotes() {
    if (!state.videoId) return;
    const body = document.getElementById('notesBody');
    body.innerHTML = loaderHtml('Generating lecture notes...');

    try {
        const r = await apiGet(`/video/${state.videoId}/notes`);
        state.notesMd = r.notes;
        state.notesLoaded = true;
        body.innerHTML = renderMd(r.notes);
        if (r.cached) toast('Loaded cached notes.');
    } catch (e) {
        body.innerHTML = `<p style="color:var(--error)">Failed: ${e.message}</p>`;
    }
}

function copyNotes() {
    if (state.notesMd) { copy(state.notesMd); toast('Notes copied!'); }
}

function downloadNotes() {
    if (!state.notesMd) return;
    const blob = new Blob([state.notesMd], { type: 'text/markdown;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `lecture_notes_${state.videoId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    toast('Notes downloaded!');
}

// ─── Chat ────────────────────────────────────────────────────────────────────

async function askQuestion() {
    if (state.asking || !state.videoId) return;
    const inp = document.getElementById('chatInput');
    const q = inp.value.trim();
    if (!q) return;

    const welcome = document.getElementById('chatWelcome');
    if (welcome) welcome.style.display = 'none';

    appendMsg('user', q);
    inp.value = '';
    const typingId = appendTyping();

    state.asking = true;
    document.getElementById('sendBtn').disabled = true;

    try {
        const r = await apiPost(`/video/${state.videoId}/ask`, {
            question: q,
            conversation_history: state.history,
        });
        removeEl(typingId);
        appendMsg('ai', r.answer, r.sources);
        state.history.push({ role: 'user', content: q }, { role: 'assistant', content: r.answer });
        if (state.history.length > 12) state.history = state.history.slice(-12);
    } catch (e) {
        removeEl(typingId);
        appendMsg('ai', `Sorry, an error occurred: ${e.message}`);
    } finally {
        state.asking = false;
        document.getElementById('sendBtn').disabled = false;
        inp.focus();
    }
}

function appendMsg(role, content, sources = []) {
    const box = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `msg msg--${role}`;

    const avatar = role === 'user' ? '👤' : '▶';
    const label = role === 'user' ? 'You' : 'VidMind AI';
    const rendered = role === 'ai' ? `<div class="md">${renderMd(content)}</div>` : esc(content);

    let srcHtml = '';
    if (sources?.length) {
        const tags = sources.map(s => {
            // Extract seconds from the youtube_url (t=XXXs)
            const match = s.youtube_url?.match(/[&?]t=(\d+)/);
            const secs = match ? parseInt(match[1]) : 0;
            return `<span class="source-tag" onclick="seekVideo(${secs})">⏱ ${s.timestamp_display}</span>`;
        }).join('');
        srcHtml = `<div class="sources"><div class="sources__title">Sources</div><div class="sources__list">${tags}</div></div>`;
    }

    div.innerHTML = `<div class="msg__inner">
        <div class="msg__avatar">${avatar}</div>
        <div class="msg__body">
            <div class="msg__role">${label}</div>
            <div class="msg__text">${rendered}</div>
            ${srcHtml}
        </div>
    </div>`;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function appendTyping() {
    const box = document.getElementById('chatMessages');
    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'msg msg--ai';
    div.innerHTML = `<div class="msg__inner">
        <div class="msg__avatar">▶</div>
        <div class="msg__body">
            <div class="msg__role">VidMind AI</div>
            <div class="msg__text"><div class="loader__dots"><span></span><span></span><span></span></div></div>
        </div>
    </div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return id;
}

// ─── Reset ───────────────────────────────────────────────────────────────────

function resetApp() {
    Object.assign(state, { videoId: null, summaryMd: null, notesMd: null, summaryLoaded: false, notesLoaded: false, history: [] });

    // Destroy YouTube player
    if (ytPlayer && typeof ytPlayer.destroy === 'function') {
        ytPlayer.destroy();
        ytPlayer = null;
        ytPlayerReady = false;
    }
    document.getElementById('ytPlayer').innerHTML = '';

    document.getElementById('results').classList.remove('show');
    document.getElementById('processingScreen').classList.remove('show');
    document.getElementById('landing').style.display = '';
    document.getElementById('newVideoBtn').style.display = 'none';
    document.getElementById('urlInput').value = '';
    document.getElementById('urlInput').disabled = false;
    document.getElementById('processBtn').disabled = false;
    document.getElementById('processBtn').textContent = 'Process →';

    document.getElementById('summaryBody').innerHTML = loaderHtml('Generating summary...');
    document.getElementById('notesBody').innerHTML = loaderHtml('Generating lecture notes...');
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat__welcome" id="chatWelcome">
            <div class="chat__welcome-icon">💬</div>
            <div class="chat__welcome-title">Ask anything about this video</div>
            <div class="chat__welcome-hint">Answers are grounded in the video's transcript</div>
        </div>`;
    switchMode('summary');
    hideError();
    document.getElementById('urlInput').focus();
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function showError(msg) {
    const bar = document.getElementById('errorBar');
    document.getElementById('errorText').textContent = msg;
    bar.classList.add('show');
}

function hideError() { document.getElementById('errorBar').classList.remove('show'); }

function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

function copy(text) {
    navigator.clipboard?.writeText(text) || (() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    })();
}

function fmtDur(s) {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
    return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function removeEl(id) { document.getElementById(id)?.remove(); }
function loaderHtml(msg) {
    return `<div class="loader"><div class="loader__dots"><span></span><span></span><span></span></div>${msg}</div>`;
}

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('newVideoBtn').style.display = 'none';
    document.getElementById('urlInput').focus();
});
