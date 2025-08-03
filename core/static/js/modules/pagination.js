/**
 * Pagination Manager - Handles pagination interactions and keyboard navigation
 */
class PaginationManager {
    constructor() {
        this.paginationContainer = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.keyboardEnabled = true;
    }

    init() {
        this.setupPagination();
        this.setupKeyboardNavigation();
        this.setupEnhancedPaginationFeatures();
    }

    /**
     * Setup pagination container and extract page info
     */
    setupPagination() {
        this.paginationContainer = document.querySelector('.pagination');
        if (!this.paginationContainer) {
            return; // No pagination on this page
        }

        this.extractPaginationInfo();
        this.enhancePaginationLinks();
    }

    /**
     * Extract current page and total pages from pagination elements
     */
    extractPaginationInfo() {
        // Find active page link
        const activePage = this.paginationContainer.querySelector('a.active');
        if (activePage) {
            this.currentPage = parseInt(activePage.textContent) || 1;
        }

        // Count total pages from pagination links
        const pageLinks = this.paginationContainer.querySelectorAll('a[href*="page="]');
        let maxPage = 1;
        pageLinks.forEach(link => {
            const match = link.href.match(/page=(\d+)/);
            if (match) {
                maxPage = Math.max(maxPage, parseInt(match[1]));
            }
        });
        this.totalPages = maxPage;
    }

    /**
     * Enhance pagination links with loading states and better UX
     */
    enhancePaginationLinks() {
        const pageLinks = this.paginationContainer.querySelectorAll('a[href*="page="]');
        
        pageLinks.forEach(link => {
            link.addEventListener('click', (event) => {
                this.handlePageNavigation(event, link);
            });

            // Add hover effects
            link.addEventListener('mouseenter', () => {
                if (!link.classList.contains('active')) {
                    link.classList.add('hover:bg-blue-50');
                }
            });
        });
    }

    /**
     * Handle page navigation with loading state
     */
    handlePageNavigation(event, link) {
        // Add loading state
        this.setLoadingState(true);

        // Extract target page
        const match = link.href.match(/page=(\d+)/);
        const targetPage = match ? parseInt(match[1]) : 1;

        // Update current page optimistically
        this.currentPage = targetPage;

        // Show loading feedback
        this.showPageLoadingFeedback(targetPage);

        // Let the default navigation proceed
        // The loading state will be cleared when the new page loads
    }

    /**
     * Setup keyboard navigation for pagination
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (event) => {
            // Only handle keyboard navigation on list pages with pagination
            if (!this.paginationContainer || !this.keyboardEnabled) {
                return;
            }

            // Prevent navigation if user is typing in an input
            if (this.isInputFocused()) {
                return;
            }

            this.handleKeyboardNavigation(event);
        });
    }

    /**
     * Handle keyboard navigation events
     */
    handleKeyboardNavigation(event) {
        let handled = false;

        // Ctrl + Arrow keys for page navigation
        if (event.ctrlKey) {
            switch (event.key) {
                case 'ArrowLeft':
                    this.navigateToPage('previous');
                    handled = true;
                    break;
                case 'ArrowRight':
                    this.navigateToPage('next');
                    handled = true;
                    break;
                case 'Home':
                    this.navigateToPage('first');
                    handled = true;
                    break;
                case 'End':
                    this.navigateToPage('last');
                    handled = true;
                    break;
            }
        }

        // Page Up/Down for pagination
        if (event.key === 'PageUp' && event.altKey) {
            this.navigateToPage('previous');
            handled = true;
        } else if (event.key === 'PageDown' && event.altKey) {
            this.navigateToPage('next');
            handled = true;
        }

        if (handled) {
            event.preventDefault();
            event.stopPropagation();
        }
    }

    /**
     * Navigate to specific page or direction
     */
    navigateToPage(direction) {
        let targetPage = this.currentPage;

        switch (direction) {
            case 'previous':
                targetPage = Math.max(1, this.currentPage - 1);
                break;
            case 'next':
                targetPage = Math.min(this.totalPages, this.currentPage + 1);
                break;
            case 'first':
                targetPage = 1;
                break;
            case 'last':
                targetPage = this.totalPages;
                break;
            default:
                if (typeof direction === 'number') {
                    targetPage = Math.max(1, Math.min(this.totalPages, direction));
                }
        }

        if (targetPage !== this.currentPage) {
            this.goToPage(targetPage);
        }
    }

    /**
     * Navigate to specific page number
     */
    goToPage(pageNumber) {
        const pageLink = this.findPageLink(pageNumber);
        if (pageLink) {
            pageLink.click();
        } else {
            // Construct URL manually if link not found
            const currentUrl = new URL(window.location);
            currentUrl.searchParams.set('page', pageNumber);
            window.location.href = currentUrl.toString();
        }
    }

    /**
     * Find pagination link for specific page
     */
    findPageLink(pageNumber) {
        const links = this.paginationContainer.querySelectorAll('a[href*="page="]');
        
        for (const link of links) {
            const match = link.href.match(/page=(\d+)/);
            if (match && parseInt(match[1]) === pageNumber) {
                return link;
            }
        }

        // Also check previous/next links
        if (pageNumber === this.currentPage - 1) {
            return this.paginationContainer.querySelector('a[href*="page="]:first-child');
        }
        if (pageNumber === this.currentPage + 1) {
            return this.paginationContainer.querySelector('a[href*="page="]:last-child');
        }

        return null;
    }

    /**
     * Check if an input element is currently focused
     */
    isInputFocused() {
        const activeElement = document.activeElement;
        return activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.contentEditable === 'true'
        );
    }

    /**
     * Setup enhanced pagination features
     */
    setupEnhancedPaginationFeatures() {
        this.addKeyboardHints();
        this.setupPageJumper();
    }

    /**
     * Add keyboard navigation hints to the UI
     */
    addKeyboardHints() {
        if (!this.paginationContainer) return;

        const hintsContainer = document.createElement('div');
        hintsContainer.className = 'pagination-hints text-xs text-gray-500 mt-2';
        hintsContainer.innerHTML = `
            <div class="flex items-center space-x-4">
                <span>⌨️ Keyboard: Ctrl+← Ctrl+→ for pages</span>
                <span>Alt+PgUp Alt+PgDn also work</span>
            </div>
        `;
        
        this.paginationContainer.appendChild(hintsContainer);
    }

    /**
     * Setup quick page jumper input
     */
    setupPageJumper() {
        if (!this.paginationContainer || this.totalPages <= 5) return;

        const jumperContainer = document.createElement('div');
        jumperContainer.className = 'page-jumper flex items-center space-x-2 mt-2';
        jumperContainer.innerHTML = `
            <span class="text-sm text-gray-600">Go to page:</span>
            <input type="number" min="1" max="${this.totalPages}" 
                   class="form-input w-20 text-center" 
                   placeholder="${this.currentPage}">
            <button class="btn btn-secondary btn-sm">Go</button>
        `;

        const input = jumperContainer.querySelector('input');
        const button = jumperContainer.querySelector('button');

        // Handle go button click
        button.addEventListener('click', () => {
            const pageNumber = parseInt(input.value);
            if (pageNumber >= 1 && pageNumber <= this.totalPages) {
                this.goToPage(pageNumber);
            }
        });

        // Handle enter key in input
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                button.click();
            }
        });

        this.paginationContainer.appendChild(jumperContainer);
    }

    /**
     * Set loading state for pagination
     */
    setLoadingState(loading) {
        if (!this.paginationContainer) return;

        const links = this.paginationContainer.querySelectorAll('a');
        links.forEach(link => {
            if (loading) {
                link.style.pointerEvents = 'none';
                link.classList.add('opacity-50');
            } else {
                link.style.pointerEvents = '';
                link.classList.remove('opacity-50');
            }
        });
    }

    /**
     * Show page loading feedback
     */
    showPageLoadingFeedback(targetPage) {
        // Create a temporary loading indicator
        const loader = document.createElement('div');
        loader.className = 'pagination-loader fixed top-4 right-4 bg-blue-500 text-white px-3 py-2 rounded-md z-50';
        loader.textContent = `Loading page ${targetPage}...`;
        
        document.body.appendChild(loader);

        // Remove loader after page loads (or timeout)
        setTimeout(() => {
            if (loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
        }, 3000);
    }

    /**
     * Enable/disable keyboard navigation
     */
    setKeyboardEnabled(enabled) {
        this.keyboardEnabled = enabled;
    }

    /**
     * Get current pagination state
     */
    getState() {
        return {
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            keyboardEnabled: this.keyboardEnabled
        };
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PaginationManager;
}