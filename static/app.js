(() => {
    'use strict';

    const refreshBtn   = document.getElementById('refresh-btn');
    const refreshIcon  = document.getElementById('refresh-icon');
    const spinner      = document.getElementById('spinner');
    const refreshLabel = document.getElementById('refresh-label');
    const releasesList = document.getElementById('releases-list');
    const errorBanner  = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const skeletonContainer = document.getElementById('skeleton-container');
    const countBar     = document.getElementById('count-bar');
    const releaseCount = document.getElementById('release-count');

    let isLoading = false;

    /* ---- Helpers ---- */
    const formatDate = (isoString) => {
        if (!isoString) return 'Unknown date';
        try {
            const d = new Date(isoString);
            return d.toLocaleDateString('en-US', {
                year: 'numeric', month: 'long', day: 'numeric'
            });
        } catch { return isoString; }
    };

    const setLoading = (loading) => {
        isLoading = loading;
        refreshBtn.disabled = loading;
        refreshIcon.style.display = loading ? 'none' : 'flex';
        spinner.style.display    = loading ? 'flex'  : 'none';
        refreshLabel.textContent = loading ? 'Loading…' : 'Refresh';
        if (loading) spinner.style.animation = 'spin 0.8s linear infinite';
    };

    const showError = (msg) => {
        errorMessage.textContent = msg || 'Failed to load release notes. Please try again.';
        errorBanner.style.display = 'flex';
    };

    const hideError = () => { errorBanner.style.display = 'none'; };

    const twitterSVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.259 5.63zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>`;

    const calendarSVG = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
    </svg>`;

    /* ---- Build a card ---- */
    const buildCard = (release, index) => {
        const card = document.createElement('div');
        card.className = 'release-card';
        card.style.animationDelay = `${index * 40}ms`;

        const tweetText  = encodeURIComponent(`[BigQuery Update] ${release.title}`);
        const tweetUrl   = encodeURIComponent(release.link || '');
        const intentUrl  = `https://twitter.com/intent/tweet?text=${tweetText}&url=${tweetUrl}`;
        const displayDate = formatDate(release.date);

        const titleHtml = release.link
            ? `<a href="${release.link}" target="_blank" rel="noopener noreferrer">${release.title}</a>`
            : release.title;

        card.innerHTML = `
            <div class="release-card-header">
                <h2 class="release-title">${titleHtml}</h2>
            </div>
            <div class="release-meta">
                <span class="release-date">${calendarSVG} ${displayDate}</span>
            </div>
            <div class="release-content">${release.content || '<em>No description available.</em>'}</div>
            <div class="release-actions">
                <a class="tweet-btn"
                   href="${intentUrl}"
                   target="_blank"
                   rel="noopener noreferrer"
                   aria-label="Share this update on X (Twitter)">
                    ${twitterSVG} Tweet this
                </a>
            </div>
        `;
        return card;
    };

    /* ---- Render list ---- */
    const renderReleases = (releases) => {
        releasesList.innerHTML = '';

        if (!Array.isArray(releases) || releases.length === 0) {
            releasesList.innerHTML = `<p style="color:var(--text-secondary);text-align:center;padding:48px 0;">No release notes found.</p>`;
        } else {
            releases.forEach((release, i) => {
                releasesList.appendChild(buildCard(release, i));
            });
            releaseCount.textContent = `${releases.length} update${releases.length !== 1 ? 's' : ''}`;
            countBar.style.display = 'flex';
        }

        skeletonContainer.style.display = 'none';
        releasesList.style.display = 'flex';
    };

    /* ---- Fetch ---- */
    const fetchReleases = async () => {
        if (isLoading) return;
        setLoading(true);
        hideError();

        // Show skeletons only on the very first load
        if (releasesList.children.length === 0) {
            skeletonContainer.style.display = 'flex';
            releasesList.style.display = 'none';
            countBar.style.display = 'none';
        }

        try {
            const res = await fetch('/api/releases');
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.error || `Server error ${res.status}`);
            }
            const releases = await res.json();
            renderReleases(releases);
        } catch (err) {
            skeletonContainer.style.display = 'none';
            showError(err.message || 'Failed to load release notes.');
        } finally {
            setLoading(false);
        }
    };

    /* ---- Bootstrap ---- */
    refreshBtn.addEventListener('click', fetchReleases);
    fetchReleases();
})();
