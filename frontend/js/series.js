/**
 * Series detail page — shows info + chapter list.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('slug');
    
    if (!slug) {
        document.getElementById('loading').textContent = 'No series slug.';
        return;
    }
    
    await loadSeriesDetail(slug);
});

async function loadSeriesDetail(slug) {
    const data = await getSeries(slug);
    const loading = document.getElementById('loading');
    const detailEl = document.getElementById('series-detail');
    const chapterEl = document.getElementById('chapter-list');
    
    if (!data) {
        loading.textContent = 'Series not found.';
        return;
    }
    
    loading.style.display = 'none';
    document.getElementById('pageTitle').textContent = data.title;
    
    detailEl.innerHTML = `
        <div class="cover">
            <img src="${data.cover_url || '/img/placeholder.svg'}" 
                 alt="${escapeHtml(data.title)}"
                 onerror="this.src='/img/placeholder.svg'">
        </div>
        <div class="info">
            <h2>${escapeHtml(data.title)}</h2>
            <div class="meta">
                <span>Author: ${escapeHtml(data.author || 'Unknown')}</span>
                <span>Status: ${data.status}</span>
            </div>
            <div class="tags">
                ${(data.tags || []).map(t => `<span>#${escapeHtml(t)}</span>`).join('')}
            </div>
            <p class="description">${escapeHtml(data.description || 'No description.')}</p>
            <p style="color:#888;font-size:0.85rem;margin-top:10px">${data.chapter_count || 0} chapters</p>
        </div>
    `;
    
    // For now show placeholder chapters
    const chCount = data.chapter_count || 0;
    if (chCount > 0) {
        let chHtml = '<h3>Chapters</h3><div class="chapter-list">';
        for (let i = 1; i <= Math.min(chCount, 10); i++) {
            chHtml += `
                <a href="/chapter.html?slug=${encodeURIComponent(data.slug)}&ch=${i}" class="chapter-item">
                    <span class="number">Ch. ${i}</span>
                    <span class="title">Chapter ${i}</span>
                </a>
            `;
        }
        if (chCount > 10) {
            chHtml += `<p style="color:#888;margin-top:10px">... and ${chCount - 10} more chapters</p>`;
        }
        chHtml += '</div>';
        chapterEl.innerHTML = chHtml;
    } else {
        chapterEl.innerHTML = '<p style="color:#666">No chapters indexed yet.</p>';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
