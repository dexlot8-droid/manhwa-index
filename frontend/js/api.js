/**
 * API client & State Storage for Manhwa Index frontend.
 * Talks to Cloudflare Worker proxy reading from Cloudflare KV.
 * Uses bundled series format: all chapters inside series:X value.
 */

const API_BASE = (typeof window !== "undefined" && window.MANHWA_API_BASE)
    ? window.MANHWA_API_BASE
    : (self.location.hostname.includes("workers.dev") ? "" : "https://manhwa-kv-proxy.dexlot8.workers.dev");

// In-memory cache
const memoryCache = {
    allSeries: null,
    series: new Map(),
    pendingRequests: new Map()
};

async function fetchJSON(endpoint) {
    const url = API_BASE + endpoint;
    
    if (memoryCache.pendingRequests.has(url)) {
        return memoryCache.pendingRequests.get(url);
    }

    const fetchPromise = (async () => {
        try {
            const res = await fetch(url, {
                headers: { "Accept": "application/json" },
                mode: "cors"
            });
            if (!res.ok) {
                console.warn("[API] HTTP " + res.status + " for " + endpoint);
                return null;
            }
            return await res.json();
        } catch (err) {
            console.error("[API] Fetch failed for " + endpoint + ":", err);
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
    const data = await fetchJSON("/all_series");
    if (data && data.series) {
        memoryCache.allSeries = data;
    }
    return data;
}

async function getSeries(slug, forceRefresh = false) {
    if (!forceRefresh && memoryCache.series.has(slug)) {
        return memoryCache.series.get(slug);
    }
    const data = await fetchJSON("/series:" + encodeURIComponent(slug));
    if (data && data.title) {
        // Sort chapters ascending by number
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

async function getChapterBySlugAndNumber(slug, chapterNumber) {
    // Get bundled series data, find chapter by number
    const seriesData = await getSeries(slug);
    if (!seriesData || !Array.isArray(seriesData.chapters)) {
        return null;
    }
    const chNum = parseFloat(chapterNumber);
    const chapter = seriesData.chapters.find(ch => parseFloat(ch.number) === chNum);
    return chapter || null;
}

async function getChapterById(chapterId) {
    // Search across all cached series for this chapter ID
    for (const [slug, seriesData] of memoryCache.series.entries()) {
        if (seriesData.chapters) {
            const ch = seriesData.chapters.find(c => c.id == chapterId);
            if (ch) return ch;
        }
    }
    console.warn("Chapter " + chapterId + " not found in cache");
    return null;
}

async function getPopular() {
    return await fetchJSON("/popular");
}

// --- Reading History & Bookmarks (LocalStorage) ---

const STORAGE_KEY_HISTORY = "manhwa_reading_history_v1";
const STORAGE_KEY_BOOKMARKS = "manhwa_bookmarks_v1";
const STORAGE_KEY_SETTINGS = "manhwa_reader_settings_v1";

const StorageService = {
    getHistory() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || "{}");
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
                lastChapterTitle: chTitle || "Chapter " + chNum,
                seriesTitle: seriesData ? seriesData.title : (existing.seriesTitle || slug),
                coverUrl: seriesData ? seriesData.cover_url : (existing.coverUrl || ""),
                updatedAt: Date.now(),
                readChapters: Array.from(readChapters)
            };

            localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
        } catch (e) {
            console.error("Failed to save reading history", e);
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
            return JSON.parse(localStorage.getItem(STORAGE_KEY_BOOKMARKS) || "[]");
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
                readerWidth: "850px",
                gap: "0px",
                direction: "vertical"
            }, JSON.parse(localStorage.getItem(STORAGE_KEY_SETTINGS) || "{}"));
        } catch {
            return { readerWidth: "850px", gap: "0px", direction: "vertical" };
        }
    },

    saveSettings(settings) {
        try {
            const current = this.getSettings();
            const updated = Object.assign(current, settings);
            localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(updated));
            return updated;
        } catch (e) {
            console.error("Failed to save settings", e);
        }
    }
};
