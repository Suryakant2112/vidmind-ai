/**
 * VidMind — Frontend Logic
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

    // Convert ⏱ MM:SS or HH:MM:SS (as written by the LLM) into clickable timestamps
    if (state.videoId) {
        html = html.replace(/⏱️?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?/g, (_, p1, p2, p3) => {
            const secs = p3
                ? parseInt(p1) * 3600 + parseInt(p2) * 60 + parseInt(p3)
                : parseInt(p1) * 60 + parseInt(p2);
            const display = p3 ? `${p1}:${p2}:${p3}` : `${p1}:${p2}`;
            return tsButton(secs, display);
        });
    }

    // Also convert any remaining YouTube timestamp links to in-page seeks
    if (state.videoId) {
        html = html.replace(
            /<a\s+href="https?:\/\/(?:www\.)?youtube\.com\/watch\?v=[^"]*?&t=(\d+)s?"[^>]*>(.*?)<\/a>/g,
            (_, secs, text) => tsButton(parseInt(secs), text)
        );
    }

    return html;
}

function tsButton(secs, label) {
    return `<button type="button" class="ts" onclick="seekVideo(${secs})" title="Jump the video to ${label}">${label}</button>`;
}

// ─── API Helpers ─────────────────────────────────────────────────────────────

// Turn an error response into an Error. Structured details ({code, message})
// keep their code so callers can react (e.g. offer the paste-transcript box).
async function apiError(res) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = body.detail;
    const err = new Error(
        (typeof detail === 'object' && detail?.message) || (typeof detail === 'string' && detail) || `Error ${res.status}`
    );
    if (typeof detail === 'object') err.code = detail?.code;
    return err;
}

async function apiPost(path, data = {}) {
    const res = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw await apiError(res);
    return res.json();
}

async function apiGet(path) {
    const res = await fetch(API + path);
    if (!res.ok) throw await apiError(res);
    return res.json();
}

// ─── Process Video ───────────────────────────────────────────────────────────

async function processVideo() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) return showError('Please paste a YouTube URL.');
    const pasteOpen = document.getElementById('pasteBox').classList.contains('show');
    const transcript = pasteOpen ? document.getElementById('transcriptInput').value.trim() : '';

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
        const result = await apiPost('/video/process', transcript ? { url, transcript } : { url });
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
        toast('Ready. The summary is being written now.');
    } catch (err) {
        clearInterval(crawl);
        bar.classList.remove('progress-bar--shimmer');
        fill.style.width = '0%';
        if (err.code === 'transcript_unavailable') {
            showPasteBox();
            showError(`${err.message} YouTube may be blocking this server. Paste the transcript below and press Make notes again.`);
        } else {
            showError(err.message);
        }
        screen.classList.remove('show');
        document.getElementById('landing').style.display = '';
    } finally {
        state.processing = false;
        setBtnLoading(false);
    }
}

function togglePasteBox() {
    const box = document.getElementById('pasteBox');
    box.classList.contains('show') ? hidePasteBox() : showPasteBox();
}

function showPasteBox() {
    document.getElementById('pasteBox').classList.add('show');
    document.getElementById('pasteToggle').textContent = 'Hide the transcript box';
    document.getElementById('transcriptInput').focus();
}

function hidePasteBox() {
    document.getElementById('pasteBox').classList.remove('show');
    document.getElementById('pasteToggle').textContent = 'No captions coming through? Paste the transcript instead';
}

function setBtnLoading(on) {
    const btn = document.getElementById('processBtn');
    const inp = document.getElementById('urlInput');
    btn.disabled = on;
    inp.disabled = on;
    document.getElementById('transcriptInput').disabled = on;
    btn.textContent = on ? 'Working…' : 'Make notes';
}

// ─── Results Display ─────────────────────────────────────────────────────────

function showResults(info) {
    document.getElementById('processingScreen').classList.remove('show');
    document.getElementById('results').classList.add('show');
    document.getElementById('newVideoBtn').style.display = '';

    // Create embedded YouTube player
    createPlayer(info.video_id);

    const meta = [];
    if (info.duration_seconds) meta.push(`${fmtDur(info.duration_seconds)} long`);
    if (info.transcript_segments) meta.push(`${info.transcript_segments} caption lines`);
    if (info.chunk_count) meta.push(`${info.chunk_count} passages indexed`);
    document.getElementById('videoMeta').innerHTML = meta.map(m => `<span>${m}</span>`).join('');

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
    body.innerHTML = loaderHtml('Writing the summary');

    try {
        const r = await apiGet(`/video/${state.videoId}/summary`);
        state.summaryMd = r.summary;
        state.summaryLoaded = true;
        body.innerHTML = renderMd(r.summary);
    } catch (e) {
        body.innerHTML = `<p class="error-text">Couldn't write the summary: ${esc(e.message)}</p>`;
    }
}

function copySummary() {
    if (state.summaryMd) { copy(state.summaryMd); toast('Summary copied'); }
}

// ─── Notes ───────────────────────────────────────────────────────────────────

async function loadNotes() {
    if (!state.videoId) return;
    const body = document.getElementById('notesBody');
    body.innerHTML = loaderHtml('Writing your notes. Long lectures can take a minute');

    try {
        const r = await apiGet(`/video/${state.videoId}/notes`);
        state.notesMd = r.notes;
        state.notesLoaded = true;
        body.innerHTML = renderMd(r.notes);
    } catch (e) {
        body.innerHTML = `<p class="error-text">Couldn't write the notes: ${esc(e.message)}</p>`;
    }
}

function copyNotes() {
    if (state.notesMd) { copy(state.notesMd); toast('Notes copied'); }
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
    toast('Notes downloaded');
}

// ─── Chat ────────────────────────────────────────────────────────────────────

async function askQuestion() {
    if (state.asking || !state.videoId) return;
    const inp = document.getElementById('chatInput');
    const q = inp.value.trim();
    if (!q) return;

    document.getElementById('chatWelcome')?.remove();

    appendQuestion(q);
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
        appendAnswer(r.answer, r.sources);
        state.history.push({ role: 'user', content: q }, { role: 'assistant', content: r.answer });
        if (state.history.length > 12) state.history = state.history.slice(-12);
    } catch (e) {
        removeEl(typingId);
        appendAnswer(null, [], `Couldn't answer that: ${e.message}`);
    } finally {
        state.asking = false;
        document.getElementById('sendBtn').disabled = false;
        inp.focus();
    }
}

function appendQuestion(text) {
    const box = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'qa qa--q';
    div.innerHTML = `<div class="qa__line"><span class="qa__mark">Q.</span><div class="qa__text">${esc(text)}</div></div>`;
    box.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// The answer is placed inside the latest question block so each Q/A pair stays together
function lastQuestionBlock() {
    const box = document.getElementById('chatMessages');
    return box.lastElementChild?.classList.contains('qa--q') ? box.lastElementChild : box;
}

function appendAnswer(markdown, sources = [], errorText = '') {
    const body = errorText
        ? `<div class="qa__error">${esc(errorText)}</div>`
        : `<div class="md">${renderMd(markdown)}</div>`;

    let srcHtml = '';
    if (sources?.length) {
        const refs = sources.map(s => {
            const match = s.youtube_url?.match(/[&?]t=(\d+)/);
            return tsButton(match ? parseInt(match[1]) : 0, s.timestamp_display);
        }).join(' · ');
        srcHtml = `<div class="sources"><span class="sources__title">From the video at</span>${refs}</div>`;
    }

    const div = document.createElement('div');
    div.className = 'qa--a';
    div.innerHTML = `<div class="qa__line"><span class="qa__mark">A.</span><div class="qa__text">${body}</div></div>${srcHtml}`;
    lastQuestionBlock().appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function appendTyping() {
    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'qa--a';
    div.innerHTML = `<div class="qa__line"><span class="qa__mark">A.</span><div class="loader" style="padding:0">Looking through the transcript<span class="caret"></span></div></div>`;
    lastQuestionBlock().appendChild(div);
    return id;
}

function chatWelcomeHtml() {
    const examples = [
        'What are the main ideas, in order?',
        'Explain the hardest part more simply.',
        'What examples were given?',
    ];
    return `<div class="chat__welcome" id="chatWelcome">
        <div class="chat__welcome-title">Ask about anything that was said.</div>
        Answers are drawn only from the transcript, with timestamps so you can check them yourself.
        <div class="chat__examples">
            ${examples.map(q => `<button class="text-link" onclick="askExample(this.textContent)">${q}</button>`).join('')}
        </div>
    </div>`;
}

function askExample(text) {
    document.getElementById('chatInput').value = text;
    askQuestion();
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
    document.getElementById('transcriptInput').value = '';
    document.getElementById('transcriptInput').disabled = false;
    hidePasteBox();
    document.getElementById('processBtn').disabled = false;
    document.getElementById('processBtn').textContent = 'Make notes';

    document.getElementById('summaryBody').innerHTML = '';
    document.getElementById('notesBody').innerHTML = '';
    document.getElementById('videoMeta').innerHTML = '';
    document.getElementById('chatMessages').innerHTML = chatWelcomeHtml();
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
    return `<div class="loader">${msg}<span class="caret"></span></div>`;
}

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('newVideoBtn').style.display = 'none';
    document.getElementById('chatMessages').innerHTML = chatWelcomeHtml();
    document.getElementById('urlInput').focus();
});
