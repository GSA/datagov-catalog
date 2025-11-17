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
        
        if (!this.input || !this.chipsContainer || !this.suggestionsContainer) {
            console.error('KeywordAutocomplete: Required elements not found');
            return;
        }
        
        this.init();
    }
    
    init() {
        // Load all keywords from API
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
                this.addKeyword(keyword.trim());
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
                    // Hide suggested keywords container after selection
                    this.hideSuggestedKeywords();
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
            return keyword.includes(query) && !this.selectedKeywords.has(item.keyword);
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
        
        keywords.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            div.dataset.keyword = item.keyword;
            div.innerHTML = `
                <span class="keyword-suggestion__text">${this.highlightMatch(item.keyword, this.input.value)}</span>
                <span class="keyword-suggestion__count">${item.count}</span>
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
    
    addKeyword(keyword) {
        if (this.selectedKeywords.has(keyword)) {
            return; // Already added
        }
        
        this.selectedKeywords.add(keyword);
        this.renderChip(keyword);
        
        // Hide suggested keywords container
        this.hideSuggestedKeywords();
    }
    
    removeKeyword(keyword) {
        this.selectedKeywords.delete(keyword);
        const chip = this.chipsContainer.querySelector(`[data-keyword="${this.escapeHtml(keyword)}"]`);
        if (chip) {
            chip.remove();
        }
        
        // Show suggested keywords again if no keywords are selected
        if (this.selectedKeywords.size === 0) {
            this.showSuggestedKeywords();
        }
    }
    
    renderChip(keyword) {
        const chip = document.createElement('div');
        chip.className = 'tag-link';
        chip.dataset.keyword = keyword;
        chip.innerHTML = `
            <span class="keyword-chip__text">${this.escapeHtml(keyword)}</span>
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const keywordAutocomplete = new KeywordAutocomplete({
        inputId: 'keyword-input',
        chipsContainerId: 'keyword-chips',
        suggestionsId: 'keyword-suggestions',
        formId: 'filter-form',
        mainSearchFormId: 'main-search-form', // NEW: main search form ID
        apiEndpoint: '/api/keywords',
        debounceDelay: 300
    });
});