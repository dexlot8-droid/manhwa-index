/**
 * Chapter reader page — displays images with navigation.
 */

let currentChapter = 0;
let seriesSlug = "";

document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.location.search);
    seriesSlug = params.get("slug") || "";
    currentChapter = parseInt(params.get("ch") || "1");
    
    if (!seriesSlug) {
        document.getElementById("loading").textContent = "No series specified.";
        return;
    }
    
    await loadChapter();
});

async function loadChapter() {
    const loading = document.getElementById("loading");
    const reader = document.getElementById("reader");
    const titleEl = document.getElementById("chapterTitle");
    const imagesEl = document.getElementById("chapterImages");
    
    // Get chapter data using bundled series format
    const data = await getChapterBySlugAndNumber(seriesSlug, currentChapter);
    
    if (!data || !data.image_urls || data.image_urls.length === 0) {
        loading.textContent = "Chapter not found.";
        return;
    }
    
    loading.style.display = "none";
    reader.style.display = "block";
    
    titleEl.textContent = data.title || ("Chapter " + currentChapter);
    
    // Render images with lazy loading
    let html = "";
    for (let i = 0; i < data.image_urls.length; i++) {
        const imgUrl = data.image_urls[i];
        html += `<img src="${imgUrl}" alt="Page ${i + 1}" loading="lazy" onerror="this.style.display=none">`;
    }
    imagesEl.innerHTML = html;
    
    // Update navigation
    const prevCh = currentChapter - 1;
    const nextCh = currentChapter + 1;
    const prevUrl = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${prevCh}`;
    const nextUrl = `/chapter.html?slug=${encodeURIComponent(seriesSlug)}&ch=${nextCh}`;
    
    const prevEl = document.getElementById("prevCh");
    const nextEl = document.getElementById("nextCh");
    const prevEl2 = document.getElementById("prevCh2");
    const nextEl2 = document.getElementById("nextCh2");
    
    if (prevEl) prevEl.href = prevEl2.href = prevEl2 ? prevUrl : prevUrl;
    if (nextEl) nextEl.href = nextEl2.href = nextEl2 ? nextUrl : nextUrl;
    
    // Update page title
    document.title = `${data.title || "Chapter " + currentChapter} - Manhwa Index`;
    
    // Save reading history
    const seriesData = await getSeries(seriesSlug);
    if (seriesData) {
        StorageService.saveHistory(seriesSlug, currentChapter, seriesData, data.title);
    }
}

function escapeHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
