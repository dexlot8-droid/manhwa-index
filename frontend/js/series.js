/**
 * Series detail page — shows info + chapter list.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const seriesId = params.get('id');
    
    if (!seriesId) {
        document.getElementById('loading').textContent = 'No series ID.';
        return;
    }
    
    await loadSeriesDetail(seriesId);
});

async function loadSeriesDetail(seriesId) {
    const data = await fetchJSON(`${API_BASE}/series:${seriesId}`);
    const loading = document.getElementById('loading');
    const detailEl = document.getElementById('series-detail');
    const chapterEl = document.getElementById('chapter-list');
    
    if (!data) {
        loading.textContent = 'Series not found.';
        return;
    }
    
    loading.style.display = 'none';
    document.getElementById('pageTitle').textContent = data.title;
    
    // Render series info
    detailEl.innerHTML = `
        <img src="${data.cover_url || '/img/placeholder.svg'}" 
             alt="${escapeHtml(data.title)}"
             onerror="this.src='/img/placeholder.svg'">
        <div class="info">
            <h2>${escapeHtml(data.title)}</h2>
            <div class="meta">
                <span>Author: ${escapeHtml(data.author || 'Unknown')}</span>
                <span>Status: ${data.status}</span>
            </div>
            <div class="meta">
                ${(data.tags || []).map(t => `<span>#${escapeHtml(t)}</span>`).join('')}
            </div>
            <p class="description">${escapeHtml(data.description || 'No description.')}</p>
            <p style="color:#888;font-size:0.85rem;margin-top:10px">${data.chapter_count || 0} chapters</p>
        </div>
    `;
    
    // Render chapter list (newest first)
    const chapters = data.chapters || [];
    if (chapters.length > 0) {
        chapterEl.innerHTML = `
            <h3>Chapters (${chapters.length})</h3>
            <div class="chapter-list">
                ${chapters.map(ch => `
                    <a href="/chapter.html?id=${ch.id}" class="chapter-item">
                        <span class="number">Ch. ${ch.chapter_number}</span>
                        <span class="title">${escapeHtml(ch.title || '')}</span>
                    </a>
                `).join('')}
            </div>
        `;
    } else {
        chapterEl.innerHTML = '<p style="color:#666">No chapters indexed yet.</p>';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
