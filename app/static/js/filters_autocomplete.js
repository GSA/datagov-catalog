function requestFilterFormSubmit(form, options = {}) {
    const controller = window.dataGovFilterFormAutoSubmit;
    if (controller && typeof controller.request === 'function' && controller.form) {
        controller.request(options);
        return;
    }

    if (controller && typeof controller.captureMapPanelState === 'function') {
        controller.captureMapPanelState();
    }

    if (!form) {
        return;
    }

    if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
    } else {
        form.submit();
    }
}

class KeywordAutocomplete {
    constructor(options) {
        this.inputId = options.inputId;
        this.chipsContainerId = options.chipsContainerId;
        this.suggestionsId = options.suggestionsId;
        this.apiEndpoint = options.apiEndpoint || '/api/keywords';
        this.formId = options.formId;
        this.mainSearchFormId = options.mainSearchFormId;
        this.debounceDelay = options.debounceDelay || 300;
        this.input = document.getElementById(this.inputId);
        this.chipsContainer = document.getElementById(this.chipsContainerId);
        this.suggestionsContainer = document.getElementById(this.suggestionsId);
        this.form = document.getElementById(this.formId);
        this.mainSearchForm = document.getElementById(this.mainSearchFormId); // NEW
        this.selectedKeywords = new Set();
        this.fetchController = null;
        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.contextualCounts = {};
        if (!this.input || !this.chipsContainer || !this.suggestionsContainer) {
            console.error('KeywordAutocomplete: Required elements not found');
            return;
        }
        // Load contextual counts from data attribute
        const countsData = this.chipsContainer.dataset.contextualCounts;
        if (countsData) {
            try {
                this.contextualCounts = JSON.parse(countsData);
            } catch (e) {
                console.error('Failed to parse contextual counts:', e);
            }
        } else {
            console.warn('No contextual counts data found in HTML');
        }

        this.init();
    }

    init() {
        // Load any existing keywords from URL parameters
        this.loadExistingKeywords();
        // Initialize suggested keywords click handlers
        this.initSuggestedKeywords();
        // Event listeners
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.input.addEventListener('focus', () => this.showSuggestions());
        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
        // Sync chips to hidden inputs on form submit
        if (this.form) {
            this.form.addEventListener('submit', () => this.syncHiddenInputs());
        }
        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', (e) => {
                this.syncHiddenInputsToMainSearch();
            });
        }
    }
    async fetchSuggestions(query) {
        // Cancel any in-flight request before starting a new one.
        if (this.fetchController) {
            this.fetchController.abort();
        }
        this.fetchController = new AbortController();

        try {
            const params = new URLSearchParams({ search: query, size: 10 });
            const response = await fetch(`${this.apiEndpoint}?${params}`, {
                signal: this.fetchController.signal,
            });
            const data = await response.json();
            return data.keywords || [];
        } catch (error) {
            if (error.name === 'AbortError') {
                return null; // Request was superseded — caller should do nothing.
            }
            console.error('Error fetching keyword suggestions:', error);
            return [];
        }
    }
    async filterAndShowSuggestions(query) {
        const keywords = await this.fetchSuggestions(query);
        if (keywords === null) {
            return; // Aborted by a newer keystroke.
        }

        const filtered = keywords.filter(
            item => !this.selectedKeywords.has(item.keyword)
        );

        if (filtered.length > 0) {
            this.renderSuggestions(filtered);
            this.showSuggestions();
        } else {
            this.hideSuggestions();
        }
    }
    loadExistingKeywords() {
        // Load keywords from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const keywords = urlParams.getAll('keyword');
        keywords.forEach(keyword => {
            if (keyword && keyword.trim()) {
                this.addKeyword(keyword.trim(), { silent: true });
            }
        });
    }
    initSuggestedKeywords() {
        // Add click handlers to suggested keyword buttons
        const suggestedContainer = document.getElementById('suggested-keywords');
        if (!suggestedContainer) return;
        const suggestedButtons = suggestedContainer.querySelectorAll('.tag-link--suggested');
        suggestedButtons.forEach(button => {
            button.addEventListener('click', () => {
                const keyword = button.dataset.keyword;
                if (keyword) {
                    this.addKeyword(keyword);
                }
            });
        });
    }
    hideSuggestedKeywords() {
        const suggestedContainer = document.getElementById('suggested-keywords');
        if (suggestedContainer) {
            suggestedContainer.style.display = 'none';
        }
    }
    showSuggestedKeywords() {
        const suggestedContainer = document.getElementById('suggested-keywords');
        if (suggestedContainer && this.selectedKeywords.size === 0) {
            suggestedContainer.style.display = 'block';
        }
    }
    handleInput(e) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length === 0) {
                this.hideSuggestions();
            } else {
                this.filterAndShowSuggestions(query);
            }
        }, this.debounceDelay);
    }
    handleKeyDown(e) {
        const suggestions = this.suggestionsContainer.querySelectorAll('.keyword-suggestion');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.currentFocusIndex = Math.min(this.currentFocusIndex + 1, suggestions.length - 1);
            this.updateSuggestionFocus(suggestions);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.currentFocusIndex = Math.max(this.currentFocusIndex - 1, 0);
            this.updateSuggestionFocus(suggestions);
        } else if (e.key === 'Enter') {
            // Enter applies the filter: stage the focused (or first) suggestion,
            // then submit the form even though it is in deferred mode.
            e.preventDefault();
            let selected = null;
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                selected = suggestions[this.currentFocusIndex];
            } else if (suggestions.length > 0) {
                selected = suggestions[0];
            }
            if (selected) {
                this.addKeyword(selected.dataset.keyword, { silent: true });
            }
            this.input.value = '';
            this.hideSuggestions();
            requestFilterFormSubmit(this.form, { force: true });
        } else if (e.key === 'Tab') {
            // Tab stages the focused suggestion without submitting.
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                e.preventDefault();
                const keyword = suggestions[this.currentFocusIndex].dataset.keyword;
                this.addKeyword(keyword);
                this.input.value = '';
                this.hideSuggestions();
            }
        } else if (e.key === 'Escape') {
            this.hideSuggestions();
        }
    }
    updateSuggestionFocus(suggestions) {
        suggestions.forEach((item, index) => {
            if (index === this.currentFocusIndex) {
                item.classList.add('keyword-suggestion--focused');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('keyword-suggestion--focused');
            }
        });
    }
    renderSuggestions(keywords) {
        this.suggestionsContainer.innerHTML = '';
        this.currentFocusIndex = -1;


        keywords.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            div.dataset.keyword = item.keyword;

            // Use contextual count if available, otherwise use the item's count
            const displayCount = this.contextualCounts[item.keyword] !== undefined
                ? this.contextualCounts[item.keyword]
                : item.count;

            const textSpan = document.createElement('span');
            textSpan.className = 'keyword-suggestion__text';
            textSpan.appendChild(this.highlightMatch(item.keyword, this.input.value));
            const countSpan = document.createElement('span');
            countSpan.className = 'keyword-suggestion__count';
            countSpan.textContent = displayCount;
            div.appendChild(textSpan);
            div.appendChild(countSpan);
            div.addEventListener('click', () => {
                this.addKeyword(item.keyword);
                this.input.value = '';
                this.hideSuggestions();
            });
            this.suggestionsContainer.appendChild(div);
        });
    }
    highlightMatch(text, query) {
        const fragment = document.createDocumentFragment();
        const index = text.toLowerCase().indexOf(query.toLowerCase());
        if (index === -1) {
            fragment.appendChild(document.createTextNode(text));
            return fragment;
        }
        fragment.appendChild(document.createTextNode(text.substring(0, index)));
        const strong = document.createElement('strong');
        strong.textContent = text.substring(index, index + query.length);
        fragment.appendChild(strong);
        fragment.appendChild(document.createTextNode(text.substring(index + query.length)));
        return fragment;
    }
    showSuggestions() {
        this.suggestionsContainer.classList.add('keyword-suggestions--visible');
    }
    hideSuggestions() {
        this.suggestionsContainer.classList.remove('keyword-suggestions--visible');
        this.currentFocusIndex = -1;
    }
    addKeyword(keyword, options = {}) {
        const silent = Boolean(options.silent);
        if (this.selectedKeywords.has(keyword)) {
            return; // Already added
        }

        this.selectedKeywords.add(keyword);
        this.renderChip(keyword);


        if (!silent) {
            requestFilterFormSubmit(this.form);
        }
    }

    removeKeyword(keyword) {
        const removed = this.selectedKeywords.delete(keyword);
        if (!removed) {
            return;
        }
        const chip = this.chipsContainer.querySelector(`[data-keyword="${this.escapeHtml(keyword)}"]`);
        if (chip) {
            chip.remove();
        }
        // Show suggested keywords again if no keywords are selected
        if (this.selectedKeywords.size === 0) {
            this.showSuggestedKeywords();
        }

        // Removing a chip applies immediately (force past the deferred panel).
        requestFilterFormSubmit(this.form, { force: true });
    }

    // Remove every selected keyword without submitting. Used by the filter
    // dropdown "Clear" action, which submits once afterward itself.
    clearAll() {
        this.selectedKeywords.clear();
        this.chipsContainer.innerHTML = '';
        this.syncHiddenInputs();
        this.showSuggestedKeywords();
    }
    renderChip(keyword) {
        const chip = document.createElement('div');
        chip.className = 'tag-link';
        chip.dataset.keyword = keyword;
        const count = this.contextualCounts[keyword];

        const textSpan = document.createElement('span');
        textSpan.className = 'keyword-chip__text';
        textSpan.textContent = keyword;
        if (count) {
            const countSpan = document.createElement('span');
            countSpan.className = 'tag-link__count';
            countSpan.textContent = `(${count})`;
            textSpan.appendChild(countSpan);
        }

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'keyword-chip__remove';
        removeBtn.setAttribute('aria-label', `Remove ${keyword}`);
        const icon = document.createElement('i');
        icon.className = 'fa-solid fa-xmark';
        removeBtn.appendChild(icon);

        chip.appendChild(textSpan);
        chip.appendChild(removeBtn);
        removeBtn.addEventListener('click', () => {
            this.removeKeyword(keyword);
        });
        this.chipsContainer.appendChild(chip);
    }
    syncHiddenInputs() {
        // Remove existing keyword hidden inputs from filter form
        const existingInputs = this.form.querySelectorAll('input[name="keyword"]');
        existingInputs.forEach(input => input.remove());
        // Add hidden input for each selected keyword
        this.selectedKeywords.forEach(keyword => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'keyword';
            input.value = keyword;
            this.form.appendChild(input);
        });
    }

    // Sync various args to hidden inputs in the main search form
    syncHiddenInputsToMainSearch() {
        if (!this.mainSearchForm) return;
        // Remove existing keyword hidden inputs from main search form
        const existingInputs = this.mainSearchForm.querySelectorAll('input[name="keyword"][type="hidden"]');
        existingInputs.forEach(input => input.remove());
        // Add hidden input for each selected keyword
        this.selectedKeywords.forEach(keyword => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'keyword';
            input.value = keyword;
            this.mainSearchForm.appendChild(input);
        });
    }
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const keywordInput = document.getElementById('keyword-input');
    const keywordChips = document.getElementById('keyword-chips');
    const keywordSuggestions = document.getElementById('keyword-suggestions');
    if (keywordInput && keywordChips && keywordSuggestions) {
        window.dataGovKeywordAutocomplete = new KeywordAutocomplete({
            inputId: 'keyword-input',
            chipsContainerId: 'keyword-chips',
            suggestionsId: 'keyword-suggestions',
            formId: 'filter-form',
            mainSearchFormId: 'main-search-form', // NEW: main search form ID
            apiEndpoint: '/api/keywords',
            debounceDelay: 300
        });
    }

    // Organization and Publisher are now USWDS combo boxes wired up in
    // filter_dropdowns.js, not custom autocompletes.
});