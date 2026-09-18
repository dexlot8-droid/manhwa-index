/**
 * API client & State Storage for Manhwa Index frontend.
 * Talks to Cloudflare Worker proxy reading from Cloudflare KV.
 */

// Universal API Base resolution:
// 1. Explicit window override if specified
// 2. Relative if hosted directly on workers.dev
// 3. Defaults to the live worker proxy for all other domains, pages.dev, localhost, and file://
const API_BASE = (typeof window !== 'undefined' && window.MANHWA_API_BASE)
    ? window.MANHWA_API_BASE
    : (self.location.hostname.includes('workers.dev') ? '' : 'https://manhwa-kv-proxy.dexlot8.workers.dev');

// In-memory cache to eliminate redundant network roundtrips
const memoryCache = {
    allSeries: null,
    series: new Map(),
    chapters: new Map(),
    pendingRequests: new Map()
};

/**
 * Robust JSON fetcher with request deduplication
 */
async function fetchJSON(endpoint) {
    const url = API_BASE + endpoint;
    
    // Deduplicate in-flight promises
    if (memoryCache.pendingRequests.has(url)) {
        return memoryCache.pendingRequests.get(url);
    }

    const fetchPromise = (async () => {
        try {
            const res = await fetch(url, {
                headers: { 'Accept': 'application/json' },
                mode: 'cors'
            });
            if (!res.ok) {
                console.warn(`[API] HTTP ${res.status} for ${endpoint}`);
                return null;
            }
            return await res.json();
        } catch (err) {
            console.error(`[API] Fetch failed for ${endpoint}:`, err);
            return null;
        } finally {
            memoryCache.pendingRequests.delete(url);
        }
    })();

    memoryCache.pendingRequests.set(url, fetchPromise);
    return fetchPromise;
}

// --- Public API ---

async function getAllSeries(forceRefresh = false) {
    if (!forceRefresh && memoryCache.allSeries) {
        return memoryCache.allSeries;
    }
    const data = await fetchJSON('/all_series');
    if (data && data.series) {
        memoryCache.allSeries = data;
    }
    return data;
}

async function getSeries(slug, forceRefresh = false) {
    if (!forceRefresh && memoryCache.series.has(slug)) {
        return memoryCache.series.get(slug);
    }
    const data = await fetchJSON('/series:' + encodeURIComponent(slug));
    if (data && data.title) {
        // Normalize chapters list sorting (ascending by chapter number)
        if (Array.isArray(data.chapters)) {
            data.chapters.sort((a, b) => {
                const numA = parseFloat(a.number) || 0;
                const numB = parseFloat(b.number) || 0;
                return numA - numB;
            });
        }
        memoryCache.series.set(slug, data);
    }
    return data;
}

async function getChapterList(seriesId) {
    return await fetchJSON('/chapters:' + seriesId);
}

async function getChapter(chapterId, forceRefresh = false) {
    const key = String(chapterId);
    if (!forceRefresh && memoryCache.chapters.has(key)) {
        return memoryCache.chapters.get(key);
    }
    const data = await fetchJSON('/chapter:' + encodeURIComponent(key));
    if (data && data.image_urls) {
        memoryCache.chapters.set(key, data);
    }
    return data;
}

async function getPopular() {
    return await fetchJSON('/popular');
}

// --- Reading History & Bookmarks (LocalStorage) ---

const STORAGE_KEY_HISTORY = 'manhwa_reading_history_v1';
const STORAGE_KEY_BOOKMARKS = 'manhwa_bookmarks_v1';
const STORAGE_KEY_SETTINGS = 'manhwa_reader_settings_v1';

const StorageService = {
    getHistory() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || '{}');
        } catch {
            return {};
        }
    },

    saveHistory(slug, chNum, seriesData, chTitle) {
        try {
            const history = this.getHistory();
            const existing = history[slug] || { readChapters: [] };
            const readChapters = new Set(existing.readChapters || []);
            readChapters.add(chNum);

            history[slug] = {
                slug,
                lastChapterNum: chNum,
                lastChapterTitle: chTitle || `Chapter ${chNum}`,
                seriesTitle: seriesData ? seriesData.title : (existing.seriesTitle || slug),
                coverUrl: seriesData ? seriesData.cover_url : (existing.coverUrl || ''),
                updatedAt: Date.now(),
                readChapters: Array.from(readChapters)
            };

            localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
        } catch (e) {
            console.error('Failed to save reading history', e);
        }
    },

    getSeriesProgress(slug) {
        const history = this.getHistory();
        return history[slug] || null;
    },

    isChapterRead(slug, chNum) {
        const progress = this.getSeriesProgress(slug);
        if (!progress || !progress.readChapters) return false;
        return progress.readChapters.includes(chNum);
    },

    getBookmarks() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY_BOOKMARKS) || '[]');
        } catch {
            return [];
        }
    },

    isBookmarked(slug) {
        const list = this.getBookmarks();
        return list.some(b => b.slug === slug);
    },

    toggleBookmark(series) {
        try {
            let list = this.getBookmarks();
            const exists = list.some(b => b.slug === series.slug);
            if (exists) {
                list = list.filter(b => b.slug !== series.slug);
            } else {
                list.unshift({
                    slug: series.slug,
                    title: series.title,
                    cover_url: series.cover_url,
                    chapter_count: series.chapter_count || (series.chapters ? series.chapters.length : 0),
                    savedAt: Date.now()
                });
            }
            localStorage.setItem(STORAGE_KEY_BOOKMARKS, JSON.stringify(list));
            return !exists;
        } catch {
            return false;
        }
    },

    getSettings() {
        try {
            return Object.assign({
                readerWidth: '850px', // '650px', '850px', '1100px', '100%'
                gap: '0px',           // '0px' (seamless webtoon) or '10px'
                direction: 'vertical'
            }, JSON.parse(localStorage.getItem(STORAGE_KEY_SETTINGS) || '{}'));
        } catch {
            return { readerWidth: '850px', gap: '0px', direction: 'vertical' };
        }
    },

    saveSettings(settings) {
        try {
            const current = this.getSettings();
            const updated = Object.assign(current, settings);
            localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(updated));
            return updated;
        } catch (e) {
            console.error('Failed to save settings', e);
        }
    }
};
