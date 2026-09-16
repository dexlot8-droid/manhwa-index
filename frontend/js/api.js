/**
 * API client for Manhwa Index frontend.
 * For local dev: talks directly to FastAPI backend on same origin.
 */

async function fetchJSON(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        console.error('API fetch failed:', err);
        return null;
    }
}

// --- Public API (FastAPI) ---

async function getAllSeries() {
    return await fetchJSON('/api/series');
}

async function getSeries(seriesId) {
    return await fetchJSON('/api/series/' + seriesId);
}

async function getChapter(chapterId) {
    return await fetchJSON('/api/chapter/' + chapterId);
}

async function getStats() {
    return await fetchJSON('/api/stats');
}
