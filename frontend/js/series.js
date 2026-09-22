/**
 * Series detail page — shows info + chapter list + download.
 */

document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.search || window.location.search);
    const slug = params.get("slug");
    
    if (!slug) {
        document.getElementById("loading").textContent = "No series slug.";
        return;
    }
    
    await loadSeriesDetail(slug);
});

async function loadSeriesDetail(slug) {
    const data = await getSeries(slug);
    const loading = document.getElementById("loading");
    const detailEl = document.getElementById("series-detail");
    const chapterEl = document.getElementById("chapter-list");
    
    if (!data) {
        loading.textContent = "Series not found.";
        return;
    }
    
    loading.style.display = "none";
    const pageTitle = document.getElementById("pageTitle");
    if (pageTitle) pageTitle.textContent = data.title;
    
    const chapters = Array.isArray(data.chapters) ? data.chapters : [];
    const chCount = chapters.length;
    
    detailEl.innerHTML = `
        <div class="cover">
            <img src="${data.cover_url || "/img/placeholder.svg"}" 
                 alt="${escapeHtml(data.title)}"
                 onerror="this.src='/img/placeholder.svg'">
        </div>
        <div class="info">
            <h2>${escapeHtml(data.title)}</h2>
            <div class="meta">
                <span>Author: ${escapeHtml(data.author || "Unknown")}</span>
                <span>Status: ${data.status || "ongoing"}</span>
            </div>
            <div class="tags">
                ${(data.tags || []).map(t => `<span>#${escapeHtml(t)}</span>`).join("")}
            </div>
            <p class="description">${escapeHtml(data.description || "No description.")}</p>
            <p style="color:#888;font-size:0.85rem;margin-top:10px">${chCount} chapters</p>
        </div>
    `;
    
    if (chCount > 0) {
        let chHtml = "<h3>Chapters</h3><div class=\"chapter-list\">";
        for (const ch of chapters) {
            chHtml += `
                <a href="/chapter.html?slug=${encodeURIComponent(data.slug)}&ch=${ch.number}" class="chapter-item">
                    <span class="number">Ch. ${ch.number}</span>
                    <span class="title">${escapeHtml(ch.title || ("Chapter " + ch.number))}</span>
                </a>
            `;
        }
        chHtml += "</div>";
        chapterEl.innerHTML = chHtml;
    } else {
        chapterEl.innerHTML = "<p style=\"color:#666\">No chapters indexed yet.</p>";
    }
}

function escapeHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


