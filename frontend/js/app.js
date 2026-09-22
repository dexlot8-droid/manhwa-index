/**
 * Dex Manhwa - High-Performance Modern Webtoon Application
 * Handles routing, views, search/filter, reader ergonomics, and persistence.
 */

let allSeries = [];
let currentSeries = null;
let activeGenre = 'All';
let searchQuery = '';
let sortOrder = 'default';
let chapterSortOrder = 'asc';
let chapterFilterQuery = '';

// Auto-hide scroll state for reader
let lastScrollY = 0;
let isNavHidden = false;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        initRouter();
        initGlobalEvents();
        await loadAllSeries();
        render();
    } catch (err) {
        console.error('[DexManhwa] Init error:', err);
        const app = document.getElementById('app');
        if (app) {
            app.innerHTML = '<div style="color:#ff4444;padding:20px;font-family:monospace">Error: ' + err.message + '<br><br>' + err.stack + '</div>';
        }
    }
});

function initRouter() {
    window.addEventListener('popstate', render);
    window.addEventListener('hashchange', render);

    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;
        
        const href = link.getAttribute('href');
        if (!href) return;
        
        if (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('//') || 
            href.startsWith('mailto:') || link.target === '_blank' ||
            e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button !== 0) {
            return;
        }

        e.preventDefault();
        navigate(href);
    });

    window.addEventListener('scroll', handleWindowScroll, { passive: true });
    window.addEventListener('keydown', handleKeyboardNav);
}

function initGlobalEvents() {
    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
    });
}

async function loadAllSeries() {
    try {
        const data = await getAllSeries();
        if (data && Array.isArray(data.series)) {
            allSeries = data.series;
        }
    } catch (err) {
        console.error('loadAllSeries error:', err);
        throw err;
    }
}

function getNormalizedPath() {
    const hash = window.location.hash;
    if (hash && hash.startsWith('#')) {
        const clean = hash.slice(1);
        return clean.startsWith('/') ? clean : '/' + clean;
    }
    const path = window.location.pathname || '/';
    return path.replace(/\/index\.html$/i, '') || '/';
}

function navigate(url) {
    let target = url;
    if (target.startsWith('#')) {
        target = target.slice(1);
    }
    if (!target.startsWith('/')) {
        target = '/' + target;
    }

    const useHash = window.location.protocol === 'file:' || window.location.hash.startsWith('#');
    if (useHash) {
        window.location.hash = '#' + target;
    } else {
        try {
            window.history.pushState({}, '', target);
            render();
        } catch {
            window.location.hash = '#' + target;
        }
    }
}

function render() {
    const path = getNormalizedPath();
    const app = document.getElementById('app');
    if (!app) return;

    // Reset reading progress bar
    const bar = document.getElementById('readingProgressBar');
    if (bar) bar.style.width = '0%';

    window.scrollTo({ top: 0, behavior: 'instant' });

    try {
        // Match: /series/:slug/chapter/:num
        const chapterMatch = path.match(/^\/series\/([^\/]+)\/chapter\/([^\/]+)/);
        if (chapterMatch) {
            const slug = decodeURIComponent(chapterMatch[1]);
            const chNum = parseFloat(chapterMatch[2]);
            renderChapterReader(app, slug, chNum);
            return;
        }

        // Match: /series/:slug
        const seriesMatch = path.match(/^\/series\/([^\/]+)\/?$/);
        if (seriesMatch) {
            const slug = decodeURIComponent(seriesMatch[1]);
            renderSeriesDetail(app, slug);
            return;
        }

        renderHome(app);
    } catch (err) {
        console.error('Render error:', err);
        app.innerHTML = '<div style="color:#ff4444;padding:20px;font-family:monospace">Render Error: ' + err.message + '<br><br>' + err.stack + '</div>';
    }
}

function renderHome(app) {
    document.title = 'Dex Manhwa - Premium Webtoon Reader';
    document.body.classList.remove('in-reader');

    const genreSet = new Set();
    allSeries.forEach(s => {
        if (Array.isArray(s.tags)) {
            s.tags.forEach(t => genreSet.add(t));
        }
    });
    const genres = ['All', ...Array.from(genreSet).sort()];

    const historyMap = StorageService.getHistory();
    const historyEntries = Object.values(historyMap)
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
        .slice(0, 4);

    // Pick top spotlight series (Nano Machine or first series)
    const spotlight = allSeries.find(s => s.slug === 'nano-machine') || allSeries[0];

    app.innerHTML = `
        ${spotlight && !searchQuery && activeGenre === 'All' ? `
            <div class="spotlight-hero">
                <div class="spotlight-bg" style="background-image: url('${proxyUrl(spotlight.cover_url)}');"></div>
                <div class="spotlight-vignette"></div>
                <div class="spotlight-content">
                    <h1 class="spotlight-title">${escapeHtml(spotlight.title)}</h1>
                    <div class="spotlight-meta">
                        <span>📖 <strong>${spotlight.chapter_count || 0}</strong> Chapters Available</span>
                        <span>•</span>
                        
                        ${(spotlight.tags || []).slice(0, 3).map(t => `<span class="badge">${escapeHtml(t)}</span>`).join('')}
                    </div>
                    <p class="spotlight-desc">
                        
                    </p>
                    <div class="spotlight-actions">
                        <a href="/series/${encodeURIComponent(spotlight.slug)}/chapter/1" class="btn btn-primary">
                            ▶ Read Chapter 1
                        </a>
                        <a href="/series/${encodeURIComponent(spotlight.slug)}" class="btn btn-secondary">
                            View Series Info
                        </a>
                    </div>
                </div>
                <div class="spotlight-cover-side">
                    <img src="${proxyUrl(spotlight.cover_url)}" alt="${escapeHtml(spotlight.title)}" class="spotlight-cover-art" referrerpolicy="no-referrer" onerror="this.src='/img/placeholder.svg'">
                </div>
            </div>
        ` : ''}

        <div class="home-controls">
            <div class="search-box-wrapper">
                <span class="search-icon">🔍</span>
                <input 
                    type="text" 
                    class="search-input" 
                    id="searchInput" 
                    value="${escapeHtml(searchQuery)}"
                    placeholder="Search manhwa by title or genre... (Press '/' to focus)" 
                    autocomplete="off"
                >
                <button class="search-clear-btn" id="searchClearBtn" title="Clear search">✕</button>
            </div>

            <div class="filter-bar">
                <div class="genre-tags">
                    ${genres.map(g => `
                        <button class="genre-chip ${activeGenre === g ? 'active' : ''}" data-genre="${escapeHtml(g)}">
                            ${escapeHtml(g)}
                        </button>
                    `).join('')}
                </div>

                <div class="sort-select-wrapper">
                    <span>Sort:</span>
                    <select class="sort-select" id="sortSelect">
                        <option value="default" ${sortOrder === 'default' ? 'selected' : ''}>Featured</option>
                        <option value="title" ${sortOrder === 'title' ? 'selected' : ''}>Alphabetical (A-Z)</option>
                        <option value="chapters" ${sortOrder === 'chapters' ? 'selected' : ''}>Most Chapters</option>
                    </select>
                </div>
            </div>
        </div>

        ${historyEntries.length > 0 ? `
            <div class="continue-reading-section">
                <div class="section-header">
                    <h2 class="section-title">⏱️ Continue Reading</h2>
                </div>
                <div class="continue-grid">
                    ${historyEntries.map(item => `
                        <a href="/series/${encodeURIComponent(item.slug)}/chapter/${item.lastChapterNum}" class="continue-card">
                            <img src="${proxyUrl(item.coverUrl)}" alt="${escapeHtml(item.seriesTitle)}" class="continue-thumb" onerror="this.src='/img/placeholder.svg'" referrerpolicy="no-referrer">
                            <div class="continue-info">
                                <div class="continue-title">${escapeHtml(item.seriesTitle)}</div>
                                <div class="continue-chapter">Resume Ch. ${item.lastChapterNum}</div>
                                <div class="continue-resume-btn">Continue ➔</div>
                            </div>
                        </a>
                    `).join('')}
                </div>
            </div>
        ` : ''}

        <div class="section-header">
            <h2 class="section-title">⚡ All Manhwa Series</h2>
            <div style="font-size: 0.85rem; color: var(--text-muted);">Showing <span id="seriesCount">${allSeries.length}</span> titles</div>
        </div>

        <div class="series-grid" id="seriesGrid">
            ${getFilteredSeriesHTML()}
        </div>
    `;

    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('searchClearBtn');
    const sortSelect = document.getElementById('sortSelect');

    if (searchInput) {
        if (searchQuery) clearBtn.style.display = 'flex';

        searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            clearBtn.style.display = searchQuery ? 'flex' : 'none';
            updateSeriesGrid();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            searchQuery = '';
            searchInput.value = '';
            clearBtn.style.display = 'none';
            searchInput.focus();
            updateSeriesGrid();
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            sortOrder = e.target.value;
            updateSeriesGrid();
        });
    }

    const genreChips = app.querySelectorAll('.genre-chip');
    genreChips.forEach(chip => {
        chip.addEventListener('click', () => {
            activeGenre = chip.dataset.genre;
            genreChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            updateSeriesGrid();
        });
    });
}

function getFilteredSeries() {
    let list = [...allSeries];

    if (activeGenre && activeGenre !== 'All') {
        list = list.filter(s => Array.isArray(s.tags) && s.tags.includes(activeGenre));
    }

    if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        list = list.filter(s => {
            const inTitle = (s.title || '').toLowerCase().includes(q);
            const inTags = Array.isArray(s.tags) && s.tags.some(t => t.toLowerCase().includes(q));
            return inTitle || inTags;
        });
    }

    if (sortOrder === 'title') {
        list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    } else if (sortOrder === 'chapters') {
        list.sort((a, b) => (b.chapter_count || 0) - (a.chapter_count || 0));
    }

    return list;
}

function getFilteredSeriesHTML() {
    const list = getFilteredSeries();
    if (list.length === 0) {
        return `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h3>No manhwa match your search</h3>
                <p>Try adjusting your search query or clear genre filters.</p>
            </div>
        `;
    }

    return list.map((s, idx) => {
        const progress = StorageService.getSeriesProgress(s.slug);
        return `
            <a href="/series/${encodeURIComponent(s.slug)}" class="series-card">
                <div class="series-card-image">
                    <div class="card-top-badges">
                        <span class="series-rank-badge">#${idx + 1}</span>
                        <span class="series-card-badge">${s.chapter_count || 0} CH</span>
                    </div>
                    <img 
                        src="${proxyUrl(s.cover_url)}" 
                        alt="${escapeHtml(s.title)}" 
                        loading="lazy" 
                        referrerpolicy="no-referrer"
                        onerror="this.src='/img/placeholder.svg'"
                    >
                </div>
                <div class="series-card-content">
                    <div class="series-card-title">${escapeHtml(s.title)}</div>
                    ${Array.isArray(s.tags) && s.tags.length > 0 ? `
                        <div class="series-card-tags">
                            ${s.tags.slice(0, 2).map(t => `<span class="card-mini-tag">${escapeHtml(t)}</span>`).join('')}
                        </div>
                    ` : ''}
                    <div class="series-card-meta">
                        <span>📖 ${s.chapter_count || 0} chapters</span>
                        
                    </div>
                    ${progress ? `
                        <div style="font-size:0.75rem; color:var(--accent-primary-hover); margin-top:8px; font-weight:700;">
                            Last Read: Ch. ${progress.lastChapterNum}
                        </div>
                    ` : ''}
                </div>
            </a>
        `;
    }).join('');
}

function updateSeriesGrid() {
    const grid = document.getElementById('seriesGrid');
    const countEl = document.getElementById('seriesCount');
    if (grid) {
        grid.innerHTML = getFilteredSeriesHTML();
    }
    if (countEl) {
        countEl.textContent = getFilteredSeries().length;
    }
}

async function renderSeriesDetail(app, slug) {
    document.body.classList.remove('in-reader');

    app.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
            <p>Loading manhwa details...</p>
        </div>
    `;

    const data = await getSeries(slug);
    if (!data) {
        app.innerHTML = `
            <div class="error-message">
                <h2>Series Not Found</h2>
                <p>Could not find series "${escapeHtml(slug)}". It may have been renamed or removed.</p>
                <a href="/" class="btn btn-secondary">← Back to Browse</a>
            </div>
        `;
        return;
    }

    // Always use cover_url from all_series (has correct hashes) if available
    const apiSeries = allSeries.find(s => s.slug === slug);
    if (apiSeries && apiSeries.cover_url) {
        data.cover_url = apiSeries.cover_url;
    }

    currentSeries = data;
    document.title = `${data.title} - Dex Manhwa`;

    chapterFilterQuery = '';
    const chapters = data.chapters || [];
    const progress = StorageService.getSeriesProgress(slug);
    const isBookmarked = StorageService.isBookmarked(slug);
    const firstChapter = chapters.length > 0 ? chapters[0] : null;

    app.innerHTML = `
        <div class="breadcrumb">
            <a href="/">Home</a>
            <span class="breadcrumb-separator">/</span>
            <span>${escapeHtml(data.title)}</span>
        </div>

        <div class="series-detail-hero">
            <img src="${proxyUrl(data.cover_url)}" class="hero-backdrop" alt="" aria-hidden="true" referrerpolicy="no-referrer">
            <div class="hero-content">
                <div class="series-cover-wrapper">
                    <img src="${proxyUrl(data.cover_url)}" alt="${escapeHtml(data.title)}" referrerpolicy="no-referrer" onerror="this.src='/img/placeholder.svg'">
                </div>
                <div class="series-info">
                    <h1>${escapeHtml(data.title)}</h1>
                    
                    <div class="series-badges">
                        
                        <span class="badge accent">📚 ${chapters.length} Chapters</span>
                        <span class="badge">Status: ${escapeHtml(data.status || 'Ongoing')}</span>
                        ${(data.tags || []).map(t => `<span class="badge">${escapeHtml(typeof t === 'object' ? t.name || t.title || JSON.stringify(t) : t)}</span>`).join('')}
                    </div>

                    <div class="series-actions">
                        ${firstChapter ? `
                            <a href="/series/${encodeURIComponent(slug)}/chapter/${firstChapter.number}" class="btn btn-primary">
                                ▶ Start Reading (Ch. ${firstChapter.number})
                            </a>
                        ` : ''}

                        ${progress ? `
                            <a href="/series/${encodeURIComponent(slug)}/chapter/${progress.lastChapterNum}" class="btn btn-secondary">
                                ⏱️ Resume Ch. ${progress.lastChapterNum}
                            </a>
                        ` : ''}

                        <button class="btn btn-secondary" id="bookmarkBtn">
                            ${isBookmarked ? '★ Bookmarked' : '☆ Bookmark'}
                        </button>
                    </div>

                    <div class="series-description">
                        ${escapeHtml(data.description || 'No description available for this series.')}
                    </div>
                </div>
            </div>
        </div>

        <div class="chapter-section">
            <div class="chapter-toolbar">
                <div class="chapter-count-title">Chapters (${chapters.length})</div>
                <div class="chapter-filters">
                    <input 
                        type="text" 
                        class="chapter-search-input" 
                        id="chapterSearchInput" 
                        placeholder="Search chapter..."
                    >
                    <button class="sort-btn" id="chapterSortBtn">
                        ⇅ ${chapterSortOrder === 'asc' ? 'Oldest First' : 'Newest First'}
                    </button>
                </div>
            </div>

            <div class="chapter-grid" id="chapterGrid">
                ${getFilteredChaptersHTML(slug, chapters)}
            </div>
        </div>
    `;

    const bookmarkBtn = document.getElementById('bookmarkBtn');
    if (bookmarkBtn) {
        bookmarkBtn.addEventListener('click', () => {
            const added = StorageService.toggleBookmark(data);
            bookmarkBtn.textContent = added ? '★ Bookmarked' : '☆ Bookmark';
        });
    }

    const chSearch = document.getElementById('chapterSearchInput');
    const chSortBtn = document.getElementById('chapterSortBtn');

    if (chSearch) {
        chSearch.addEventListener('input', (e) => {
            chapterFilterQuery = e.target.value.toLowerCase().trim();
            updateChapterGrid(slug, chapters);
        });
    }

    if (chSortBtn) {
        chSortBtn.addEventListener('click', () => {
            chapterSortOrder = chapterSortOrder === 'asc' ? 'desc' : 'asc';
            chSortBtn.innerHTML = `⇅ ${chapterSortOrder === 'asc' ? 'Oldest First' : 'Newest First'}`;
            updateChapterGrid(slug, chapters);
        });
    }
}

function getFilteredChapters(chapters) {
    let list = [...chapters];

    if (chapterFilterQuery) {
        list = list.filter(ch => {
            const numStr = String(ch.number);
            const titleStr = (ch.title || '').toLowerCase();
            return numStr.includes(chapterFilterQuery) || titleStr.includes(chapterFilterQuery);
        });
    }

    if (chapterSortOrder === 'desc') {
        list.reverse();
    }

    return list;
}

function getFilteredChaptersHTML(slug, chapters) {
    const list = getFilteredChapters(chapters);
    if (list.length === 0) {
        return `<div class="empty-state" style="grid-column: 1 / -1;"><p>No chapters match "${escapeHtml(chapterFilterQuery)}"</p></div>`;
    }

    return list.map(ch => {
        const isRead = StorageService.isChapterRead(slug, ch.number);
        return `
            <a href="/series/${encodeURIComponent(slug)}/chapter/${ch.number}" class="chapter-item ${isRead ? 'read' : ''}">
                <span class="chapter-number">Ch. ${ch.number}</span>
                <span style="font-size: 0.8rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${escapeHtml(ch.title || `Chapter ${ch.number}`)}
                </span>
            </a>
        `;
    }).join('');
}

function updateChapterGrid(slug, chapters) {
    const grid = document.getElementById('chapterGrid');
    if (grid) {
        grid.innerHTML = getFilteredChaptersHTML(slug, chapters);
    }
}

async function renderChapterReader(app, slug, chNum) {
    // Enable reader mode to eliminate all external header/footer & distracting hovers
    document.body.classList.add('in-reader');

    app.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
            <p>Loading Chapter ${chNum}...</p>
        </div>
    `;

    const seriesData = await getSeries(slug);
    if (!seriesData) {
        app.innerHTML = `
            <div class="error-message">
                <h2>Series Not Found</h2>
                <a href="/" class="btn btn-secondary">← Back to Home</a>
            </div>
        `;
        return;
    }

    currentSeries = seriesData;
    const chapters = seriesData.chapters || [];

    const chapterObj = chapters.find(ch => parseFloat(ch.number) === chNum);
    if (!chapterObj) {
        app.innerHTML = `
            <div class="error-message">
                <h2>Chapter ${chNum} Not Found</h2>
                <a href="/series/${encodeURIComponent(slug)}" class="btn btn-secondary">← Back to Series</a>
            </div>
        `;
        return;
    }

    const chapterData = chapterObj;
    const image_urls = Array.isArray(chapterData.images) ? chapterData.images : (chapterData.image_urls || []);
    if (!image_urls.length) {
        app.innerHTML = `
            <div class="error-message">
                <h2>Could not load chapter images</h2>
                <p>The chapter content could not be retrieved from the source server.</p>
                <a href="/series/${encodeURIComponent(slug)}" class="btn btn-secondary">← Back to Series</a>
            </div>
        `;
        return;
    }

    StorageService.saveHistory(slug, chNum, seriesData, chapterData.title || `Chapter ${chNum}`);

    const seriesTitle = seriesData.title;
    document.title = `${seriesTitle} Ch.${chNum} - Dex Manhwa`;

    const chNumbers = chapters.map(ch => parseFloat(ch.number));
    const currIdx = chNumbers.indexOf(chNum);
    const prevNum = currIdx > 0 ? chNumbers[currIdx - 1] : null;
    const nextNum = currIdx >= 0 && currIdx < chNumbers.length - 1 ? chNumbers[currIdx + 1] : null;

    const settings = StorageService.getSettings();

    app.innerHTML = `
        <div class="reader-wrapper">
            <!-- Floating Auto-Hiding Reader Bar (Slides away when scrolling down to read) -->
            <div class="reader-top-bar" id="readerTopBar">
                <div class="reader-breadcrumbs">
                    <a href="/series/${encodeURIComponent(slug)}">← ${escapeHtml(seriesTitle)}</a>
                    <span class="sep">/</span>
                    <span>Ch. ${chNum}</span>
                </div>

                <div class="reader-controls-cluster">
                    <select class="chapter-select" id="chapterDropdown">
                        ${chapters.map(ch => `
                            <option value="${ch.number}" ${parseFloat(ch.number) === chNum ? 'selected' : ''}>
                                Ch. ${ch.number} ${ch.title ? `(${escapeHtml(ch.title)})` : ''}
                            </option>
                        `).join('')}
                    </select>

                    <a href="${prevNum !== null ? `/series/${encodeURIComponent(slug)}/chapter/${prevNum}` : '#'}" 
                       class="reader-nav-btn ${prevNum === null ? 'disabled' : ''}">
                       ◀ Prev
                    </a>

                    <a href="${nextNum !== null ? `/series/${encodeURIComponent(slug)}/chapter/${nextNum}` : '#'}" 
                       class="reader-nav-btn ${nextNum === null ? 'disabled' : ''}">
                       Next ▶
                    </a>
                    <button class="btn btn-download" id="downloadChapterBtn" style="margin-left:10px;padding:6px 14px;font-size:0.9rem">
                        ⬇️ Download
                    </button>
                    <span id="downloadCounter" style="margin-left:10px;font-size:0.85rem;color:#888;"></span>
                </div>
            </div>

            <!-- Reader Settings Toolbar -->
            <div class="reader-settings-bar">
                <div class="setting-group">
                    <span>Width:</span>
                    <button class="setting-btn ${settings.readerWidth === '650px' ? 'active' : ''}" data-width="650px">Slim</button>
                    <button class="setting-btn ${settings.readerWidth === '850px' ? 'active' : ''}" data-width="850px">Default</button>
                    <button class="setting-btn ${settings.readerWidth === '1100px' ? 'active' : ''}" data-width="1100px">Wide</button>
                    <button class="setting-btn ${settings.readerWidth === '100%' ? 'active' : ''}" data-width="100%">Full</button>
                </div>

                <div class="setting-group">
                    <span>Gap:</span>
                    <button class="setting-btn ${settings.gap === '0px' ? 'active' : ''}" data-gap="0px">Seamless (0px)</button>
                    <button class="setting-btn ${settings.gap === '10px' ? 'active' : ''}" data-gap="10px">Spaced</button>
                </div>

                <div style="font-size: 0.8rem; color: var(--text-muted);">
                    ${image_urls.length} Pages • Use ◀ ▶ keys
                </div>
            </div>

            <!-- Main Canvas: STRICT NO HOVER EFFECTS -->
            <div class="reader-canvas" id="readerCanvas" style="max-width: ${settings.readerWidth}; gap: ${settings.gap};">
                ${image_urls.map((url, i) => `
                    <div class="page-wrapper" id="pageWrap-${i}">
                        <div class="page-skeleton">
                            <div class="loading-spinner" style="width:24px;height:24px;border-width:2px;"></div>
                            <span>Page ${i + 1} / ${image_urls.length}</span>
                        </div>
                        <img 
                            src="${url}" 
                            alt="Page ${i + 1}" 
                            class="page-image" 
                            loading="lazy" 
                            referrerpolicy="no-referrer"
                            onload="onPageLoad(this, ${i})"
                            onerror="onPageError(this, '${url}', ${i})"
                        >
                    </div>
                `).join('')}
            </div>

            <!-- Bottom Navigation -->
            <div class="reader-bottom-nav">
                <a href="${prevNum !== null ? `/series/${encodeURIComponent(slug)}/chapter/${prevNum}` : '#'}" 
                   class="reader-nav-btn ${prevNum === null ? 'disabled' : ''}">
                   ◀ Previous Chapter
                </a>

                <a href="/series/${encodeURIComponent(slug)}" class="reader-nav-btn">
                    Series Index
                </a>

                <a href="${nextNum !== null ? `/series/${encodeURIComponent(slug)}/chapter/${nextNum}` : '#'}" 
                   class="reader-nav-btn ${nextNum === null ? 'disabled' : ''}">
                   Next Chapter ▶
                </a>
            </div>
        </div>

        <div class="floating-actions" id="floatingActions">
            <button class="floating-btn" id="scrollTopBtn" title="Back to Top">▲</button>
        </div>
    `;

    const dropdown = document.getElementById('chapterDropdown');
    if (dropdown) {
        dropdown.addEventListener('change', (e) => {
            navigate(`/series/${encodeURIComponent(slug)}/chapter/${e.target.value}`);
        });
    }

    // Wire up download button
    const dlBtn = document.getElementById('downloadChapterBtn');
    if (dlBtn) {
        dlBtn.addEventListener('click', () => downloadChapter(slug, chNum, chapterData));
    }
    
    // Show download counter
    const counter = document.getElementById('downloadCounter');
    if (counter) {
        const count = getDownloadCount();
        if (count >= 10) {
            counter.textContent = `Daily limit reached (${count}/10)`;
            counter.style.color = '#ff4444';
        } else if (count > 0) {
            counter.textContent = `Downloads today: ${count}/10`;
        } else {
            counter.textContent = `0/10 downloads today`;
        }
    }

    const canvas = document.getElementById('readerCanvas');
    const widthBtns = app.querySelectorAll('[data-width]');
    widthBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const w = btn.dataset.width;
            widthBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            canvas.style.maxWidth = w;
            StorageService.saveSettings({ readerWidth: w });
        });
    });

    const gapBtns = app.querySelectorAll('[data-gap]');
    gapBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const g = btn.dataset.gap;
            gapBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            canvas.style.gap = g;
            StorageService.saveSettings({ gap: g });
        });
    });

    const scrollBtn = document.getElementById('scrollTopBtn');
    if (scrollBtn) {
        scrollBtn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
}

// Global Scroll Handler: updates progress bar and auto-hides reader bar
function handleWindowScroll() {
    const currentY = window.scrollY;

    // 1. Reading Progress
    const bar = document.getElementById('readingProgressBar');
    if (bar && document.body.classList.contains('in-reader')) {
        const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (totalHeight > 0) {
            const progress = Math.min(100, Math.max(0, (currentY / totalHeight) * 100));
            bar.style.width = progress + '%';
        }
    }

    // 2. Auto-hide reader bars when scrolling down to read
    const topBar = document.getElementById('readerTopBar');
    const floatActions = document.getElementById('floatingActions');

    if (topBar && document.body.classList.contains('in-reader')) {
        // Scrolling down past 70px -> hide top bar
        if (currentY > lastScrollY && currentY > 70) {
            if (!isNavHidden) {
                topBar.classList.add('nav-hidden');
                if (floatActions) floatActions.classList.add('hidden');
                isNavHidden = true;
            }
        } 
        // Scrolling up or at very top -> reveal top bar
        else if (currentY < lastScrollY || currentY <= 40) {
            if (isNavHidden) {
                topBar.classList.remove('nav-hidden');
                if (floatActions) floatActions.classList.remove('hidden');
                isNavHidden = false;
            }
        }
    }

    lastScrollY = currentY;
}

window.onPageLoad = function(img, index) {
    const wrap = document.getElementById(`pageWrap-${index}`);
    if (wrap) {
        wrap.classList.add('loaded');
        const skeleton = wrap.querySelector('.page-skeleton');
        if (skeleton) skeleton.remove();
    }
};

window.onPageError = function(img, originalUrl, index) {
    const wrap = document.getElementById(`pageWrap-${index}`);
    if (!wrap) return;

    img.style.display = 'none';
    const skeleton = wrap.querySelector('.page-skeleton');
    if (skeleton) skeleton.remove();

    if (wrap.querySelector('.page-error')) return;

    const errorBox = document.createElement('div');
    errorBox.className = 'page-error';
    errorBox.innerHTML = `
        <p style="color: var(--accent-crimson); font-size: 0.9rem;">⚠️ Failed to load Page ${index + 1}</p>
        <button class="retry-btn">Tap to Retry</button>
    `;

    errorBox.querySelector('.retry-btn').addEventListener('click', () => {
        errorBox.remove();
        img.style.display = 'block';
        img.src = originalUrl + (originalUrl.includes('?') ? '&' : '?') + 'retry=' + Date.now();
    });

    wrap.appendChild(errorBox);
};

function handleKeyboardNav(e) {
    const path = getNormalizedPath();
    const match = path.match(/^\/series\/([^\/]+)\/chapter\/([^\/]+)/);
    if (!match) return;

    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    const slug = decodeURIComponent(match[1]);
    const chNum = parseFloat(match[2]);

    if (!currentSeries || !currentSeries.chapters) return;
    const chapters = currentSeries.chapters;
    const chNumbers = chapters.map(ch => parseFloat(ch.number));
    const currIdx = chNumbers.indexOf(chNum);

    if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
        if (currIdx > 0) {
            navigate(`/series/${encodeURIComponent(slug)}/chapter/${chNumbers[currIdx - 1]}`);
        }
    } else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
        if (currIdx >= 0 && currIdx < chNumbers.length - 1) {
            navigate(`/series/${encodeURIComponent(slug)}/chapter/${chNumbers[currIdx + 1]}`);
        }
    } else if (e.key === 'Escape') {
        navigate(`/series/${encodeURIComponent(slug)}`);
    }
}

// --- Helper: route image URLs through Worker proxy to avoid CORS blocks ---
function proxyUrl(url) {
    if (!url) return '/img/placeholder.svg';
    return 'https://manhwa-kv-proxy.dexlot8.workers.dev/proxy/image?url=' + encodeURIComponent(url);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}


// --- Download functionality (per-chapter) ---
function getDownloadCount() {
    const today = new Date().toISOString().slice(0, 10);
    const data = JSON.parse(localStorage.getItem("dexmanhwa_downloads") || "{}");
    if (data.date === today) return data.count;
    return 0;
}

function incrementDownloadCount() {
    const today = new Date().toISOString().slice(0, 10);
    const data = { date: today, count: getDownloadCount() + 1 };
    localStorage.setItem("dexmanhwa_downloads", JSON.stringify(data));
}

async function downloadChapter(slug, chapterNum, chapterData) {
    const MAX_DAILY = 10;
    if (getDownloadCount() >= MAX_DAILY) {
        const counter = document.getElementById('downloadCounter');
        if (counter) counter.textContent = `Daily limit reached (${getDownloadCount()}/${MAX_DAILY})`;
        alert(`Daily download limit reached (${MAX_DAILY}/day). Come back tomorrow.`);
        return;
    }
    
    const btn = document.getElementById('downloadChapterBtn');
    const counter = document.getElementById('downloadCounter');
    if (btn) { btn.disabled = true; btn.textContent = "Downloading..."; }
    if (counter) counter.textContent = "Downloading...";
    
    try {
        if (!chapterData || !chapterData.image_urls || chapterData.image_urls.length === 0) {
            alert("No images to download.");
            if (btn) { btn.disabled = false; btn.textContent = "⬇️ Download"; }
            return;
        }
        
        if (!window.JSZip) {
            await new Promise((resolve, reject) => {
                const s = document.createElement("script");
                s.src = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js";
                s.onload = resolve; s.onerror = reject;
                document.head.appendChild(s);
            });
        }
        
        const zip = new JSZip();
        const imgFolder = zip.folder("ch" + chapterNum);
        let downloaded = 0;
        
        for (let i = 0; i < chapterData.image_urls.length; i++) {
            try {
                const imgUrl = "https://manhwa-kv-proxy.dexlot8.workers.dev/proxy/image?url=" + encodeURIComponent(chapterData.image_urls[i]);
                const res = await fetch(imgUrl);
                if (!res.ok) continue;
                const blob = await res.blob();
                const ext = chapterData.image_urls[i].split(".").pop().split("?")[0] || "jpg";
                imgFolder.file(String(i + 1).padStart(3, "0") + "." + ext, blob);
                downloaded++;
            } catch (e) {
                console.warn("Image failed:", e);
            }
        }
        
        if (downloaded === 0) {
            alert("Could not download images.");
            if (btn) { btn.disabled = false; btn.textContent = "⬇️ Download"; }
            return;
        }
        
        const blob = await zip.generateAsync({ type: "blob" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = slug + "_ch" + chapterNum + ".zip";
        a.click();
        URL.revokeObjectURL(url);
        
        incrementDownloadCount();
        
        const counter = document.getElementById('downloadCounter');
        if (counter) counter.textContent = `Downloads today: ${getDownloadCount()}/${MAX_DAILY}`;
        
        if (btn) { btn.disabled = false; btn.textContent = "⬇️ Download Again"; }
    } catch (err) {
        console.error("Download failed:", err);
        alert("Download failed: " + err.message);
        if (btn) { btn.disabled = false; btn.textContent = "⬇️ Download"; }
    }
}
