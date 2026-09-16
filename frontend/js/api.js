/**
 * API client for Manhwa Index frontend.
 * In production: talks to Cloudflare Worker which reads from KV.
 */

const API_BASE = self.location.hostname.includes('pages.dev') 
    ? 'https://manhwa-kv-proxy.dexlot8.workers.dev' 
    : '';

async function fetchJSON(url) {
    try {
        const res = await fetch(API_BASE + url);
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        console.error('API fetch failed:', err);
        return null;
    }
}

// --- Public API ---

async function getAllSeries() {
    return await fetchJSON('/all_series');
}

async function getSeries(slug) {
    return await fetchJSON('/series:' + slug);
}

async function getChapterList(seriesId) {
    return await fetchJSON('/chapters:' + seriesId);
}

async function getChapter(chapterId) {
    return await fetchJSON('/chapter:' + chapterId);
}

async function getPopular() {
    return await fetchJSON('/popular');
}
