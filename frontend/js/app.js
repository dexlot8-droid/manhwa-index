/**
 * Main app logic — Browse and search series on the homepage.
 */

let allSeries = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadStats();
    await loadSeries();
    
    // Search handler
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterSeries(e.target.value);
    });
});

async function loadStats() {
    const data = await getStats();
    if (data) {
        document.getElementById('stats').innerHTML = 
            '<strong>' + data.active_series + '</strong> series indexed &bull; ' +
            '<strong>' + data.active_chapters + '</strong> chapters &bull; ' +
            '<strong>' + (data.active_chapters * 30).toLocaleString() + '+</strong> pages';
    }
}

async function loadSeries() {
    const seriesList = await getAllSeries();
    const loading = document.getElementById('loading');
    const grid = document.getElementById('series-grid');
    
    if (!seriesList || seriesList.length === 0) {
        loading.textContent = 'No series indexed yet. Add one via the admin panel at /admin';
        loading.innerHTML += '<br><br><a href="/admin" style="color:#61afef">Open Admin Panel</a>';
        return;
    }
    
    loading.style.display = 'none';
    allSeries = seriesList;
    
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
        
        html += '<a href="/series.html?id=' + s.id + '" class="series-card">';
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
