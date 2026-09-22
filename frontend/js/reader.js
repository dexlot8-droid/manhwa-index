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
    
    // Render images with lazy loading + proxy hotlink-protected images
    let html = "";
    for (let i = 0; i < data.image_urls.length; i++) {
        const imgUrl = "/proxy/image?url=" + encodeURIComponent(data.image_urls[i]);
        html += '<img src="' + imgUrl + '" alt="Page ' + (i + 1) + '" loading="lazy" onerror="this.style.display=\'none\'">';
    }
    imagesEl.innerHTML = html;
    
    // Update navigation
    const prevCh = currentChapter - 1;
    const nextCh = currentChapter + 1;
    const prevUrl = "/chapter.html?slug=" + encodeURIComponent(seriesSlug) + "&ch=" + prevCh;
    const nextUrl = "/chapter.html?slug=" + encodeURIComponent(seriesSlug) + "&ch=" + nextCh;
    
    const prevEl = document.getElementById("prevCh");
    const nextEl = document.getElementById("nextCh");
    const prevEl2 = document.getElementById("prevCh2");
    const nextEl2 = document.getElementById("nextCh2");
    
    if (prevEl) { prevEl.href = prevUrl; if (prevEl2) prevEl2.href = prevUrl; }
    if (nextEl) { nextEl.href = nextUrl; if (nextEl2) nextEl2.href = nextUrl; }
    
    // Update page title
    document.title = (data.title || "Chapter " + currentChapter) + " - Dex Manhwa";
    
    // Wire up download button
    const dlBtn = document.getElementById("downloadChapterBtn");
    if (dlBtn) {
        dlBtn.addEventListener("click", () => downloadChapter(seriesSlug, currentChapter, data));
    }
    
    // Save reading history
    const seriesData = await getSeries(seriesSlug);
    if (seriesData) {
        StorageService.saveHistory(seriesSlug, currentChapter, seriesData, data.title);
    }
}

// Daily download cap (localStorage-based, per user)
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

async function downloadChapter(slug, chapterNum, chapterData) {
    const MAX_DAILY = 10;
    if (getDownloadCount() >= MAX_DAILY) {
        alert(`Daily download limit reached (${MAX_DAILY}/day). Come back tomorrow.`);
        return;
    }
    
    const btn = document.getElementById("downloadChapterBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Downloading..."; }
    
    try {
        if (!chapterData || !chapterData.image_urls || chapterData.image_urls.length === 0) {
            alert("No images to download.");
            if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download Chapter"; }
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
        const imgFolder = zip.folder("ch" + chapterNum);
        
        let downloaded = 0;
        
        for (let i = 0; i < chapterData.image_urls.length; i++) {
            try {
                const imgUrl = "/proxy/image?url=" + encodeURIComponent(chapterData.image_urls[i]);
                const res = await fetch(imgUrl);
                if (!res.ok) continue;
                const blob = await res.blob();
                const ext = chapterData.image_urls[i].split(".").pop().split("?")[0] || "jpg";
                imgFolder.file(String(i + 1).padStart(3, "0") + "." + ext, blob);
                downloaded++;
            } catch (e) {
                console.warn("Image failed:", e);
            }
        }
        
        if (downloaded === 0) {
            alert("Could not download images. They may be hotlink-protected.");
            if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download Chapter"; }
            return;
        }
        
        const blob = await zip.generateAsync({ type: "blob" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = slug + "_ch" + chapterNum + ".zip";
        a.click();
        URL.revokeObjectURL(url);
        
        incrementDownloadCount();
        
        if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download Again"; }
    } catch (err) {
        console.error("Download failed:", err);
        alert("Download failed: " + err.message);
        if (btn) { btn.disabled = false; btn.innerHTML = "<span>⬇️</span> Download Chapter"; }
    }
}

function escapeHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
