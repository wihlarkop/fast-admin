/**
 * Fast-Admin Main Entry Point
 * Coordinates all admin interface modules and functionality
 */
class FastAdmin {
    constructor() {
        this.tableManager = null;
        this.bulkActions = null;
        this.paginationManager = null;
        this.initialized = false;
    }

    /**
     * Initialize the admin interface
     */
    async init() {
        if (this.initialized) {
            console.warn('FastAdmin already initialized');
            return;
        }

        try {
            // Initialize core modules
            await this.initializeModules();

            // Setup global event handlers
            this.setupGlobalEventHandlers();

            // Setup HTMX enhancements
            this.setupHTMXEnhancements();

            // Setup legacy functionality
            this.setupLegacyFeatures();

            // Mark as initialized
            this.initialized = true;

            // Dispatch initialization event
            this.dispatchEvent('admin:initialized', {
                modules: this.getModuleStatus()
            });

        } catch (error) {
            console.error('Failed to initialize FastAdmin:', error);
            this.handleInitializationError(error);
        }
    }

    /**
     * Initialize all admin modules
     */
    async initializeModules() {
        // Initialize Table Manager
        if (typeof TableManager !== 'undefined') {
            this.tableManager = new TableManager();
            this.tableManager.init();
        }

        // Initialize Bulk Actions
        if (typeof BulkActions !== 'undefined') {
            this.bulkActions = new BulkActions();
            this.bulkActions.init();
        }

        // Initialize Pagination Manager
        if (typeof PaginationManager !== 'undefined') {
            this.paginationManager = new PaginationManager();
            this.paginationManager.init();
        }

        // Setup inter-module communication
        this.setupModuleCommunication();
    }

    /**
     * Setup communication between modules
     */
    setupModuleCommunication() {
        // Handle bulk actions clear selection requests
        document.addEventListener('bulkActions:clearSelection', () => {
            if (this.tableManager) {
                this.tableManager.clearSelection();
            }
        });

        // Handle table selection changes for other modules
        document.addEventListener('table:selectionChanged', (event) => {
            this.dispatchEvent('admin:selectionChanged', event.detail);
        });
    }

    /**
     * Setup global event handlers
     */
    setupGlobalEventHandlers() {
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.handlePageHidden();
            } else {
                this.handlePageVisible();
            }
        });

        // Handle global keyboard shortcuts
        document.addEventListener('keydown', (event) => {
            this.handleGlobalKeyboard(event);
        });

        // Handle window resize for responsive features
        window.addEventListener('resize', () => {
            this.handleWindowResize();
        });
    }

    /**
     * Setup HTMX enhancements and error handling
     */
    setupHTMXEnhancements() {
        if (typeof htmx === 'undefined') {
            console.warn('HTMX not found, some features may not work');
            return;
        }

        // Configure HTMX
        htmx.config.requestClass = "htmx-request";
        htmx.config.includeIndicatorStyles = false;
        htmx.config.defaultSwapStyle = "outerHTML";

        // Add global loading indicator
        this.createGlobalLoader();

        // Enhanced error handling
        document.addEventListener('htmx:responseError', (event) => {
            this.handleHTMXError(event);
        });

        // Loading state management
        document.addEventListener('htmx:beforeRequest', (event) => {
            this.handleHTMXBeforeRequest(event);
        });

        document.addEventListener('htmx:afterRequest', (event) => {
            this.handleHTMXAfterRequest(event);
        });

        // Handle redirects properly to prevent UI nesting
        document.addEventListener('htmx:beforeSwap', (event) => {
            // If the response is a redirect (status code 3xx)
            if (event.detail.xhr.status >= 300 && event.detail.xhr.status < 400) {
                // Get the redirect URL from the Location header
                const redirectUrl = event.detail.xhr.getResponseHeader('Location');
                if (redirectUrl) {
                    // Prevent the default swap behavior
                    event.preventDefault();
                    // Navigate to the redirect URL
                    window.location.href = redirectUrl;
                }
            }
        });

        // Re-initialize modules after HTMX swaps
        document.addEventListener('htmx:afterSwap', (event) => {
            this.handleHTMXAfterSwap(event);
        });
    }

    /**
     * Setup legacy features from original admin.js
     */
    setupLegacyFeatures() {
        this.setupFormValidation();
        this.setupConfirmDialogs();
        this.setupToasts();
        this.addCSSAnimations();
    }

    /**
     * Handle global keyboard shortcuts
     */
    handleGlobalKeyboard(event) {
        // Only handle when not typing in inputs
        if (this.isInputFocused()) return;

        // Ctrl+/ for help/shortcuts
        if (event.ctrlKey && event.key === '/') {
            event.preventDefault();
            this.showKeyboardShortcuts();
        }

        // Escape to clear selections or close modals
        if (event.key === 'Escape') {
            if (this.tableManager?.hasSelection()) {
                event.preventDefault();
                this.tableManager.clearSelection();
            } else {
                // Close modals
                const modals = document.querySelectorAll('.modal:not([style*="display: none"])');
                modals.forEach(modal => {
                    modal.style.display = 'none';
                });
            }
        }

        // Ctrl/Cmd + S to save forms
        if ((event.ctrlKey || event.metaKey) && event.key === 's') {
            const form = document.querySelector('form');
            if (form) {
                event.preventDefault();
                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn) {
                    submitBtn.click();
                }
            }
        }
    }

    /**
     * Handle HTMX errors with user-friendly messages
     */
    handleHTMXError(event) {
        const {xhr} = event.detail;
        let message = 'An error occurred. Please try again.';

        // Customize message based on status code
        switch (xhr.status) {
            case 401:
                message = 'Your session has expired. Please log in again.';
                break;
            case 403:
                message = 'You do not have permission to perform this action.';
                break;
            case 404:
                message = 'The requested resource was not found.';
                break;
            case 500:
                message = 'A server error occurred. Please try again later.';
                break;
        }

        this.showToast(message, 'error');

        // Dispatch error event for custom handling
        this.dispatchEvent('admin:error', {
            status: xhr.status,
            message: message,
            originalEvent: event
        });
    }

    /**
     * Handle HTMX before request
     */
    handleHTMXBeforeRequest(event) {
        const target = event.target;

        // Add loading state to buttons
        if (target.tagName === 'BUTTON' || target.type === 'submit') {
            target.disabled = true;
            target.dataset.originalText = target.textContent;
            target.textContent = 'Loading...';
        }

        // Show global loading indicator
        this.setGlobalLoading(true);
    }

    /**
     * Handle HTMX after request
     */
    handleHTMXAfterRequest(event) {
        const target = event.target;

        // Restore button state
        if (target.tagName === 'BUTTON' || target.type === 'submit') {
            target.disabled = false;
            if (target.dataset.originalText) {
                target.textContent = target.dataset.originalText;
                delete target.dataset.originalText;
            }
        }

        // Remove global loading indicator
        this.setGlobalLoading(false);
    }

    /**
     * Handle HTMX after content swap
     */
    handleHTMXAfterSwap(event) {
        // Show success toasts if configured
        const response = event.detail.xhr;
        const successMessage = response.getResponseHeader('HX-Trigger-After-Swap');
        if (successMessage && successMessage.includes('showToast')) {
            try {
                const data = JSON.parse(successMessage);
                if (data.showToast) {
                    this.showToast(data.showToast.message, data.showToast.type || 'success');
                }
            } catch (e) {
                this.showToast('Operation completed successfully', 'success');
            }
        }

        // Re-initialize modules for new content
        setTimeout(() => {
            this.reinitializeModules(event.target);
        }, 10);
    }

    /**
     * Reinitialize modules for new content
     */
    reinitializeModules(container = document) {
        // Check if we need to reinitialize table functionality
        if (container.querySelector('.table') || container.classList?.contains('table')) {
            if (this.tableManager) {
                this.tableManager.init();
            }
            if (this.bulkActions) {
                this.bulkActions.init();
            }
        }

        // Check if we need to reinitialize pagination
        if (container.querySelector('.pagination') || container.classList?.contains('pagination')) {
            if (this.paginationManager) {
                this.paginationManager.init();
            }
        }
    }

    /**
     * Create global loading indicator
     */
    createGlobalLoader() {
        if (document.querySelector('.global-loader')) return; // Already exists

        const loader = document.createElement('div');
        loader.className = 'global-loader';
        loader.style.display = 'none';
        document.body.appendChild(loader);
    }

    /**
     * Set global loading state
     */
    setGlobalLoading(loading) {
        const body = document.body;
        const loader = document.querySelector('.global-loader');

        if (loading) {
            body.classList.add('htmx-request');
            if (loader) loader.style.display = 'block';
        } else {
            body.classList.remove('htmx-request');
            if (loader) loader.style.display = 'none';
        }
    }

    /**
     * Form validation enhancements
     */
    setupFormValidation() {
        document.addEventListener('htmx:afterRequest', (event) => {
            const form = event.target.closest('form');
            if (form) {
                this.validateForm(form);
            }
        });
    }

    /**
     * Validate form
     */
    validateForm(form) {
        const inputs = form.querySelectorAll('input, textarea, select');
        let isValid = true;

        inputs.forEach(input => {
            const errorElement = form.querySelector(`[data-error-for="${input.name}"]`);

            // Clear previous errors
            if (errorElement) {
                errorElement.textContent = '';
                errorElement.style.display = 'none';
            }
            input.classList.remove('border-red-500');

            // Validate required fields
            if (input.hasAttribute('required') && !input.value.trim()) {
                this.showFieldError(input, 'This field is required');
                isValid = false;
            }

            // Validate email fields
            if (input.type === 'email' && input.value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(input.value)) {
                    this.showFieldError(input, 'Please enter a valid email address');
                    isValid = false;
                }
            }

            // Validate URL fields
            if (input.type === 'url' && input.value) {
                try {
                    new URL(input.value);
                } catch {
                    this.showFieldError(input, 'Please enter a valid URL');
                    isValid = false;
                }
            }
        });

        return isValid;
    }

    /**
     * Show field validation error
     */
    showFieldError(input, message) {
        input.classList.add('border-red-500');

        const form = input.closest('form');
        const errorElement = form.querySelector(`[data-error-for="${input.name}"]`);

        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        } else {
            const error = document.createElement('div');
            error.className = 'text-red-500 text-sm mt-1';
            error.setAttribute('data-error-for', input.name);
            error.textContent = message;
            input.parentNode.insertBefore(error, input.nextSibling);
        }
    }

    /**
     * Setup confirmation dialogs
     */
    setupConfirmDialogs() {
        document.addEventListener('click', (event) => {
            const target = event.target;

            // Skip elements that already have hx-confirm attribute to avoid duplicate confirmation dialogs
            if ((target.classList.contains('btn-danger') || target.hasAttribute('hx-delete')) && !target.hasAttribute('hx-confirm')) {
                const message = target.getAttribute('data-confirm') ||
                    'Are you sure you want to delete this item?';
                if (!confirm(message)) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            }
        });
    }

    /**
     * Setup toast notifications
     */
    setupToasts() {
        // Error toasts are handled in handleHTMXError
        // Success toasts are handled in handleHTMXAfterSwap
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            min-width: 300px;
            animation: slideInRight 0.3s ease-out;
        `;
        toast.textContent = message;

        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.className = 'float-right ml-2 cursor-pointer';
        closeBtn.onclick = () => this.hideToast(toast);
        toast.appendChild(closeBtn);

        document.body.appendChild(toast);

        // Auto-hide after 5 seconds
        setTimeout(() => this.hideToast(toast), 5000);
        return toast;
    }

    /**
     * Hide toast notification
     */
    hideToast(toast) {
        toast.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    /**
     * Show keyboard shortcuts help
     */
    showKeyboardShortcuts() {
        const shortcuts = [
            {key: 'Ctrl + ←/→', description: 'Navigate pagination'},
            {key: 'Alt + PgUp/PgDn', description: 'Navigate pagination'},
            {key: 'Escape', description: 'Clear selections/Close modals'},
            {key: 'Ctrl + S', description: 'Save form'},
            {key: 'Ctrl + /', description: 'Show this help'}
        ];

        const helpContent = shortcuts.map(shortcut =>
            `<div class="flex justify-between py-1">
                <kbd class="px-2 py-1 bg-gray-200 rounded text-sm">${shortcut.key}</kbd>
                <span>${shortcut.description}</span>
            </div>`
        ).join('');

        this.showToast(`
            <div class="keyboard-shortcuts">
                <h4 class="font-bold mb-2">Keyboard Shortcuts</h4>
                ${helpContent}
            </div>
        `, 'info');
    }

    /**
     * Add CSS animations
     */
    addCSSAnimations() {
        if (document.getElementById('fast-admin-styles')) return;

        const style = document.createElement('style');
        style.id = 'fast-admin-styles';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
            
            .toast {
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                border-radius: 0.375rem;
            }
            
            .global-loader {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 4px;
                background: linear-gradient(90deg, #3b82f6, #60a5fa, #3b82f6);
                background-size: 200% 100%;
                animation: loading 2s infinite;
                z-index: 9999;
                display: none;
            }
            
            @keyframes loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }

            .fade-in {
                animation: fadeIn 0.3s ease-in;
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Check if an input element is focused
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
     * Handle page becoming hidden
     */
    handlePageHidden() {
        this.dispatchEvent('admin:pageHidden');
    }

    /**
     * Handle page becoming visible
     */
    handlePageVisible() {
        this.dispatchEvent('admin:pageVisible');
    }

    /**
     * Handle window resize
     */
    handleWindowResize() {
        this.dispatchEvent('admin:windowResize', {
            width: window.innerWidth,
            height: window.innerHeight
        });
    }

    /**
     * Handle initialization errors
     */
    handleInitializationError(error) {
        console.error('FastAdmin initialization failed:', error);
        this.showToast('Admin interface failed to initialize. Some features may not work.', 'error');
    }

    /**
     * Get status of all modules
     */
    getModuleStatus() {
        return {
            tableManager: !!this.tableManager,
            bulkActions: !!this.bulkActions,
            paginationManager: !!this.paginationManager,
            htmx: typeof htmx !== 'undefined'
        };
    }

    /**
     * Dispatch custom events
     */
    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(eventName, {detail});
        document.dispatchEvent(event);
    }

    /**
     * Destroy admin instance
     */
    destroy() {
        this.initialized = false;
        this.tableManager = null;
        this.bulkActions = null;
        this.paginationManager = null;

        this.dispatchEvent('admin:destroyed');
    }
}

// Legacy function for clearSelection - needed for template compatibility
function clearSelection() {
    if (window.fastAdmin?.tableManager) {
        window.fastAdmin.tableManager.clearSelection();
    }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
    window.fastAdmin = new FastAdmin();
    window.fastAdmin.init();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FastAdmin;
}