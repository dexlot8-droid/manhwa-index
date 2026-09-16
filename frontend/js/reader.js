/**
 * Chapter reader page — loads image URLs and displays them.
 */

let currentChapter = null;
let seriesChapters = [];

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const chapterId = params.get('id');
    
    if (!chapterId) {
        document.getElementById('loading').textContent = 'No chapter ID.';
        return;
    }
    
    await loadChapter(chapterId);
});

async function loadChapter(chapterId) {
    const data = await fetchJSON(`${API_BASE}/chapter:${chapterId}`);
    const loading = document.getElementById('loading');
    const imagesEl = document.getElementById('chapter-images');
    const infoEl = document.getElementById('chapter-info');
    const navEl = document.getElementById('chapter-nav');
    
    if (!data) {
        loading.textContent = 'Chapter not found.';
        return;
    }
    
    loading.style.display = 'none';
    currentChapter = data;
    
    document.getElementById('pageTitle').textContent = `Chapter ${data.chapter_number}`;
    infoEl.textContent = `Chapter ${data.chapter_number}${data.title ? ' — ' + data.title : ''} (${data.image_count} pages)`;
    
    // Render images
    const imageUrls = data.image_urls || [];
    if (imageUrls.length > 0) {
        imagesEl.innerHTML = imageUrls.map(url => 
            `<img src="${escapeHtml(url)}" alt="Page" loading="lazy" onerror="this.style.display='none'">`
        ).join('');
    } else {
        imagesEl.innerHTML = '<p style="color:#666;text-align:center;padding:40px">No images found for this chapter.</p>';
    }
    
    // Load series chapters for prev/next navigation
    if (data.series_id) {
        const seriesData = await fetchJSON(`${API_BASE}/series:${data.series_id}`);
        if (seriesData && seriesData.chapters) {
            seriesChapters = seriesData.chapters;
            renderNav(chapterId, data.series_id);
        }
    }
}

function renderNav(currentChapterId, seriesId) {
    const navEl = document.getElementById('chapter-nav');
    const currentIndex = seriesChapters.findIndex(ch => ch.id == currentChapterId);
    
    const prev = currentIndex < seriesChapters.length - 1 ? seriesChapters[currentIndex + 1] : null;
    const next = currentIndex > 0 ? seriesChapters[currentIndex - 1] : null;
    
    navEl.innerHTML = `
        <a href="${prev ? '/chapter.html?id=' + prev.id : '#'}" 
           class="${prev ? '' : 'disabled'}">
            ← Ch. ${prev ? prev.chapter_number : '—'}
        </a>
        <a href="/series.html?id=${seriesId}" class="disabled" style="flex:0.5">
            All Chapters
        </a>
        <a href="${next ? '/chapter.html?id=' + next.id : '#'}" 
           class="${next ? '' : 'disabled'}">
            Ch. ${next ? next.chapter_number : '—'} →
        </a>
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Keyboard navigation
document.addEventListener('keydown', (e) => {
    const links = document.querySelectorAll('.chapter-nav a');
    if (e.key === 'ArrowLeft' && links[0] && !links[0].classList.contains('disabled')) {
        links[0].click();
    } else if (e.key === 'ArrowRight' && links[2] && !links[2].classList.contains('disabled')) {
        links[2].click();
    }
});
