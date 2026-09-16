/**
 * Chapter reader page — displays images with navigation.
 */

let currentChapter = 0;
let seriesSlug = '';

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    seriesSlug = params.get('slug') || '';
    currentChapter = parseInt(params.get('ch') || '1');
    
    if (!seriesSlug) {
        document.getElementById('loading').textContent = 'No series specified.';
        return;
    }
    
    await loadChapter();
});

async function loadChapter() {
    const loading = document.getElementById('loading');
    const reader = document.getElementById('reader');
    const titleEl = document.getElementById('chapterTitle');
    const imagesEl = document.getElementById('chapterImages');
    
    // Get chapter data
    const data = await getChapter(seriesSlug + ':' + currentChapter);
    
    if (!data || !data.image_urls || data.image_urls.length === 0) {
        loading.textContent = 'Chapter not found.';
        return;
    }
    
    loading.style.display = 'none';
    reader.style.display = 'block';
    
    titleEl.textContent = data.title || ('Chapter ' + currentChapter);
    
    // Render images with lazy loading
    let html = '';
    for (let i = 0; i < data.image_urls.length; i++) {
        const imgUrl = data.image_urls[i];
        html += `<img src="${imgUrl}" alt="Page ${i + 1}" loading="lazy" onerror="this.style.display='none'">`;
    }
    imagesEl.innerHTML = html;
    
    // Update navigation
    document.getElementById('prevCh').href = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${currentChapter - 1}`;
    document.getElementById('nextCh').href = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${currentChapter + 1}`;
    document.getElementById('prevCh2').href = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${currentChapter - 1}`;
    document.getElementById('nextCh2').href = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${currentChapter + 1}`;
    
    // Update page title
    document.title = `${data.title || 'Chapter ' + currentChapter} - Manhwa Index`;
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
