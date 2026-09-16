/**
 * Manhwa Index — Single Page App with hash routing.
 * Routes: #/ (home), #/series/:slug (detail), #/chapter/:slug/:ch (reader)
 */

let allSeries = [];

document.addEventListener('DOMContentLoaded', async () => {
    // Handle hash routing
    window.addEventListener('hashchange', render);
    await loadAllSeries();
    render();
});

async function loadAllSeries() {
    const data = await getAllSeries();
    if (data && data.series) {
        allSeries = data.series;
    }
}

function render() {
    const hash = window.location.hash || '#/';
    const app = document.getElementById('app');
    
    if (hash.startsWith('#/series/')) {
        const slug = hash.replace('#/series/', '');
        renderSeriesDetail(app, slug);
    } else if (hash.startsWith('#/chapter/')) {
        const parts = hash.replace('#/chapter/', '').split('/');
        const slug = parts[0];
        const ch = parseInt(parts[1] || '1');
        renderChapter(app, slug, ch);
    } else {
        renderHome(app);
    }
}

function renderHome(app) {
    const total = allSeries.length;
    const totalChapters = allSeries.reduce((sum, s) => sum + (s.chapter_count || 0), 0);
    
    let html = '<div class="stats">';
    html += '<strong>' + total + '</strong> series &bull; ';
    html += '<strong>' + totalChapters + '</strong> chapters &bull; ';
    html += '<strong>' + (totalChapters * 30).toLocaleString() + '+</strong> pages';
    html += '</div>';
    
    html += '<div id="search"><input type="text" id="searchInput" placeholder="Search series..."></div>';
    html += '<div id="series-grid" class="grid">';
    
    if (allSeries.length === 0) {
        html += '<p style="color:#666">Loading series...</p>';
    }
    
    for (let i = 0; i < allSeries.length; i++) {
        const s = allSeries[i];
        const cover = s.cover_url || '/img/placeholder.svg';
        const title = escapeHtml(s.title);
        const chCount = s.chapter_count || 0;
        
        html += '<a href="#/series/' + encodeURIComponent(s.slug) + '" class="series-card">';
        html += '<img src="' + cover + '" alt="' + title + '" loading="lazy" onerror="this.src=\'/img/placeholder.svg\'">';
        html += '<div class="info">';
        html += '<div class="title">' + title + '</div>';
        html += '<div class="meta">' + chCount + ' ch</div>';
        html += '</div></a>';
    }
    
    html += '</div>';
    app.innerHTML = html;
    
    // Attach search handler
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filterSeries(e.target.value);
        });
    }
}

function filterSeries(query) {
    const q = query.toLowerCase().trim();
    if (!q) {
        renderHome(document.getElementById('app'));
        return;
    }
    
    const filtered = allSeries.filter(s => {
        const titleMatch = s.title.toLowerCase().indexOf(q) !== -1;
        const tagMatch = (s.tags || []).some(t => t.indexOf(q) !== -1);
        return titleMatch || tagMatch;
    });
    
    const app = document.getElementById('app');
    const grid = app.querySelector('#series-grid');
    if (!grid) return;
    
    let html = '';
    for (let i = 0; i < filtered.length; i++) {
        const s = filtered[i];
        const cover = s.cover_url || '/img/placeholder.svg';
        const title = escapeHtml(s.title);
        const chCount = s.chapter_count || 0;
        
        html += '<a href="#/series/' + encodeURIComponent(s.slug) + '" class="series-card">';
        html += '<img src="' + cover + '" alt="' + title + '" loading="lazy" onerror="this.src=\'/img/placeholder.svg\'">';
        html += '<div class="info">';
        html += '<div class="title">' + title + '</div>';
        html += '<div class="meta">' + chCount + ' ch</div>';
        html += '</div></a>';
    }
    grid.innerHTML = html;
}

async function renderSeriesDetail(app, slug) {
    const data = await getSeries(slug);
    
    if (!data) {
        app.innerHTML = '<p style="color:#666">Series not found.</p>';
        return;
    }
    
    const cover = data.cover_url || '/img/placeholder.svg';
    const title = escapeHtml(data.title);
    const chCount = data.chapter_count || 0;
    
    let html = '<div class="series-detail">';
    html += '<div class="cover"><img src="' + cover + '" alt="' + title + '" onerror="this.src=\'/img/placeholder.svg\'"></div>';
    html += '<div class="info">';
    html += '<h2>' + title + '</h2>';
    html += '<div class="meta"><span>Author: ' + escapeHtml(data.author || 'Unknown') + '</span><span>Status: ' + data.status + '</span></div>';
    html += '<div class="tags">' + (data.tags || []).map(t => '<span>#' + escapeHtml(t) + '</span>').join('') + '</div>';
    html += '<p class="description">' + escapeHtml(data.description || 'No description.') + '</p>';
    html += '<p style="color:#888;font-size:0.85rem;margin-top:10px">' + chCount + ' chapters</p>';
    html += '</div></div>';
    
    // Chapter list
    html += '<h3>Chapters</h3><div class="chapter-list">';
    const chapters = data.chapters || [];
    if (chapters.length === 0) {
        // Generate chapter links from chapter_count
        for (let i = 1; i <= Math.min(chCount, 50); i++) {
            html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + i + '" class="chapter-item">';
            html += '<span class="number">Ch. ' + i + '</span>';
            html += '<span class="title">Chapter ' + i + '</span>';
            html += '</a>';
        }
    } else {
        for (let i = 0; i < Math.min(chapters.length, 50); i++) {
            const ch = chapters[i];
            html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + ch.chapter_number + '" class="chapter-item">';
            html += '<span class="number">Ch. ' + ch.chapter_number + '</span>';
            html += '<span class="title">' + escapeHtml(ch.title) + '</span>';
            html += '</a>';
        }
    }
    html += '</div>';
    
    app.innerHTML = html;
    document.title = title + ' - Manhwa Index';
}

async function renderChapter(app, slug, chNum) {
    const data = await getSeries(slug);
    
    if (!data) {
        app.innerHTML = '<p style="color:#666">Chapter not found.</p>';
        return;
    }
    
    const title = data.title || slug;
    const chapters = data.chapters || [];
    let chapter = null;
    
    // Find the chapter
    for (let i = 0; i < chapters.length; i++) {
        if (chapters[i].chapter_number == chNum) {
            chapter = chapters[i];
            break;
        }
    }
    
    // If no chapter data, generate placeholder
    if (!chapter) {
        chapter = {
            chapter_number: chNum,
            title: 'Chapter ' + chNum,
            image_urls: []
        };
    }
    
    let html = '<div class="chapter-reader">';
    html += '<h1>' + escapeHtml(title) + ' - ' + escapeHtml(chapter.title) + '</h1>';
    
    // Navigation
    html += '<div class="chapter-nav">';
    html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + (chNum - 1) + '">← Previous</a>';
    html += '<a href="#/series/' + encodeURIComponent(slug) + '">Series</a>';
    html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + (chNum + 1) + '">Next →</a>';
    html += '</div>';
    
    // Images
    html += '<div id="chapter-images">';
    const images = chapter.image_urls || [];
    if (images.length === 0) {
        html += '<p style="color:#666;text-align:center;padding:40px">No images available for this chapter.</p>';
    } else {
        for (let i = 0; i < images.length; i++) {
            html += '<img src="' + images[i] + '" alt="Page ' + (i + 1) + '" loading="lazy" onerror="this.style.display=\'none\'">';
        }
    }
    html += '</div>';
    
    // Bottom navigation
    html += '<div class="chapter-nav" style="margin-top:20px">';
    html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + (chNum - 1) + '">← Previous</a>';
    html += '<a href="#/series/' + encodeURIComponent(slug) + '">Series</a>';
    html += '<a href="#/chapter/' + encodeURIComponent(slug) + '/' + (chNum + 1) + '">Next →</a>';
    html += '</div>';
    
    html += '</div>';
    
    app.innerHTML = html;
    document.title = title + ' Ch. ' + chNum + ' - Manhwa Index';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
