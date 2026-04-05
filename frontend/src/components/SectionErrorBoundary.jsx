import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class SectionErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    if (process.env.NODE_ENV !== 'production') {
      console.error(`SectionErrorBoundary [${this.props.name || 'unknown'}]:`, error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onRetry) {
      this.props.onRetry();
    }
  };

  render() {
    if (this.state.hasError) {
      const { isRTL, className, fallbackMessage } = this.props;
      const rtl = isRTL !== false;
      const defaultMessage = rtl ? 'حدث خطأ في هذا القسم' : 'An error occurred in this section';

      return (
        <div dir={rtl ? 'rtl' : 'ltr'} className={`flex flex-col items-center justify-center p-8 rounded-2xl bg-red-50/50 dark:bg-red-950/20 border border-red-200/50 dark:border-red-800/30 ${className || ''}`}>
          <div className="w-12 h-12 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-3">
            <AlertTriangle className="h-6 w-6 text-red-500" />
          </div>
          <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">
            {fallbackMessage || defaultMessage}
          </p>
          <p className="text-xs text-red-500/70 dark:text-red-400/50 mb-4">
            {rtl ? 'باقي الصفحة تعمل بشكل طبيعي' : 'The rest of the page is working normally'}
          </p>
          <button
            onClick={this.handleRetry}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 hover:bg-red-200 dark:hover:bg-red-900/60 rounded-lg transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            {rtl ? 'إعادة المحاولة' : 'Retry'}
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default SectionErrorBoundary;
