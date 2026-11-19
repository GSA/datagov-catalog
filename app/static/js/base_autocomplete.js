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

// Subclasses implement init(), filterAndShowSuggestions(query), getSuggestionLabel(item),
// and selectSuggestion(item), and call this.start() at the end of their constructor.
// Optional hooks: hasRequiredElements(), getSuggestionCount(item), setDataAttributes(element, item).
class BaseAutocomplete {
    constructor(options, defaults = {}) {
        this.inputId = options.inputId;
        this.suggestionsId = options.suggestionsId;
        this.apiEndpoint = options.apiEndpoint || defaults.apiEndpoint;
        this.formId = options.formId;
        this.mainSearchFormId = options.mainSearchFormId;
        this.debounceDelay = options.debounceDelay ?? 300;
        this.minQueryLength = defaults.minQueryLength ?? 1;

        this.input = document.getElementById(this.inputId);
        this.suggestionsContainer = document.getElementById(this.suggestionsId);
        this.form = document.getElementById(this.formId);
        this.mainSearchForm = document.getElementById(this.mainSearchFormId);

        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.renderedSuggestions = [];
    }

    start() {
        if (!this.hasRequiredElements()) {
            console.error(`${this.constructor.name}: Required elements not found`);
            return;
        }
        this.init();
    }

    hasRequiredElements() {
        return Boolean(this.input && this.suggestionsContainer);
    }

    init() {
        throw new Error(`${this.constructor.name} must implement init()`);
    }

    bindInputEvents() {
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.input.addEventListener('focus', () => this.showSuggestions());
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    handleInput(e) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < this.minQueryLength) {
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
            const item = this.renderedSuggestions[this.currentFocusIndex];
            if (this.currentFocusIndex >= 0 && item) {
                e.preventDefault();
                this.chooseSuggestion(item);
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

    filterAndShowSuggestions() {
        throw new Error(`${this.constructor.name} must implement filterAndShowSuggestions()`);
    }

    displaySuggestions(items) {
        if (items.length > 0) {
            this.renderSuggestions(items);
            this.showSuggestions();
        } else {
            this.hideSuggestions();
        }
    }

    renderSuggestions(items) {
        this.suggestionsContainer.replaceChildren();
        this.currentFocusIndex = -1;
        this.renderedSuggestions = items;

        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            this.setDataAttributes(div, item);

            const textSpan = document.createElement('span');
            textSpan.className = 'keyword-suggestion__text';
            textSpan.appendChild(this.highlightMatch(this.getSuggestionLabel(item), this.input.value.trim()));
            div.appendChild(textSpan);

            const count = this.getSuggestionCount(item);
            if (count !== null) {
                const countSpan = document.createElement('span');
                countSpan.className = 'keyword-suggestion__count';
                countSpan.textContent = count;
                div.appendChild(countSpan);
            }

            div.addEventListener('click', () => this.chooseSuggestion(item));
            this.suggestionsContainer.appendChild(div);
        });
    }

    getSuggestionLabel() {
        throw new Error(`${this.constructor.name} must implement getSuggestionLabel()`);
    }

    getSuggestionCount() {
        return null;
    }

    setDataAttributes() {}

    chooseSuggestion(item) {
        this.selectSuggestion(item);
        this.input.value = '';
        this.hideSuggestions();
    }

    selectSuggestion() {
        throw new Error(`${this.constructor.name} must implement selectSuggestion()`);
    }

    highlightMatch(text, query) {
        const fragment = document.createDocumentFragment();
        if (!text) {
            return fragment;
        }

        const index = text.toLowerCase().indexOf(query.toLowerCase());
        if (index === -1 || !query) {
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
        if (this.renderedSuggestions.length === 0) {
            return;
        }
        this.suggestionsContainer.classList.add('keyword-suggestions--visible');
        this.input.setAttribute('aria-expanded', 'true');
    }

    hideSuggestions() {
        this.suggestionsContainer.classList.remove('keyword-suggestions--visible');
        this.currentFocusIndex = -1;
        this.input.setAttribute('aria-expanded', 'false');
    }

    parseContextualCounts(element) {
        const countsData = element.dataset.contextualCounts;
        if (!countsData) {
            return {};
        }
        try {
            return JSON.parse(countsData);
        } catch (e) {
            console.error(`${this.constructor.name}: Failed to parse contextual counts:`, e);
            return {};
        }
    }

    createChip(label, countText, onRemove) {
        const chip = document.createElement('div');
        chip.className = 'tag-link';

        const textSpan = document.createElement('span');
        textSpan.className = 'keyword-chip__text';
        textSpan.textContent = label;
        if (countText) {
            const countSpan = document.createElement('span');
            countSpan.className = 'tag-link__count';
            countSpan.textContent = `(${countText})`;
            textSpan.appendChild(countSpan);
        }

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'keyword-chip__remove';
        removeBtn.setAttribute('aria-label', `Remove ${label}`);
        const icon = document.createElement('i');
        icon.className = 'fa-solid fa-xmark';
        removeBtn.appendChild(icon);
        removeBtn.addEventListener('click', onRemove);

        chip.appendChild(textSpan);
        chip.appendChild(removeBtn);
        return chip;
    }

    replaceHiddenInputs(form, name, values) {
        if (!form) {
            return;
        }
        form.querySelectorAll(`input[name="${name}"][type="hidden"]`).forEach((input) => input.remove());
        values.forEach((value) => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = value;
            form.appendChild(input);
        });
    }
}

// Subclasses implement parseItems(data), getInitialSelection(), selectionFromButton(button),
// toSelection(item), getItemKey(item), getSelectionKey(item), getItemTotal(item),
// matchesQuery(item, query), getHiddenInputValue(selection), and setDataAttributes(element, item).
class SingleSelectAutocomplete extends BaseAutocomplete {
    constructor(options, defaults) {
        super(options, defaults);
        this.chipsContainer = document.getElementById(options.chipsContainerId);
        this.inputHint = document.getElementById(`${this.inputId}-hint`);
        this.suggestedContainer = document.getElementById(
            options.suggestedContainerId || defaults.suggestedContainerId
        );
        this.suggestedButtonSelector = defaults.suggestedButtonSelector;
        this.hiddenInputName = defaults.hiddenInputName;
        this.inputHintText = defaults.inputHintText;
        this.numberFormatter = new Intl.NumberFormat();
        this.contextualCounts = {};
        this.items = [];
        this.selected = null;
    }

    hasRequiredElements() {
        return super.hasRequiredElements() && Boolean(this.chipsContainer);
    }

    init() {
        this.contextualCounts = this.parseContextualCounts(this.chipsContainer);
        this.loadItems();
        this.initSuggestedButtons();

        const initialSelection = this.getInitialSelection();
        if (initialSelection) {
            this.setSelection(initialSelection, { silent: true });
        }

        this.bindInputEvents();
        if (this.form) {
            this.form.addEventListener('submit', () => this.syncHiddenInputs());
        }
        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', () => this.syncHiddenInputs());
        }
    }

    async loadItems() {
        try {
            const response = await fetch(this.apiEndpoint);
            this.items = this.parseItems(await response.json());
        } catch (error) {
            console.error(`${this.constructor.name}: Error loading suggestions:`, error);
            this.items = [];
        }
    }

    initSuggestedButtons() {
        if (!this.suggestedContainer) {
            return;
        }
        this.suggestedContainer.querySelectorAll(this.suggestedButtonSelector).forEach((button) => {
            button.addEventListener('click', () => {
                const selection = this.selectionFromButton(button);
                if (selection) {
                    this.setSelection(selection);
                    this.input.value = '';
                }
            });
        });
    }

    filterAndShowSuggestions(query) {
        const hasContextualCounts = Object.keys(this.contextualCounts).length > 0;
        const matches = this.items.filter((item) => {
            const hasCount = !hasContextualCounts || this.contextualCounts[this.getItemKey(item)] > 0;
            return !this.isSelected(item) && hasCount && this.matchesQuery(item, query);
        });
        this.displaySuggestions(matches.slice(0, 10));
    }

    isSelected(item) {
        if (!this.selected) {
            return false;
        }
        const selectedKey = this.getSelectionKey(this.selected);
        return Boolean(selectedKey) && selectedKey === this.getSelectionKey(item);
    }

    getSuggestionLabel(item) {
        return item.name;
    }

    getSuggestionCount(item) {
        const contextualCount = this.contextualCounts[this.getItemKey(item)];
        const count = contextualCount !== undefined ? contextualCount : this.getItemTotal(item);
        return this.formatCount(count || 0);
    }

    selectSuggestion(item) {
        this.setSelection(this.toSelection(item));
    }

    setSelection(selection, options = {}) {
        if (!selection) {
            return;
        }
        this.selected = selection;
        this.renderChip(selection);
        this.syncHiddenInputs();
        this.hideSuggestedContainer();
        this.hideInput();
        if (!options.silent) {
            requestFilterFormSubmit(this.form);
        }
    }

    renderChip(selection) {
        const count = this.contextualCounts[this.getItemKey(selection)];
        const chip = this.createChip(
            selection.name,
            count ? this.formatCount(count) : null,
            () => this.clearSelection()
        );
        this.setDataAttributes(chip, selection);
        this.chipsContainer.replaceChildren(chip);
    }

    clearSelection() {
        this.selected = null;
        this.chipsContainer.replaceChildren();
        this.syncHiddenInputs();
        this.showSuggestedContainer();
        this.showInput();
        requestFilterFormSubmit(this.form);
    }

    syncHiddenInputs() {
        const values = this.selected ? [this.getHiddenInputValue(this.selected)] : [];
        this.replaceHiddenInputs(this.form, this.hiddenInputName, values);
        this.replaceHiddenInputs(this.mainSearchForm, this.hiddenInputName, values);
    }

    formatCount(value) {
        return this.numberFormatter.format(Number.isFinite(value) ? value : 0);
    }

    hideSuggestedContainer() {
        if (this.suggestedContainer) {
            this.suggestedContainer.style.display = 'none';
        }
    }

    showSuggestedContainer() {
        if (this.suggestedContainer && !this.selected) {
            this.suggestedContainer.style.display = 'block';
        }
    }

    hideInput() {
        this.input.classList.add('display-none');
        if (this.inputHint) {
            this.inputHint.textContent = 'Remove the filter to search again';
        }
        this.hideSuggestions();
    }

    showInput() {
        this.input.classList.remove('display-none');
        if (this.inputHint) {
            this.inputHint.textContent = this.inputHintText;
        }
    }
}
