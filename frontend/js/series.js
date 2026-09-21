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
    
    // Download button (10/day cap enforced)
    let downloadBtn = "";
    if (chCount > 0) {
        downloadBtn = `<button class="btn btn-primary" onclick="downloadSeries('${data.slug}')" id="downloadBtn">
            <span>⬇️</span> Download All Chapters
        </button>`;
    }
    
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
            <div class="actions" style="margin-top:15px">
                ${downloadBtn}
            </div>
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

// Daily download cap (localStorage-based)
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

async function downloadSeries(slug) {
    const MAX_DAILY = 10;
    if (getDownloadCount() >= MAX_DAILY) {
        alert(`Daily download limit reached (${MAX_DAILY}/day). Come back tomorrow.`);
        return;
    }
    
    const btn = document.getElementById("downloadBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Downloading..."; }
    
    try {
        const seriesData = await getSeries(slug);
        if (!seriesData || !seriesData.chapters || seriesData.chapters.length === 0) {
            alert("No chapters to download.");
            return;
        }
        
        // Dynamically load JSZip
        if (!window.JSZip) {
            await new Promise((resolve, reject) => {
                const s = document.createElement("script");
                s.src = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js";
                s.onload = resolve;
                s.onerror = reject;
                document.head.appendChild(s);
            });
        }
        
        const zip = new JSZip();
        const imgFolder = zip.folder(seriesData.slug || "series");
        
        // Download first 3 chapters as sample (to avoid abuse)
        const chaptersToDownload = seriesData.chapters.slice(0, 3);
        let downloaded = 0;
        
        for (const ch of chaptersToDownload) {
            if (!ch.image_urls || ch.image_urls.length === 0) continue;
            const chFolder = imgFolder.folder("ch" + ch.number);
            
            for (let i = 0; i < ch.image_urls.length; i++) {
                try {
                    const imgUrl = "/proxy/image?url=" + encodeURIComponent(ch.image_urls[i]);
                    const res = await fetch(imgUrl);
                    if (!res.ok) continue;
                    const blob = await res.blob();
                    const ext = ch.image_urls[i].split(".").pop().split("?")[0] || "jpg";
                    chFolder.file(String(i + 1).padStart(3, "0") + "." + ext, blob);
                    downloaded++;
                } catch (e) {
                    console.warn("Image failed:", e);
                }
            }
        }
        
        if (downloaded === 0) {
            alert("Could not download images. They may be hotlink-protected.");
            return;
        }
        
        const blob = await zip.generateAsync({ type: "blob" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = (seriesData.slug || "manhwa") + "_ch1-" + chaptersToDownload.length + ".zip";
        a.click();
        URL.revokeObjectURL(url);
        
        incrementDownloadCount();
        
        if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download Again"; }
    } catch (err) {
        console.error("Download failed:", err);
        alert("Download failed: " + err.message);
        if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download"; }
    }
}
