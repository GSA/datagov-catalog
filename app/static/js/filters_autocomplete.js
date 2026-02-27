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
        this.allKeywords = [];
        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.contextualCounts = {};
        if (!this.input || !this.chipsContainer || !this.suggestionsContainer) {
            console.error('KeywordAutocomplete: Required elements not found');
            return;
        }
        // Load contextual counts from data attribute
        const countsData = this.chipsContainer.dataset.contextualCounts;
        console.log('Raw contextual counts data:', countsData ? countsData.substring(0, 200) + '...' : 'NONE');
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
        // Load all keywords from API, then apply contextual counts
        this.loadKeywords();
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
    async loadKeywords() {
        try {
            const response = await fetch(`${this.apiEndpoint}?size=500`);
            const data = await response.json();
            this.allKeywords = data.keywords || [];
        } catch (error) {
            console.error('Error loading keywords:', error);
            this.allKeywords = [];
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
        } else if (e.key === 'Enter' || e.key === 'Tab') {
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
    filterAndShowSuggestions(query) {
        // Filter keywords that match the query and aren't already selected
        const filtered = this.allKeywords.filter(item => {
            const keyword = item.keyword.toLowerCase();
            const matchesQuery = keyword.includes(query);
            const notSelected = !this.selectedKeywords.has(item.keyword);

            // If we have contextual counts, only show keywords with count > 0
            const hasContextualCount = Object.keys(this.contextualCounts).length > 0;
            const hasCount = !hasContextualCount || (this.contextualCounts[item.keyword] > 0);

            return matchesQuery && notSelected && hasCount;
        });

        // Limit to top 10 results
        const topResults = filtered.slice(0, 10);

        if (topResults.length > 0) {
            this.renderSuggestions(topResults);
            this.showSuggestions();
        } else {
            this.hideSuggestions();
        }
    }

    renderSuggestions(keywords) {
        this.suggestionsContainer.innerHTML = '';
        this.currentFocusIndex = -1;

        console.log('Rendering suggestions with contextual counts:', Object.keys(this.contextualCounts).length > 0);

        keywords.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            div.dataset.keyword = item.keyword;

            // Use contextual count if available, otherwise use the item's count
            const displayCount = this.contextualCounts[item.keyword] !== undefined
                ? this.contextualCounts[item.keyword]
                : item.count;

            div.innerHTML = `
                <span class="keyword-suggestion__text">${this.highlightMatch(item.keyword, this.input.value)}</span>
                <span class="keyword-suggestion__count">${displayCount}</span>
            `;
            div.addEventListener('click', () => {
                this.addKeyword(item.keyword);
                this.input.value = '';
                this.hideSuggestions();
            });
            this.suggestionsContainer.appendChild(div);
        });
    }
    highlightMatch(text, query) {
        const index = text.toLowerCase().indexOf(query.toLowerCase());
        if (index === -1) return text;
        const before = text.substring(0, index);
        const match = text.substring(index, index + query.length);
        const after = text.substring(index + query.length);
        return `${before}<strong>${match}</strong>${after}`;
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

        requestFilterFormSubmit(this.form);
    }
    renderChip(keyword) {
        const chip = document.createElement('div');
        chip.className = 'tag-link';
        chip.dataset.keyword = keyword;
        const count = this.contextualCounts[keyword];
        const countHtml = count ? `<span class="tag-link__count">(${count})</span>` : '';
        chip.innerHTML = `
            <span class="keyword-chip__text">${this.escapeHtml(keyword)}${countHtml}</span>
            <button type="button" class="keyword-chip__remove" aria-label="Remove ${this.escapeHtml(keyword)}">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;
        const removeBtn = chip.querySelector('.keyword-chip__remove');
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

class OrganizationAutocomplete {
    constructor(options) {
        this.inputId = options.inputId;
        this.chipsContainerId = options.chipsContainerId;
        this.suggestionsId = options.suggestionsId;
        this.apiEndpoint = options.apiEndpoint || '/api/organizations';
        this.formId = options.formId;
        this.mainSearchFormId = options.mainSearchFormId;
        this.debounceDelay = options.debounceDelay || 300;
        this.requestSize = options.requestSize || 500;
        this.suggestedContainerId = options.suggestedContainerId || 'suggested-organizations';

        this.input = document.getElementById(this.inputId);
        this.chipsContainer = document.getElementById(this.chipsContainerId);
        this.suggestionsContainer = document.getElementById(this.suggestionsId);
        this.form = document.getElementById(this.formId);
        this.mainSearchForm = document.getElementById(this.mainSearchFormId);
        this.suggestedContainer = null;

        this.organizations = [];
        this.selectedOrganization = null;
        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.numberFormatter = new Intl.NumberFormat();
        this.initialSelection = options.initialSelection || this.getInitialSelection();
        this.contextualCounts = {};

        if (!this.input || !this.chipsContainer || !this.suggestionsContainer) {
            console.error('OrganizationAutocomplete: Required elements not found');
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
        }

        this.init();
    }

    init() {
        this.loadOrganizations();
        this.initSuggestedOrganizations();

        if (this.initialSelection) {
            this.setOrganization(this.initialSelection, { silent: true });
            this.hideSuggestedOrganizations();
        }

        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.input.addEventListener('focus', () => this.showSuggestions());

        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });

        if (this.form) {
            this.form.addEventListener('submit', () => this.syncHiddenInputs());
        }

        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', () => this.syncHiddenInputs());
        }
    }

    initSuggestedOrganizations() {
        this.suggestedContainer = document.getElementById(this.suggestedContainerId);
        if (!this.suggestedContainer) {
            return;
        }

        const buttons = this.suggestedContainer.querySelectorAll('.tag-link--organization');
        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                const orgId = button.dataset.orgId;
                const orgName = button.dataset.orgName;
                const orgSlug = button.dataset.orgSlug;
                if (orgName) {
                    this.setOrganization({ id: orgId, name: orgName, slug: orgSlug });
                    this.input.value = '';
                    this.hideSuggestedOrganizations();
                }
            });
        });
    }

    getInitialSelection() {
        if (!this.chipsContainer || !this.chipsContainer.dataset) {
            return null;
        }

        const id = this.chipsContainer.dataset.initialOrgId;
        const name = this.chipsContainer.dataset.initialOrgName;
        const slug = this.chipsContainer.dataset.initialOrgSlug;

        if ((id || slug) && name) {
            return { id, name, slug };
        }

        return null;
    }

    async loadOrganizations() {
        try {
            const response = await fetch(`${this.apiEndpoint}?size=${this.requestSize}`);
            const data = await response.json();
            const organizations = data.organizations || [];
            this.organizations = organizations
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
        } catch (error) {
            console.error('Error loading organizations:', error);
            this.organizations = [];
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
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                e.preventDefault();
                const orgId = suggestions[this.currentFocusIndex].dataset.orgId;
                const orgSlug = suggestions[this.currentFocusIndex].dataset.orgSlug;
                const organization = this.organizations.find((item) => {
                    if (orgSlug) {
                        return (item.slug || '').toString() === orgSlug;
                    }
                    return String(item.id) === String(orgId);
                });
                if (organization) {
                    this.setOrganization({
                        id: organization.id != null ? String(organization.id) : undefined,
                        name: organization.name,
                        slug: organization.slug,
                    });
                }
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

    filterAndShowSuggestions(query) {
        const filtered = this.organizations.filter((item) => {
            const name = (item.name || '').toLowerCase();
            const slug = (item.slug || '').toLowerCase();
            const aliases = Array.isArray(item.aliases)
                ? item.aliases.map((alias) => (alias || '').toLowerCase())
                : [];

            const currentKey = this.selectedOrganization
                ? (this.selectedOrganization.slug || this.selectedOrganization.id || '')
                    .toString()
                    .toLowerCase()
                : null;
            const itemKey = (item.slug || item.id || '').toString().toLowerCase();
            const alreadySelected = currentKey && currentKey === itemKey;

            if (alreadySelected) {
                return false;
            }

            const aliasMatch = aliases.some((alias) => alias.includes(query));
            return (
                name.includes(query) || slug.includes(query) || aliasMatch
            );
        });

        const topResults = filtered.slice(0, 10);

        if (topResults.length > 0) {
            this.renderSuggestions(topResults);
            this.showSuggestions();
        } else {
            this.hideSuggestions();
        }
    }

    renderSuggestions(items) {
        this.suggestionsContainer.innerHTML = '';
        this.currentFocusIndex = -1;

        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            if (item.id !== undefined) {
                div.dataset.orgId = String(item.id);
            }
            if (item.slug) {
                div.dataset.orgSlug = item.slug;
            }
            div.innerHTML = `
                <span class="keyword-suggestion__text">${this.highlightMatch(item.name, this.input.value)}</span>
                <span class="keyword-suggestion__count">${this.formatCount(item.dataset_count || 0)}</span>
            `;

            div.addEventListener('click', () => {
                this.setOrganization({
                    id: item.id != null ? String(item.id) : undefined,
                    name: item.name,
                    slug: item.slug,
                });
                this.input.value = '';
                this.hideSuggestions();
            });

            this.suggestionsContainer.appendChild(div);
        });
    }

    setOrganization(organization, options = {}) {
        const silent = Boolean(options.silent);
        if (!organization) {
            return;
        }

        const normalizedId = organization.id != null ? String(organization.id) : '';
        const normalizedSlug = organization.slug || '';
        this.selectedOrganization = {
            id: normalizedId,
            name: organization.name || '',
            slug: normalizedSlug,
        };
        this.renderChip(this.selectedOrganization);
        this.syncHiddenInputs();
        this.hideSuggestedOrganizations();

        if (!silent) {
            requestFilterFormSubmit(this.form);
        }
    }

    renderChip(organization) {
        this.chipsContainer.innerHTML = '';

        const chip = document.createElement('div');
        chip.className = 'tag-link';
        if (organization.id) {
            chip.dataset.orgId = organization.id;
        }
        if (organization.slug) {
            chip.dataset.orgSlug = organization.slug;
        }

        const count = organization.slug ? this.contextualCounts[organization.slug] : null;
        const countHtml = count ? ` <span class="tag-link__count">(${this.formatCount(count)})</span>` : '';

        chip.innerHTML = `
            <span class="keyword-chip__text">${this.escapeHtml(organization.name)}${countHtml}</span>
            <button type="button" class="keyword-chip__remove" aria-label="Remove ${this.escapeHtml(organization.name)}">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        const removeBtn = chip.querySelector('.keyword-chip__remove');
        removeBtn.addEventListener('click', () => {
            this.clearSelection();
        });

        this.chipsContainer.appendChild(chip);
    }

    clearSelection() {
        this.selectedOrganization = null;
        this.chipsContainer.innerHTML = '';
        this.syncHiddenInputs();
        this.showSuggestedOrganizations();
        requestFilterFormSubmit(this.form);
    }

    syncHiddenInputs() {
        this.syncFormHiddenInputs(this.form);
        this.syncFormHiddenInputs(this.mainSearchForm);
    }

    syncFormHiddenInputs(form) {
        if (!form) {
            return;
        }

        const existing = form.querySelectorAll('input[name="org_slug"][type="hidden"]');
        existing.forEach((input) => input.remove());

        if (this.selectedOrganization) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'org_slug';
            input.value = this.selectedOrganization.slug || this.selectedOrganization.name;
            form.appendChild(input);
        }
    }

    highlightMatch(text, query) {
        if (!text) {
            return '';
        }

        const normalizedText = text.toLowerCase();
        const normalizedQuery = query.toLowerCase();
        const index = normalizedText.indexOf(normalizedQuery);
        if (index === -1 || !query) {
            return this.escapeHtml(text);
        }

        const before = this.escapeHtml(text.substring(0, index));
        const match = this.escapeHtml(text.substring(index, index + query.length));
        const after = this.escapeHtml(text.substring(index + query.length));

        return `${before}<strong>${match}</strong>${after}`;
    }

    showSuggestions() {
        this.suggestionsContainer.classList.add('keyword-suggestions--visible');
        this.input.setAttribute('aria-expanded', 'true');
    }

    hideSuggestions() {
        this.suggestionsContainer.classList.remove('keyword-suggestions--visible');
        this.currentFocusIndex = -1;
        this.input.setAttribute('aria-expanded', 'false');
    }

    formatCount(value) {
        const count = Number.isFinite(value) ? value : 0;
        return this.numberFormatter.format(count);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    hideSuggestedOrganizations() {
        if (this.suggestedContainer) {
            this.suggestedContainer.style.display = 'none';
        }
    }

    showSuggestedOrganizations() {
        if (this.suggestedContainer && !this.selectedOrganization) {
            this.suggestedContainer.style.display = 'block';
        }
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
            mainSearchFormId: 'main-search-form', // NEW: main search form ID
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
            requestSize: 500,
            suggestedContainerId: 'suggested-organizations'
        });
    }
});