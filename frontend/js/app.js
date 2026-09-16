/**
 * Main app logic — Browse and search series on the homepage.
 */

let allSeries = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadStats();
    await loadSeries();
    
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterSeries(e.target.value);
    });
});

async function loadStats() {
    const data = await getAllSeries();
    if (data && data.series) {
        const total = data.series.length;
        const totalChapters = data.series.reduce(function(sum, s) { return sum + (s.chapter_count || 0); }, 0);
        document.getElementById('stats').innerHTML = 
            '<strong>' + total + '</strong> series indexed &bull; ' +
            '<strong>' + totalChapters + '</strong> chapters &bull; ' +
            '<strong>' + (totalChapters * 30).toLocaleString() + '+</strong> pages';
    }
}

async function loadSeries() {
    const data = await getAllSeries();
    const loading = document.getElementById('loading');
    const grid = document.getElementById('series-grid');
    
    if (!data || !data.series || data.series.length === 0) {
        loading.textContent = 'No series indexed yet.';
        return;
    }
    
    loading.style.display = 'none';
    allSeries = data.series;
    renderSeries(allSeries);
}

function renderSeries(seriesList) {
    const grid = document.getElementById('series-grid');
    
    if (seriesList.length === 0) {
        grid.innerHTML = '<p style="color:#666;grid-column:1/-1">No matches found.</p>';
        return;
    }
    
    var html = '';
    for (var i = 0; i < seriesList.length; i++) {
        var s = seriesList[i];
        var cover = s.cover_url || '/img/placeholder.svg';
        var title = escapeHtml(s.title);
        var chCount = s.chapter_count || 0;
        
        // Use slug for detail link
        html += '<a href="/series.html?slug=' + encodeURIComponent(s.slug) + '" class="series-card">';
        html += '<img src="' + cover + '" alt="' + title + '" loading="lazy" onerror="this.src=\'/img/placeholder.svg\'">';
        html += '<div class="info">';
        html += '<div class="title">' + title + '</div>';
        html += '<div class="meta">' + chCount + ' ch</div>';
        html += '</div></a>';
    }
    grid.innerHTML = html;
}

function filterSeries(query) {
    var q = query.toLowerCase().trim();
    if (!q) {
        renderSeries(allSeries);
        return;
    }
    
    var filtered = allSeries.filter(function(s) { 
        var titleMatch = s.title.toLowerCase().indexOf(q) !== -1;
        var tagMatch = (s.tags || []).some(function(t) { return t.indexOf(q) !== -1; });
        return titleMatch || tagMatch;
    });
    renderSeries(filtered);
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
