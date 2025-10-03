/**
 * QuickExpense Web UI JavaScript
 * Handles file upload, auth status, and results display
 */

class QuickExpenseUI {
    constructor() {
        this.authStatus = null;
        this.isProcessing = false;

        // DOM elements
        this.elements = {
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            authDetails: document.getElementById('authDetails'),
            connectBtn: document.getElementById('connectBtn'),
            uploadZone: document.getElementById('uploadZone'),
            fileInput: document.getElementById('fileInput'),
            processingState: document.getElementById('processingState'),
            processingMessage: document.getElementById('processingMessage'),
            resultsSection: document.getElementById('resultsSection'),
            errorSection: document.getElementById('errorSection'),
            errorMessage: document.getElementById('errorMessage'),
            receiptBasic: document.getElementById('receiptBasic'),
            taxBasic: document.getElementById('taxBasic'),
            businessRulesBasic: document.getElementById('businessRulesBasic'),
            toggleDetails: document.getElementById('toggleDetails'),
            detailedInfo: document.getElementById('detailedInfo'),
            expenseSummaryDetailed: document.getElementById('expenseSummaryDetailed'),
            processAnotherBtn: document.getElementById('processAnotherBtn'),
            tryAgainBtn: document.getElementById('tryAgainBtn')
        };

        this.init();
    }

    init() {
        this.checkAuthStatus();
        this.setupEventListeners();
        this.setupDropZone();
        this.setupDetailsToggle();
    }

    // ===== AUTH STATUS MANAGEMENT =====

    async checkAuthStatus() {
        try {
            const response = await fetch('/api/web/auth-status');
            const data = await response.json();

            this.authStatus = data;
            this.updateAuthUI(data);
        } catch (error) {
            console.error('Error checking auth status:', error);
            this.updateAuthUI({
                authenticated: false,
                message: 'Unable to check authentication status'
            });
        }
    }

    updateAuthUI(authData) {
        const { statusDot, statusText, authDetails, connectBtn } = this.elements;

        if (authData.authenticated) {
            statusDot.classList.remove('error');
            statusDot.classList.add('connected');
            statusText.textContent = 'Connected to QuickBooks';
            authDetails.textContent = authData.company_name ?
                `Company: ${authData.company_name}` :
                `Company ID: ${authData.company_id || 'Unknown'}`;
            connectBtn.style.display = 'none';
        } else {
            statusDot.classList.remove('connected');
            statusDot.classList.add('error');
            statusText.textContent = 'Not connected to QuickBooks';
            authDetails.textContent = authData.message || 'Authentication required';
            connectBtn.style.display = 'inline-flex';
        }
    }

    async handleConnectClick() {
        try {
            const response = await fetch('/api/web/auth-url');
            const data = await response.json();

            if (data.auth_url) {
                this.openOAuthPopup(data.auth_url);
            } else {
                throw new Error('No authorization URL received');
            }
        } catch (error) {
            console.error('Error getting auth URL:', error);
            this.showError('Failed to initiate QuickBooks connection');
        }
    }

    openOAuthPopup(authUrl) {
        const popup = window.open(
            authUrl,
            'quickbooks_oauth',
            'width=600,height=700,scrollbars=yes,resizable=yes'
        );

        // Listen for messages from popup
        const messageHandler = (event) => {
            if (event.data.type === 'oauth_success') {
                popup.close();
                window.removeEventListener('message', messageHandler);
                this.handleOAuthSuccess();
            } else if (event.data.type === 'oauth_error') {
                popup.close();
                window.removeEventListener('message', messageHandler);
                this.showError('QuickBooks authentication failed');
            }
        };

        window.addEventListener('message', messageHandler);

        // Poll for popup close (fallback)
        const pollTimer = setInterval(() => {
            if (popup.closed) {
                clearInterval(pollTimer);
                window.removeEventListener('message', messageHandler);
                // Check auth status in case popup closed without message
                setTimeout(() => this.checkAuthStatus(), 1000);
            }
        }, 1000);
    }

    handleOAuthSuccess() {
        this.checkAuthStatus();
        this.showSuccessMessage('Successfully connected to QuickBooks!');
    }

    // ===== FILE UPLOAD MANAGEMENT =====

    setupEventListeners() {
        const { connectBtn, uploadZone, fileInput, processAnotherBtn, tryAgainBtn } = this.elements;

        connectBtn.addEventListener('click', () => this.handleConnectClick());
        uploadZone.addEventListener('click', () => this.handleUploadClick());
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        processAnotherBtn.addEventListener('click', () => this.resetToUpload());
        tryAgainBtn.addEventListener('click', () => this.resetToUpload());
    }

    setupDropZone() {
        const { uploadZone } = this.elements;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => this.highlight(), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => this.unhighlight(), false);
        });

        // Handle dropped files
        uploadZone.addEventListener('drop', (e) => this.handleDrop(e), false);
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight() {
        this.elements.uploadZone.classList.add('drag-over');
    }

    unhighlight() {
        this.elements.uploadZone.classList.remove('drag-over');
    }

    handleUploadClick() {
        if (!this.isProcessing) {
            this.elements.fileInput.click();
        }
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    // ===== FILE VALIDATION =====

    validateFile(file) {
        // Check if file exists
        if (!file) {
            throw new Error('No file selected. Please choose a receipt file to upload.');
        }

        // Check file name
        if (!file.name || file.name.trim() === '') {
            throw new Error('Invalid file. Please select a valid receipt file.');
        }

        const supportedTypes = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/bmp', 'image/webp', 'application/pdf'
        ];

        const supportedExtensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.pdf', '.heic', '.heif'
        ];

        const maxSize = 10 * 1024 * 1024; // 10MB
        const minSize = 1024; // 1KB minimum

        // Check file size
        if (file.size === 0) {
            throw new Error('File appears to be empty. Please select a valid receipt file.');
        }

        if (file.size < minSize) {
            throw new Error('File too small. Please select a valid receipt image or PDF.');
        }

        if (file.size > maxSize) {
            const maxSizeMB = Math.round(maxSize / (1024 * 1024));
            const fileSizeMB = Math.round(file.size / (1024 * 1024) * 10) / 10;
            throw new Error(`File too large (${fileSizeMB}MB). Maximum size is ${maxSizeMB}MB.`);
        }

        // Check file type and extension
        const fileName = file.name.toLowerCase();
        const hasValidExtension = supportedExtensions.some(ext => fileName.endsWith(ext));
        const hasValidType = supportedTypes.includes(file.type) || fileName.endsWith('.heic') || fileName.endsWith('.heif');

        if (!hasValidExtension && !hasValidType) {
            throw new Error(`Unsupported file format "${file.name.split('.').pop()?.toUpperCase() || 'unknown'}". Please use JPEG, PNG, PDF, or HEIC files.`);
        }

        // Additional validation for suspicious files
        const suspiciousExtensions = ['.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.jar'];
        const isSuspicious = suspiciousExtensions.some(ext => fileName.endsWith(ext));

        if (isSuspicious) {
            throw new Error('Invalid file type. Please upload only receipt images or PDFs.');
        }

        return true;
    }

    // ===== FILE PROCESSING =====

    async processFile(file) {
        if (this.isProcessing) return;

        try {
            // Check authentication first
            if (!this.authStatus?.authenticated) {
                this.showError('Please connect to QuickBooks before uploading receipts. Click the "Connect to QuickBooks" button above.');
                return;
            }

            // Validate file
            this.validateFile(file);

            // Start processing
            this.isProcessing = true;
            this.showProcessing(`Extracting data from ${file.name}...`);

            // Prepare form data
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', '');
            formData.append('additional_context', '');

            // Add dry-run option
            const dryRunCheckbox = document.getElementById('dryRunCheckbox');
            formData.append('dry_run', dryRunCheckbox ? dryRunCheckbox.checked : false);

            // Update processing message
            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'Analyzing receipt with AI... (this may take 2-3 minutes)';
                }
            }, 5000);

            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'AI processing complete. Applying business rules...';
                }
            }, 90000); // After ~1.5 minutes

            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'Creating expense in QuickBooks...';
                }
            }, 120000); // After ~2 minutes

            // Upload and process with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout for Gemini AI processing

            let response;
            try {
                response = await fetch('/api/web/upload-receipt', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
            } catch (fetchError) {
                clearTimeout(timeoutId);

                if (fetchError.name === 'AbortError') {
                    throw new Error('Processing timed out after 3 minutes. AI processing of large files can take time. Please try again.');
                }

                if (!navigator.onLine) {
                    throw new Error('No internet connection. Please check your network and try again.');
                }

                throw new Error('Network error. Please check your connection and try again.');
            }

            // Handle response
            if (!response.ok) {
                let errorMessage = `Server error (${response.status})`;

                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;

                    // Handle specific error types
                    if (response.status === 401 || response.status === 403) {
                        errorMessage = 'Authentication expired. Please reconnect to QuickBooks.';
                        // Refresh auth status
                        this.checkAuthStatus();
                    } else if (response.status === 413) {
                        errorMessage = 'File too large for server. Please use a smaller file.';
                    } else if (response.status === 422) {
                        errorMessage = 'Invalid file format or corrupted file. Please try a different file.';
                    } else if (response.status === 500) {
                        errorMessage = 'Server error while processing. Please try again in a moment.';
                    }

                } catch (parseError) {
                    console.warn('Could not parse error response:', parseError);
                }

                throw new Error(errorMessage);
            }

            const result = await response.json();
            console.log('Response received:', result);

            // Validate response structure
            if (!result || typeof result !== 'object') {
                throw new Error('Invalid response from server. Please try again.');
            }

            if (result.status !== 'success') {
                throw new Error(result.message || 'Processing failed. Please try again.');
            }

            console.log('About to show results with:', result);

            // Ensure we have the required data structure
            if (!result.receipt_info) {
                console.warn('Missing receipt_info, using empty object');
                result.receipt_info = {};
            }
            if (!result.tax_deductibility) {
                console.warn('Missing tax_deductibility, using empty object');
                result.tax_deductibility = {};
            }
            if (!result.business_rules) {
                console.warn('Missing business_rules, using empty object');
                result.business_rules = {};
            }

            this.showResults(result);

        } catch (error) {
            console.error('Error processing file:', error);

            // Provide user-friendly error messages
            let userMessage = error.message;

            // Handle common error patterns
            if (userMessage.toLowerCase().includes('token') || userMessage.toLowerCase().includes('auth')) {
                userMessage = 'Authentication issue. Please reconnect to QuickBooks and try again.';
                this.checkAuthStatus(); // Refresh auth status
            } else if (userMessage.toLowerCase().includes('network') || userMessage.toLowerCase().includes('fetch')) {
                userMessage = 'Network error. Please check your internet connection and try again.';
            } else if (userMessage.toLowerCase().includes('timeout')) {
                userMessage = 'Processing timed out. AI processing can take 2-3 minutes for large files.';
            } else if (userMessage.toLowerCase().includes('gemini') || userMessage.toLowerCase().includes('ai')) {
                userMessage = 'AI processing error. Please try again or use a clearer receipt image.';
            } else if (userMessage.toLowerCase().includes('quickbooks')) {
                userMessage = 'QuickBooks integration error. Please verify your connection and try again.';
            }

            this.showError(userMessage || 'An unexpected error occurred while processing your receipt.');
        } finally {
            this.isProcessing = false;
        }
    }

    // ===== UI STATE MANAGEMENT =====

    showProcessing(message) {
        const { uploadZone, processingState, processingMessage, resultsSection, errorSection } = this.elements;

        uploadZone.style.display = 'none';
        processingState.style.display = 'block';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';

        processingMessage.textContent = message;
    }

    showResults(data) {
        const { uploadZone, processingState, resultsSection, errorSection } = this.elements;

        // Hide the entire upload section when showing results
        const uploadSection = document.querySelector('.upload-section');
        if (uploadSection) {
            uploadSection.style.display = 'none';
        }

        uploadZone.style.display = 'none';
        processingState.style.display = 'none';
        resultsSection.style.display = 'block';
        errorSection.style.display = 'none';

        // Update title for dry-run mode
        const resultsTitle = resultsSection.querySelector('h2');
        if (data.dry_run) {
            resultsTitle.textContent = 'Receipt Processed (Dry Run - Preview Only)';
        } else {
            resultsTitle.textContent = 'Receipt Processed Successfully';
        }

        this.populateResults(data);
    }

    showError(message) {
        const { uploadZone, processingState, resultsSection, errorSection, errorMessage } = this.elements;

        uploadZone.style.display = 'block';
        processingState.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'block';

        errorMessage.textContent = message;
    }

    resetToUpload() {
        const { uploadZone, processingState, resultsSection, errorSection, fileInput } = this.elements;

        // Show the entire upload section when resetting
        const uploadSection = document.querySelector('.upload-section');
        if (uploadSection) {
            uploadSection.style.display = 'block';
        }

        uploadZone.style.display = 'flex';
        processingState.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';

        // Reset file input
        fileInput.value = '';
        this.isProcessing = false;
    }

    showSuccessMessage(message) {
        // Create temporary success notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--status-success);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // ===== RESULTS DISPLAY =====

    populateResults(data) {
        console.log('Populating results with data:', data);

        try {
            console.log('Populating basic receipt info...');
            this.populateReceiptBasic(data.receipt_info);

            console.log('Populating basic tax summary...');
            this.populateTaxBasic(data.tax_deductibility);

            console.log('Populating business rules...');
            this.populateBusinessRulesBasic(data.business_rules, data.dry_run);

            console.log('Populating detailed information...');
            this.populateDetailedInfo(data);

            console.log('All populate methods completed successfully');
        } catch (error) {
            console.error('Error in populateResults:', error);
            // Don't re-throw, just log the error and continue
            // This allows partial results to be displayed
        }
    }

    populateReceiptBasic(receiptInfo) {
        const container = this.elements.receiptBasic;
        if (!container) {
            console.error('Receipt container not found');
            return;
        }
        container.innerHTML = '';

        if (!receiptInfo) {
            container.innerHTML = '<p>Receipt information not available</p>';
            return;
        }

        const data = [
            { label: 'Vendor', value: receiptInfo.vendor_name || 'Unknown' },
            { label: 'Date', value: receiptInfo.date ? new Date(receiptInfo.date).toLocaleDateString('en-CA') : 'Unknown' },
            { label: 'Total', value: `$${receiptInfo.total_amount?.toFixed(2) || '0.00'}`, className: 'amount' },
            { label: 'Currency', value: receiptInfo.currency || 'CAD' }
        ];

        data.forEach(item => {
            const row = this.createDataRow(item.label, item.value, item.className);
            container.appendChild(row);
        });
    }

    populateTaxBasic(taxData) {
        const container = this.elements.taxBasic;
        if (!container) {
            console.error('Tax container not found');
            return;
        }
        container.innerHTML = '';

        if (!taxData) {
            container.innerHTML = '<p>Tax information not available</p>';
            return;
        }

        const totalAmount = parseFloat(taxData.total_amount) || 0;
        const deductibleAmount = parseFloat(taxData.deductible_amount) || 0;
        const deductibilityRate = parseFloat(taxData.deductibility_rate) || 0;

        const data = [
            { label: 'Total Amount', value: `$${totalAmount.toFixed(2)}`, className: 'amount' },
            { label: 'Deductible', value: `$${deductibleAmount.toFixed(2)}`, className: 'amount highlight' },
            { label: 'Rate', value: `${deductibilityRate.toFixed(1)}%`, className: 'highlight' }
        ];

        data.forEach(item => {
            const row = this.createDataRow(item.label, item.value, item.className);
            container.appendChild(row);
        });
    }

    populateBusinessRulesBasic(businessRules, isDryRun = false) {
        const container = this.elements.businessRulesBasic;
        if (!container) {
            console.error('Business rules container not found');
            return;
        }
        container.innerHTML = '';

        // Add dry run indicator at the top if applicable
        if (isDryRun) {
            const dryRunIndicator = document.createElement('div');
            dryRunIndicator.className = 'dry-run-indicator';
            dryRunIndicator.innerHTML = '<strong>Mode:</strong> Dry Run (Preview Only)';
            dryRunIndicator.style.marginBottom = '1rem';
            dryRunIndicator.style.padding = '0.5rem';
            dryRunIndicator.style.backgroundColor = 'var(--peach-light)';
            dryRunIndicator.style.borderRadius = 'var(--radius-sm)';
            dryRunIndicator.style.fontSize = '0.875rem';
            container.appendChild(dryRunIndicator);
        }

        if (!businessRules?.applied_rules?.length) {
            const noRulesMsg = document.createElement('p');
            noRulesMsg.textContent = 'No business rules applied';
            noRulesMsg.style.color = 'var(--text-muted)';
            container.appendChild(noRulesMsg);
            return;
        }

        // Display each applied rule
        businessRules.applied_rules.forEach((rule, index) => {
            const ruleDiv = document.createElement('div');
            ruleDiv.className = 'rule-item-compact';
            if (index > 0) {
                ruleDiv.style.marginTop = '1rem';
                ruleDiv.style.paddingTop = '1rem';
                ruleDiv.style.borderTop = '1px solid var(--border-light)';
            }

            // Rule name
            const ruleName = document.createElement('div');
            ruleName.className = 'rule-name-compact';
            ruleName.textContent = rule.description || rule.rule_applied;
            ruleName.style.fontWeight = '500';
            ruleName.style.marginBottom = '0.5rem';
            ruleDiv.appendChild(ruleName);

            // Rule details in compact format
            const details = [
                { label: 'Category', value: rule.category },
                { label: 'Account', value: rule.qb_account },
                { label: 'Deductible', value: `${rule.deductible_percentage}%`, className: 'highlight' },
                { label: 'Amount', value: `$${(rule.amount || 0).toFixed(2)}`, className: 'amount' }
            ];

            details.forEach(detail => {
                const row = this.createDataRow(detail.label, detail.value, detail.className);
                row.style.fontSize = '0.875rem';
                ruleDiv.appendChild(row);
            });

            container.appendChild(ruleDiv);
        });
    }

    populateDetailedInfo(data) {
        // Only populate expense summary details
        this.populateExpenseSummaryDetailed(data.enhanced_expense);
    }


    populateExpenseSummaryDetailed(expenseData) {
        const container = this.elements.expenseSummaryDetailed;
        if (!container) {
            console.error('Expense summary container not found');
            return;
        }
        container.innerHTML = '';

        // Create a summary based on available data
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'rule-item-simple';

        const details = document.createElement('div');
        details.className = 'rule-details-simple';

        // Build summary from available data
        let summaryHtml = '';

        if (expenseData) {
            // Try to extract meaningful information from the expense data
            const itemsCount = expenseData.items_count ||
                               (expenseData.line_items?.length) ||
                               (Array.isArray(expenseData) ? expenseData.length : 1);

            const categoriesSet = new Set();
            if (expenseData.line_items) {
                expenseData.line_items.forEach(item => {
                    if (item.category) categoriesSet.add(item.category);
                });
            } else if (expenseData.category) {
                categoriesSet.add(expenseData.category);
            }

            summaryHtml = `
                <strong>Items Processed:</strong> ${itemsCount}<br>
                <strong>Categories Found:</strong> ${categoriesSet.size || 1}<br>
                <strong>Processing Time:</strong> ${new Date().toLocaleTimeString('en-CA')}<br>
                <strong>Payment Method:</strong> ${expenseData.payment || 'Not specified'}
            `;
        } else {
            summaryHtml = `
                <strong>Processing Time:</strong> ${new Date().toLocaleTimeString('en-CA')}<br>
                <strong>Status:</strong> Completed
            `;
        }

        details.innerHTML = summaryHtml;
        summaryDiv.appendChild(details);
        container.appendChild(summaryDiv);
    }

    setupDetailsToggle() {
        const toggleBtn = this.elements.toggleDetails;
        const detailedInfo = this.elements.detailedInfo;
        const toggleText = document.getElementById('toggleText');
        const toggleIcon = document.getElementById('toggleIcon');

        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', () => {
            const isHidden = detailedInfo.style.display === 'none';

            if (isHidden) {
                detailedInfo.style.display = 'block';
                toggleText.textContent = 'Hide Details';
                toggleIcon.textContent = '▲';
            } else {
                detailedInfo.style.display = 'none';
                toggleText.textContent = 'Show Details';
                toggleIcon.textContent = '▼';
            }
        });
    }

    createDataRow(label, value, className = '') {
        const row = document.createElement('div');
        row.className = 'data-row';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'data-label';
        labelSpan.textContent = label;

        const valueSpan = document.createElement('span');
        valueSpan.className = `data-value ${className}`.trim();
        valueSpan.textContent = value;

        row.appendChild(labelSpan);
        row.appendChild(valueSpan);

        return row;
    }




    formatCurrency(amount) {
        if (amount === null || amount === undefined) return '$0.00';
        return new Intl.NumberFormat('en-CA', {
            style: 'currency',
            currency: 'CAD'
        }).format(amount);
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new QuickExpenseUI();
});

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);
