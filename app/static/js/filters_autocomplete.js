function requestFilterFormSubmit(form, options = {}) {
  const controller = window.dataGovFilterFormAutoSubmit;
  if (
    controller &&
    typeof controller.request === "function" &&
    controller.form
  ) {
    controller.request(options);
    return;
  }

  if (controller && typeof controller.captureMapPanelState === "function") {
    controller.captureMapPanelState();
  }

  if (!form) {
    return;
  }

  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
  } else {
    form.submit();
  }
}

class BaseAutocomplete {
  constructor(options) {
    this.inputId = options.inputId;
    this.chipsContainerId = options.chipsContainerId;
    this.suggestionsId = options.suggestionsId;
    this.apiEndpoint = options.apiEndpoint;
    this.formId = options.formId;
    this.mainSearchFormId = options.mainSearchFormId;
    this.debounceDelay = options.debounceDelay || 300;
    this.suggestedContainerId = options.suggestedContainerId || null;

    this.input = document.getElementById(this.inputId);
    this.chipsContainer = document.getElementById(this.chipsContainerId);
    this.suggestionsContainer = document.getElementById(this.suggestionsId);
    this.form = document.getElementById(this.formId);
    this.mainSearchForm = document.getElementById(this.mainSearchFormId);
    this.suggestedContainer = this.suggestedContainerId
      ? document.getElementById(this.suggestedContainerId)
      : null;

    this.debounceTimer = null;
    this.currentFocusIndex = -1;
    this.contextualCounts = {};
    this.numberFormatter = new Intl.NumberFormat();

    if (!this.input || !this.chipsContainer || !this.suggestionsContainer) {
      console.error(`${this.constructor.name}: Required elements not found`);
      return;
    }

    this.loadContextualCounts();
    this.init();
  }

  loadContextualCounts() {
    const countsData = this.chipsContainer.dataset.contextualCounts;
    if (countsData) {
      try {
        this.contextualCounts = JSON.parse(countsData);
      } catch (e) {
        console.error("Failed to parse contextual counts:", e);
      }
    }
  }

  init() {
    this.loadData();
    this.initSuggestedItems();
    this.loadInitialSelection();

    this.input.addEventListener("input", (e) => this.handleInput(e));
    this.input.addEventListener("keydown", (e) => this.handleKeyDown(e));
    this.input.addEventListener("focus", () => this.showSuggestions());

    document.addEventListener("click", (e) => {
      if (
        !this.input.contains(e.target) &&
        !this.suggestionsContainer.contains(e.target)
      ) {
        this.hideSuggestions();
      }
    });

    if (this.form) {
      this.form.addEventListener("submit", () => this.syncHiddenInputs());
    }

    if (this.mainSearchForm) {
      this.mainSearchForm.addEventListener("submit", () =>
        this.syncHiddenInputs(),
      );
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
    const suggestions = this.suggestionsContainer.querySelectorAll(
      ".keyword-suggestion",
    );

    if (e.key === "ArrowDown") {
      e.preventDefault();
      this.currentFocusIndex = Math.min(
        this.currentFocusIndex + 1,
        suggestions.length - 1,
      );
      this.updateSuggestionFocus(suggestions);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      this.currentFocusIndex = Math.max(this.currentFocusIndex - 1, 0);
      this.updateSuggestionFocus(suggestions);
    } else if (e.key === "Enter" || e.key === "Tab") {
      if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
        e.preventDefault();
        this.handleSuggestionSelection(suggestions[this.currentFocusIndex]);
        this.input.value = "";
        this.hideSuggestions();
      }
    } else if (e.key === "Escape") {
      this.hideSuggestions();
    }
  }

  updateSuggestionFocus(suggestions) {
    suggestions.forEach((item, index) => {
      if (index === this.currentFocusIndex) {
        item.classList.add("keyword-suggestion--focused");
        item.scrollIntoView({ block: "nearest" });
      } else {
        item.classList.remove("keyword-suggestion--focused");
      }
    });
  }

  showSuggestions() {
    this.suggestionsContainer.classList.add("keyword-suggestions--visible");
    this.input.setAttribute("aria-expanded", "true");
  }

  hideSuggestions() {
    this.suggestionsContainer.classList.remove("keyword-suggestions--visible");
    this.currentFocusIndex = -1;
    this.input.setAttribute("aria-expanded", "false");
  }

  hideSuggestedItems() {
    if (this.suggestedContainer) {
      this.suggestedContainer.style.display = "none";
    }
  }

  showSuggestedItems() {
    if (this.suggestedContainer && this.shouldShowSuggestedItems()) {
      this.suggestedContainer.style.display = "block";
    }
  }

  highlightMatch(text, query) {
    const fragment = document.createDocumentFragment();
    if (!text) {
      return fragment;
    }

    const normalizedText = text.toLowerCase();
    const normalizedQuery = (query || "").toLowerCase();
    const index = normalizedText.indexOf(normalizedQuery);

    if (index === -1 || !query) {
      fragment.appendChild(document.createTextNode(text));
      return fragment;
    }

    fragment.appendChild(document.createTextNode(text.substring(0, index)));
    const strong = document.createElement("strong");
    strong.textContent = text.substring(index, index + query.length);
    fragment.appendChild(strong);
    fragment.appendChild(
      document.createTextNode(text.substring(index + query.length)),
    );
    return fragment;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
  }

  formatCount(value) {
    const count = Number.isFinite(value) ? value : 0;
    return this.numberFormatter.format(count);
  }

  createSuggestionElement() {
    const div = document.createElement("div");
    div.className = "keyword-suggestion";
    return div;
  }

  createChipElement() {
    const chip = document.createElement("div");
    chip.className = "tag-link";
    return chip;
  }

  // Hooks for subclasses
  async loadData() {}
  initSuggestedItems() {}
  loadInitialSelection() {}
  filterAndShowSuggestions() {}
  renderSuggestions() {}
  handleSuggestionSelection() {}
  syncHiddenInputs() {}
  shouldShowSuggestedItems() {
    return false;
  }
}

class KeywordAutocomplete extends BaseAutocomplete {
  constructor(options) {
    super({
      ...options,
      apiEndpoint: options.apiEndpoint || "/api/keywords",
    });

    this.selectedKeywords = new Set();
    this.allKeywords = [];
  }

  init() {
    this.selectedKeywords = new Set();
    this.allKeywords = [];
    super.init();
    this.loadExistingKeywords();
  }

  async loadData() {
    try {
      const response = await fetch(`${this.apiEndpoint}?size=500`);
      const data = await response.json();
      this.allKeywords = data.keywords || [];
    } catch (error) {
      console.error("Error loading keywords:", error);
      this.allKeywords = [];
    }
  }

  loadExistingKeywords() {
    const urlParams = new URLSearchParams(window.location.search);
    const keywords = urlParams.getAll("keyword");
    keywords.forEach((keyword) => {
      if (keyword && keyword.trim()) {
        this.addKeyword(keyword.trim(), { silent: true });
      }
    });
  }

  initSuggestedItems() {
    this.suggestedContainer = document.getElementById("suggested-keywords");
    if (!this.suggestedContainer) {
      return;
    }

    const suggestedButtons = this.suggestedContainer.querySelectorAll(
      ".tag-link--suggested",
    );
    suggestedButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const keyword = button.dataset.keyword;
        if (keyword) {
          this.addKeyword(keyword);
        }
      });
    });
  }

  shouldShowSuggestedItems() {
    return this.selectedKeywords.size === 0;
  }

  filterAndShowSuggestions(query) {
    const filtered = this.allKeywords.filter((item) => {
      const keyword = item.keyword.toLowerCase();
      const matchesQuery = keyword.includes(query);
      const notSelected = !this.selectedKeywords.has(item.keyword);

      const hasContextualCount = Object.keys(this.contextualCounts).length > 0;
      const hasCount =
        !hasContextualCount || this.contextualCounts[item.keyword] > 0;

      return matchesQuery && notSelected && hasCount;
    });

    const topResults = filtered.slice(0, 10);

    if (topResults.length > 0) {
      this.renderSuggestions(topResults);
      this.showSuggestions();
    } else {
      this.hideSuggestions();
    }
  }

  renderSuggestions(keywords) {
    this.suggestionsContainer.innerHTML = "";
    this.currentFocusIndex = -1;

    keywords.forEach((item) => {
      const div = this.createSuggestionElement();
      div.dataset.keyword = item.keyword;

      const displayCount =
        this.contextualCounts[item.keyword] !== undefined
          ? this.contextualCounts[item.keyword]
          : item.count;

      const textSpan = document.createElement("span");
      textSpan.className = "keyword-suggestion__text";
      textSpan.appendChild(this.highlightMatch(item.keyword, this.input.value));

      const countSpan = document.createElement("span");
      countSpan.className = "keyword-suggestion__count";
      countSpan.textContent = displayCount;

      div.appendChild(textSpan);
      div.appendChild(countSpan);

      div.addEventListener("click", () => {
        this.addKeyword(item.keyword);
        this.input.value = "";
        this.hideSuggestions();
      });

      this.suggestionsContainer.appendChild(div);
    });
  }

  handleSuggestionSelection(suggestion) {
    const keyword = suggestion.dataset.keyword;
    this.addKeyword(keyword);
  }

  addKeyword(keyword, options = {}) {
    const silent = Boolean(options.silent);
    if (this.selectedKeywords.has(keyword)) {
      return;
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

    const chip = this.chipsContainer.querySelector(
      `[data-keyword="${this.escapeHtml(keyword)}"]`,
    );
    if (chip) {
      chip.remove();
    }

    if (this.selectedKeywords.size === 0) {
      this.showSuggestedItems();
    }

    requestFilterFormSubmit(this.form);
  }

  renderChip(keyword) {
    const chip = this.createChipElement();
    chip.dataset.keyword = keyword;
    const count = this.contextualCounts[keyword];

    const textSpan = document.createElement("span");
    textSpan.className = "keyword-chip__text";
    textSpan.textContent = keyword;

    if (count) {
      const countSpan = document.createElement("span");
      countSpan.className = "tag-link__count";
      countSpan.textContent = `(${count})`;
      textSpan.appendChild(countSpan);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "keyword-chip__remove";
    removeBtn.setAttribute("aria-label", `Remove ${keyword}`);

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-xmark";
    removeBtn.appendChild(icon);

    chip.appendChild(textSpan);
    chip.appendChild(removeBtn);

    removeBtn.addEventListener("click", () => {
      this.removeKeyword(keyword);
    });

    this.chipsContainer.appendChild(chip);
  }

  syncHiddenInputs() {
    if (this.form) {
      const existingInputs = this.form.querySelectorAll(
        'input[name="keyword"]',
      );
      existingInputs.forEach((input) => input.remove());

      this.selectedKeywords.forEach((keyword) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "keyword";
        input.value = keyword;
        this.form.appendChild(input);
      });
    }

    if (this.mainSearchForm) {
      const existingInputs = this.mainSearchForm.querySelectorAll(
        'input[name="keyword"][type="hidden"]',
      );
      existingInputs.forEach((input) => input.remove());

      this.selectedKeywords.forEach((keyword) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "keyword";
        input.value = keyword;
        this.mainSearchForm.appendChild(input);
      });
    }
  }
}

class OrganizationAutocomplete extends BaseAutocomplete {
  constructor(options) {
    super({
      ...options,
      apiEndpoint: options.apiEndpoint || "/api/organizations",
      suggestedContainerId:
        options.suggestedContainerId || "suggested-organizations",
    });

    this.organizations = [];
    this.selectedOrganization = null;
    this.initialSelection =
      options.initialSelection || this.getInitialSelection();
  }

  init() {
    this.organizations = [];
    this.selectedOrganization = null;
    super.init();
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

  loadInitialSelection() {
    if (this.initialSelection) {
      this.setOrganization(this.initialSelection, { silent: true });
      this.hideSuggestedItems();
    }
  }

  async loadData() {
    try {
      const response = await fetch(this.apiEndpoint);
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
          slug: item.slug || "",
        }));
    } catch (error) {
      console.error("Error loading organizations:", error);
      this.organizations = [];
    }
  }

  initSuggestedItems() {
    if (!this.suggestedContainer) {
      return;
    }

    const buttons = this.suggestedContainer.querySelectorAll(
      ".tag-link--organization",
    );
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const orgId = button.dataset.orgId;
        const orgName = button.dataset.orgName;
        const orgSlug = button.dataset.orgSlug;

        if (orgName) {
          this.setOrganization({ id: orgId, name: orgName, slug: orgSlug });
          this.input.value = "";
          this.hideSuggestedItems();
        }
      });
    });
  }

  shouldShowSuggestedItems() {
    return !this.selectedOrganization;
  }

  filterAndShowSuggestions(query) {
    const filtered = this.organizations.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const slug = (item.slug || "").toLowerCase();
      const aliases = Array.isArray(item.aliases)
        ? item.aliases.map((alias) => (alias || "").toLowerCase())
        : [];

      const currentKey = this.selectedOrganization
        ? (this.selectedOrganization.slug || this.selectedOrganization.id || "")
            .toString()
            .toLowerCase()
        : null;
      const itemKey = (item.slug || item.id || "").toString().toLowerCase();
      const alreadySelected = currentKey && currentKey === itemKey;

      if (alreadySelected) {
        return false;
      }

      const aliasMatch = aliases.some((alias) => alias.includes(query));
      return name.includes(query) || slug.includes(query) || aliasMatch;
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
    this.suggestionsContainer.innerHTML = "";
    this.currentFocusIndex = -1;

    items.forEach((item) => {
      const div = this.createSuggestionElement();
      if (item.id !== undefined) {
        div.dataset.orgId = String(item.id);
      }
      if (item.slug) {
        div.dataset.orgSlug = item.slug;
      }

      const textSpan = document.createElement("span");
      textSpan.className = "keyword-suggestion__text";
      textSpan.appendChild(this.highlightMatch(item.name, this.input.value));

      const countSpan = document.createElement("span");
      countSpan.className = "keyword-suggestion__count";
      countSpan.textContent = this.formatCount(item.dataset_count || 0);

      div.appendChild(textSpan);
      div.appendChild(countSpan);

      div.addEventListener("click", () => {
        this.setOrganization({
          id: item.id != null ? String(item.id) : undefined,
          name: item.name,
          slug: item.slug,
        });
        this.input.value = "";
        this.hideSuggestions();
      });

      this.suggestionsContainer.appendChild(div);
    });
  }

  handleSuggestionSelection(suggestion) {
    const orgId = suggestion.dataset.orgId;
    const orgSlug = suggestion.dataset.orgSlug;

    const organization = this.organizations.find((item) => {
      if (orgSlug) {
        return (item.slug || "").toString() === orgSlug;
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
  }

  setOrganization(organization, options = {}) {
    const silent = Boolean(options.silent);
    if (!organization) {
      return;
    }

    const normalizedId = organization.id != null ? String(organization.id) : "";
    const normalizedSlug = organization.slug || "";
    this.selectedOrganization = {
      id: normalizedId,
      name: organization.name || "",
      slug: normalizedSlug,
    };

    this.renderChip(this.selectedOrganization);
    this.syncHiddenInputs();
    this.hideSuggestedItems();

    if (!silent) {
      requestFilterFormSubmit(this.form);
    }
  }

  renderChip(organization) {
    this.chipsContainer.innerHTML = "";

    const chip = this.createChipElement();
    if (organization.id) {
      chip.dataset.orgId = organization.id;
    }
    if (organization.slug) {
      chip.dataset.orgSlug = organization.slug;
    }

    const count = organization.slug
      ? this.contextualCounts[organization.slug]
      : null;

    const textSpan = document.createElement("span");
    textSpan.className = "keyword-chip__text";
    textSpan.textContent = organization.name;

    if (count) {
      const countSpan = document.createElement("span");
      countSpan.className = "tag-link__count";
      countSpan.textContent = `(${this.formatCount(count)})`;
      textSpan.appendChild(countSpan);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "keyword-chip__remove";
    removeBtn.setAttribute("aria-label", `Remove ${organization.name}`);

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-xmark";
    removeBtn.appendChild(icon);

    chip.appendChild(textSpan);
    chip.appendChild(removeBtn);

    removeBtn.addEventListener("click", () => {
      this.clearSelection();
    });

    this.chipsContainer.appendChild(chip);
  }

  clearSelection() {
    this.selectedOrganization = null;
    this.chipsContainer.innerHTML = "";
    this.syncHiddenInputs();
    this.showSuggestedItems();
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

    const existing = form.querySelectorAll(
      'input[name="org_slug"][type="hidden"]',
    );
    existing.forEach((input) => input.remove());

    if (this.selectedOrganization) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "org_slug";
      input.value =
        this.selectedOrganization.slug || this.selectedOrganization.name;
      form.appendChild(input);
    }
  }
}

class PublisherAutocomplete extends BaseAutocomplete {
  constructor(options) {
    super({
      ...options,
      apiEndpoint: options.apiEndpoint || "/api/publishers",
      suggestedContainerId:
        options.suggestedContainerId || "suggested-publishers",
    });

    this.publishers = [];
    this.selectedPublisher = null;
    this.initialSelection =
      options.initialSelection || this.getInitialSelection();
  }

  init() {
    this.publishers = [];
    this.selectedPublisher = null;
    super.init();
  }

  getInitialSelection() {
    if (!this.chipsContainer || !this.chipsContainer.dataset) {
      return null;
    }

    return this.chipsContainer.dataset.initialPublisherName || null;
  }

  loadInitialSelection() {
    if (this.initialSelection) {
      this.setPublisher(this.initialSelection, { silent: true });
      this.hideSuggestedItems();
    }
  }

  async loadData() {
    try {
      const response = await fetch(this.apiEndpoint);
      const data = await response.json();
      this.publishers = (data.publishers || []).filter((item) => item.name);
    } catch (error) {
      console.error("Error loading publishers:", error);
      this.publishers = [];
    }
  }

  initSuggestedItems() {
    if (!this.suggestedContainer) {
      return;
    }

    const buttons = this.suggestedContainer.querySelectorAll(
      ".tag-link--publisher",
    );
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const publisherName = button.dataset.publisherName;
        if (publisherName) {
          this.setPublisher(publisherName);
          this.input.value = "";
          this.hideSuggestedItems();
        }
      });
    });
  }

  shouldShowSuggestedItems() {
    return !this.selectedPublisher;
  }

  filterAndShowSuggestions(query) {
    const filtered = this.publishers.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const alreadySelected =
        this.selectedPublisher && this.selectedPublisher.toLowerCase() === name;

      const hasContextualCount = Object.keys(this.contextualCounts).length > 0;
      const count = this.contextualCounts[item.name];
      const hasCount = !hasContextualCount || count > 0;

      return name.includes(query) && !alreadySelected && hasCount;
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
    this.suggestionsContainer.innerHTML = "";
    this.currentFocusIndex = -1;

    items.forEach((item) => {
      const div = this.createSuggestionElement();
      div.dataset.publisherName = item.name;

      const displayCount =
        this.contextualCounts[item.name] !== undefined
          ? this.contextualCounts[item.name]
          : item.count;

      const textSpan = document.createElement("span");
      textSpan.className = "keyword-suggestion__text";
      textSpan.appendChild(this.highlightMatch(item.name, this.input.value));

      const countSpan = document.createElement("span");
      countSpan.className = "keyword-suggestion__count";
      countSpan.textContent = this.formatCount(displayCount || 0);

      div.appendChild(textSpan);
      div.appendChild(countSpan);

      div.addEventListener("click", () => {
        this.setPublisher(item.name);
        this.input.value = "";
        this.hideSuggestions();
      });

      this.suggestionsContainer.appendChild(div);
    });
  }

  handleSuggestionSelection(suggestion) {
    const publisherName = suggestion.dataset.publisherName;
    if (publisherName) {
      this.setPublisher(publisherName);
    }
  }

  setPublisher(name, options = {}) {
    const silent = Boolean(options.silent);
    if (!name) {
      return;
    }

    this.selectedPublisher = name;
    this.renderChip(name);
    this.syncHiddenInputs();
    this.hideSuggestedItems();

    if (!silent) {
      requestFilterFormSubmit(this.form);
    }
  }

  renderChip(name) {
    this.chipsContainer.innerHTML = "";

    const chip = this.createChipElement();
    chip.dataset.publisherName = name;
    const count = this.contextualCounts[name];

    const textSpan = document.createElement("span");
    textSpan.className = "keyword-chip__text";
    textSpan.textContent = name;

    if (count) {
      const countSpan = document.createElement("span");
      countSpan.className = "tag-link__count";
      countSpan.textContent = `(${this.formatCount(count)})`;
      textSpan.appendChild(countSpan);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "keyword-chip__remove";
    removeBtn.setAttribute("aria-label", `Remove ${name}`);

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-xmark";
    removeBtn.appendChild(icon);

    chip.appendChild(textSpan);
    chip.appendChild(removeBtn);

    removeBtn.addEventListener("click", () => {
      this.clearSelection();
    });

    this.chipsContainer.appendChild(chip);
  }

  clearSelection() {
    this.selectedPublisher = null;
    this.chipsContainer.innerHTML = "";
    this.syncHiddenInputs();
    this.showSuggestedItems();
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

    const existing = form.querySelectorAll(
      'input[name="publisher"][type="hidden"]',
    );
    existing.forEach((input) => input.remove());

    if (this.selectedPublisher) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "publisher";
      input.value = this.selectedPublisher;
      form.appendChild(input);
    }
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  const keywordInput = document.getElementById("keyword-input");
  const keywordChips = document.getElementById("keyword-chips");
  const keywordSuggestions = document.getElementById("keyword-suggestions");
  if (keywordInput && keywordChips && keywordSuggestions) {
    new KeywordAutocomplete({
      inputId: "keyword-input",
      chipsContainerId: "keyword-chips",
      suggestionsId: "keyword-suggestions",
      formId: "filter-form",
      mainSearchFormId: "main-search-form",
      apiEndpoint: "/api/keywords",
      debounceDelay: 300,
    });
  }

  const organizationInput = document.getElementById("organization-input");
  const organizationChips = document.getElementById("organization-chips");
  const organizationSuggestions = document.getElementById(
    "organization-suggestions",
  );
  if (organizationInput && organizationChips && organizationSuggestions) {
    new OrganizationAutocomplete({
      inputId: "organization-input",
      chipsContainerId: "organization-chips",
      suggestionsId: "organization-suggestions",
      formId: "filter-form",
      mainSearchFormId: "main-search-form",
      apiEndpoint: "/api/organizations",
      debounceDelay: 300,
      suggestedContainerId: "suggested-organizations",
    });
  }

  const publisherInput = document.getElementById("publisher-input");
  const publisherChips = document.getElementById("publisher-chips");
  const publisherSuggestions = document.getElementById("publisher-suggestions");
  if (publisherInput && publisherChips && publisherSuggestions) {
    new PublisherAutocomplete({
      inputId: "publisher-input",
      chipsContainerId: "publisher-chips",
      suggestionsId: "publisher-suggestions",
      formId: "filter-form",
      mainSearchFormId: "main-search-form",
      apiEndpoint: "/api/publishers",
      debounceDelay: 300,
      suggestedContainerId: "suggested-publishers",
    });
  }
});
