class KeywordAutocomplete extends BaseAutocomplete {
    constructor(options) {
        super(options, { apiEndpoint: '/api/keywords' });
        this.chipsContainer = document.getElementById(options.chipsContainerId);
        this.selectedKeywords = new Set();
        this.fetchController = null;
        this.contextualCounts = {};
        this.start();
    }

    hasRequiredElements() {
        return super.hasRequiredElements() && Boolean(this.chipsContainer);
    }

    init() {
        this.contextualCounts = this.parseContextualCounts(this.chipsContainer);
        this.loadExistingKeywords();
        this.initSuggestedKeywords();
        this.bindInputEvents();
        if (this.form) {
            this.form.addEventListener('submit', () => this.syncHiddenInputs());
        }
        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', () => this.syncHiddenInputsToMainSearch());
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
            for (const keyword of this.selectedKeywords) {
                if (keyword) {
                    params.append('keyword', keyword);
                }
            }
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

        this.displaySuggestions(keywords.filter((item) => !this.selectedKeywords.has(item.keyword)));
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
    getSuggestionLabel(item) {
        return item.keyword;
    }

    // Prefer the response count for the current filter context, falling back
    // to the page's contextual counts when the API did not provide one.
    getSuggestionCount(item) {
        if (item.count !== undefined) {
            return item.count;
        }
        return this.contextualCounts[item.keyword] ?? 0;
    }

    setDataAttributes(element, item) {
        element.dataset.keyword = item.keyword;
    }

    selectSuggestion(item) {
        this.addKeyword(item.keyword);
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
        if (!this.selectedKeywords.delete(keyword)) {
            return;
        }
        const chip = [...this.chipsContainer.children].find((el) => el.dataset.keyword === keyword);
        if (chip) {
            chip.remove();
        }
        // Show suggested keywords again if no keywords are selected
        if (this.selectedKeywords.size === 0) {
            this.showSuggestedKeywords();
        }

        requestFilterFormSubmit(this.form);
    }

    renderChip(keyword) {
        const chip = this.createChip(keyword, this.contextualCounts[keyword], () => this.removeKeyword(keyword));
        this.setDataAttributes(chip, { keyword });
        this.chipsContainer.appendChild(chip);
    }

    syncHiddenInputs() {
        this.replaceHiddenInputs(this.form, 'keyword', [...this.selectedKeywords]);
    }

    syncHiddenInputsToMainSearch() {
        this.replaceHiddenInputs(this.mainSearchForm, 'keyword', [...this.selectedKeywords]);
    }
}

class OrganizationAutocomplete extends SingleSelectAutocomplete {
    constructor(options) {
        super(options, {
            apiEndpoint: '/api/organizations',
            suggestedContainerId: 'suggested-organizations',
            suggestedButtonSelector: '.tag-link--organization',
            hiddenInputName: 'org_slug',
            inputHintText: 'Start typing to select an organization',
        });
        this.start();
    }

    parseItems(data) {
        return (data.organizations || [])
            .sort((a, b) => {
                const countA = Number.isFinite(a.dataset_count) ? a.dataset_count : 0;
                const countB = Number.isFinite(b.dataset_count) ? b.dataset_count : 0;
                return countB - countA;
            })
            .map((item) => ({
                ...item,
                aliases: Array.isArray(item.aliases) ? item.aliases : [],
                slug: item.slug || '',
            }));
    }

    getInitialSelection() {
        const { initialOrgId: id, initialOrgName: name, initialOrgSlug: slug } = this.chipsContainer.dataset;
        return (id || slug) && name ? this.toSelection({ id, name, slug }) : null;
    }

    selectionFromButton(button) {
        const { orgId: id, orgName: name, orgSlug: slug } = button.dataset;
        return name ? this.toSelection({ id, name, slug }) : null;
    }

    toSelection(item) {
        return {
            id: item.id != null ? String(item.id) : '',
            name: item.name || '',
            slug: item.slug || '',
        };
    }

    getItemKey(item) {
        return item.slug;
    }

    getSelectionKey(item) {
        return (item.slug || item.id || '').toString().toLowerCase();
    }

    getItemTotal(item) {
        return item.dataset_count;
    }

    matchesQuery(item, query) {
        return [item.name, item.slug, ...item.aliases]
            .map((value) => (value || '').toLowerCase())
            .some((value) => value.includes(query));
    }

    getHiddenInputValue(selection) {
        return selection.slug || selection.name;
    }

    setDataAttributes(element, item) {
        if (item.id) {
            element.dataset.orgId = String(item.id);
        }
        if (item.slug) {
            element.dataset.orgSlug = item.slug;
        }
    }
}

class PublisherAutocomplete extends SingleSelectAutocomplete {
    constructor(options) {
        super(options, {
            apiEndpoint: '/api/publishers',
            suggestedContainerId: 'suggested-publishers',
            suggestedButtonSelector: '.tag-link--publisher',
            hiddenInputName: 'publisher',
            inputHintText: 'Start typing to select a publisher',
        });
        this.start();
    }

    parseItems(data) {
        return (data.publishers || []).filter((item) => item.name);
    }

    getInitialSelection() {
        const name = this.chipsContainer.dataset.initialPublisherName;
        return name ? { name } : null;
    }

    selectionFromButton(button) {
        const name = button.dataset.publisherName;
        return name ? { name } : null;
    }

    toSelection(item) {
        return { name: item.name };
    }

    getItemKey(item) {
        return item.name;
    }

    getSelectionKey(item) {
        return (item.name || '').toLowerCase();
    }

    getItemTotal(item) {
        return item.count;
    }

    matchesQuery(item, query) {
        return item.name.toLowerCase().includes(query);
    }

    getHiddenInputValue(selection) {
        return selection.name;
    }

    setDataAttributes(element, item) {
        element.dataset.publisherName = item.name;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const keywordInput = document.getElementById('keyword-input');
    const keywordChips = document.getElementById('keyword-chips');
    const keywordSuggestions = document.getElementById('keyword-suggestions');
    if (keywordInput && keywordChips && keywordSuggestions) {
        new KeywordAutocomplete({
            inputId: 'keyword-input',
            chipsContainerId: 'keyword-chips',
            suggestionsId: 'keyword-suggestions',
            formId: 'filter-form',
            mainSearchFormId: 'main-search-form',
            apiEndpoint: '/api/keywords',
            debounceDelay: 300
        });
    }

    const organizationInput = document.getElementById('organization-input');
    const organizationChips = document.getElementById('organization-chips');
    const organizationSuggestions = document.getElementById('organization-suggestions');
    if (organizationInput && organizationChips && organizationSuggestions) {
        new OrganizationAutocomplete({
            inputId: 'organization-input',
            chipsContainerId: 'organization-chips',
            suggestionsId: 'organization-suggestions',
            formId: 'filter-form',
            mainSearchFormId: 'main-search-form',
            apiEndpoint: '/api/organizations',
            debounceDelay: 300,
            suggestedContainerId: 'suggested-organizations'
        });
    }

    const publisherInput = document.getElementById('publisher-input');
    const publisherChips = document.getElementById('publisher-chips');
    const publisherSuggestions = document.getElementById('publisher-suggestions');
    if (publisherInput && publisherChips && publisherSuggestions) {
        new PublisherAutocomplete({
            inputId: 'publisher-input',
            chipsContainerId: 'publisher-chips',
            suggestionsId: 'publisher-suggestions',
            formId: 'filter-form',
            mainSearchFormId: 'main-search-form',
            apiEndpoint: '/api/publishers',
            debounceDelay: 300,
            suggestedContainerId: 'suggested-publishers'
        });
    }
});