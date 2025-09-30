# QuickExpense Web UI Implementation

## Overview

The QuickExpense web UI provides a modern, professional interface for receipt processing with an essentials-only design philosophy. The implementation focuses on clean information presentation, efficient use of space, and intuitive user experience.

## Design Philosophy

### Essentials-Only Approach
- Focus on core information: Receipt details, Tax analysis, and Status
- Secondary information hidden in expandable details section
- Minimal visual clutter with clean typography
- Professional appearance suitable for business applications

### Grid-Based Layout
- Three-column responsive grid utilizing horizontal space
- Mobile-first responsive design with breakpoints
- Consistent spacing using CSS custom properties
- Clean visual hierarchy with proper information grouping

## Technical Architecture

### Frontend Stack
- **HTML5**: Semantic structure with accessibility considerations
- **CSS Grid**: Modern layout system with responsive design
- **Vanilla JavaScript**: No external frameworks, lightweight implementation
- **CSS Custom Properties**: Consistent design system with variables

### Backend Integration
- **FastAPI Web Endpoints**: Dedicated `/api/web/` namespace
- **File Upload Handling**: Support for JPEG, PNG, PDF, HEIC formats
- **OAuth Integration**: Seamless QuickBooks authentication with popup flow
- **Real-time Processing**: WebSocket-like experience with progress feedback

## File Structure

```
src/quickexpense/web/
├── templates/
│   └── index.html              # Main web UI template
└── static/
    ├── css/
    │   └── app.css            # Grid-based styles with design system
    └── js/
        └── app.js             # UI logic and API integration
```

## Key Components

### 1. Authentication Status (`auth-status`)
- Real-time connection checking with visual indicators
- Status dot with color-coded states (connected/error)
- Company information display
- One-click authentication with OAuth popup

### 2. File Upload Zone (`upload-zone`)
- Drag-and-drop interface with visual feedback
- Click-to-select fallback option
- File validation with user-friendly error messages
- Progress indicators during processing

### 3. Essentials Grid (`essential-grid`)
Three-column layout showing:
- **Receipt Overview**: Vendor, date, total amount, currency
- **Tax Analysis**: Total amount, deductible amount, deductibility rate
- **Status**: Processing mode (live/dry-run), creation status, expense ID

### 4. Expandable Details (`detailed-info`)
- Business rules applied with confidence scores
- Processing summary with item counts
- Toggle button with smooth animation
- Secondary information organized in cards

## CSS Design System

### Color Palette
```css
/* Core Brand Colors */
--primary-dark: oklch(0.25 0 0);        /* Dark grey for text/buttons */
--background-white: oklch(1 0 0);       /* Pure white */

/* Peach/Pink Gradient System */
--peach-light: oklch(0.95 0.02 20);     /* Very soft peach */
--peach-medium: oklch(0.96 0.01 15);    /* Light peach backgrounds */
--pink-accent: oklch(0.92 0.03 25);     /* Soft pink for highlights */

/* Status Colors */
--status-success: #10b981;              /* Green for connected */
--status-warning: #f59e0b;              /* Yellow for disconnected */
--status-error: #ef4444;                /* Red for errors */
```

### Typography Scale
```css
/* Font Stack */
--font-sans: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'Geist Mono', 'SF Mono', Monaco, 'Cascadia Code', monospace;

/* Typography Hierarchy */
h1: 2.5rem, font-weight: 600
h2: 2rem, font-weight: 600
h3: 1.5rem, font-weight: 600
p: 1rem, line-height: 1.6
```

### Spacing System
```css
/* 4px Base Unit Scale */
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.25rem;   /* 20px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
```

## JavaScript Architecture

### Class-Based Structure
```javascript
class QuickExpenseUI {
    constructor() {
        // DOM element references
        // State management
        // Event binding
    }

    // Authentication methods
    checkAuthStatus()
    handleConnectClick()

    // File processing methods
    validateFile()
    processFile()

    // UI state management
    showProcessing()
    showResults()
    showError()

    // Results population
    populateReceiptBasic()
    populateTaxBasic()
    populateStatusBasic()
}
```

### Event Handling
- File drag-and-drop with visual feedback
- OAuth popup window management
- Progress state updates
- Error handling with user-friendly messages
- Responsive toggle for expandable details

## API Endpoints

### Authentication
- `GET /api/web/auth-status` - Check QuickBooks connection
- `GET /api/web/auth-url` - Generate OAuth authorization URL
- `GET /api/web/callback` - Handle OAuth callback

### Receipt Processing
- `POST /api/web/upload-receipt` - Upload and process receipt
  - File validation and processing
  - AI extraction using Gemini
  - Business rules application
  - QuickBooks expense creation

## User Experience Flow

### 1. Initial Load
1. Check authentication status
2. Display connection indicator
3. Show upload zone if authenticated
4. Provide connect button if not authenticated

### 2. Authentication Flow
1. Click "Connect to QuickBooks"
2. Open OAuth popup window
3. Complete authorization in popup
4. Receive tokens and close popup
5. Update UI to show connected state

### 3. Receipt Processing
1. Select or drag-drop receipt file
2. Validate file format and size
3. Show processing state with progress messages
4. Extract data using AI (2-3 minute timeout)
5. Apply business rules for categorization
6. Create expense in QuickBooks (or preview in dry-run)
7. Display results in essentials grid

### 4. Results Display
1. Show essential information in three columns
2. Highlight key metrics (deductible amount, rate)
3. Provide expandable details for advanced users
4. Show processing status and expense ID
5. Allow processing another receipt

## Responsive Design

### Breakpoints
- **Desktop**: 3-column grid (default)
- **Tablet** (≤900px): 2-column grid
- **Mobile** (≤600px): 1-column stack

### Mobile Optimizations
- Touch-friendly button sizes
- Simplified navigation
- Condensed information display
- Swipe-friendly interactions

## Error Handling

### Client-Side Validation
- File format checking
- File size limits (10MB)
- Network connectivity
- Browser compatibility

### Server-Side Error Mapping
- 401: Authentication expired → "Please reconnect to QuickBooks"
- 413: File too large → "File too large for server"
- 422: Invalid format → "Invalid file format or corrupted"
- 500: Server error → "Server error while processing"

## Performance Considerations

### Optimization Strategies
- Vanilla JavaScript (no framework overhead)
- CSS-only animations where possible
- Efficient DOM manipulation
- Progressive loading states
- Timeout handling for long operations

### File Processing
- 10MB file size limit
- Multiple format support with validation
- Base64 encoding for API transmission
- Progress feedback during long operations

## Accessibility Features

### Semantic HTML
- Proper heading hierarchy
- Form labels and ARIA attributes
- Keyboard navigation support
- Screen reader compatibility

### Visual Design
- High contrast ratios
- Clear visual hierarchy
- Consistent interaction patterns
- Error states with clear messaging

## Browser Compatibility

### Supported Browsers
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Required Features
- CSS Grid support
- ES6 Classes
- Fetch API
- CSS Custom Properties

## Future Enhancements

### Planned Features
1. **Batch Upload**: Multiple receipt processing
2. **Keyboard Shortcuts**: Power user efficiency
3. **Dark Mode**: Alternative color scheme
4. **Progressive Web App**: Offline capabilities
5. **Advanced Filtering**: Search and filter results

### Technical Improvements
1. **WebSocket Integration**: Real-time updates
2. **Caching Strategy**: Performance optimization
3. **Service Worker**: Offline support
4. **Bundle Optimization**: Minimize payload size

## Development Guidelines

### Code Style
- Follow existing JavaScript patterns
- Use CSS custom properties for consistency
- Maintain semantic HTML structure
- Keep functions focused and pure

### Testing Strategy
- Manual testing across browsers
- Responsive design testing
- Error scenario validation
- Performance monitoring

### Documentation
- Inline code comments for complex logic
- CSS component documentation
- API endpoint documentation
- User experience flow documentation
