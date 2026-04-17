import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, showDetails: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
    this.setState({ errorInfo });
  }

  toggleDetails = () => {
    this.setState((s) => ({ showDetails: !s.showDetails }));
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div dir="rtl" className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-gray-800 p-6">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="w-20 h-20 mx-auto bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">
                حدث خطأ غير متوقع
              </h2>
              <p className="text-gray-500 dark:text-gray-400 text-sm">
                نعتذر عن هذا الخطأ. يرجى إعادة تحميل الصفحة أو العودة للرئيسية.
              </p>
            </div>

            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReload}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                إعادة تحميل
              </button>
              <button
                onClick={this.handleGoHome}
                className="px-6 py-2.5 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors font-medium"
              >
                الصفحة الرئيسية
              </button>
            </div>

            {process.env.NODE_ENV !== 'production' && this.state.error && (
              <div className="text-start">
                <button
                  onClick={this.toggleDetails}
                  className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline"
                  dir="ltr"
                >
                  {this.state.showDetails ? 'Hide details' : 'Show technical details'}
                </button>
                {this.state.showDetails && (
                  <pre
                    dir="ltr"
                    className="mt-3 p-3 max-h-72 overflow-auto text-[11px] leading-relaxed text-left bg-gray-900 text-red-200 rounded-lg whitespace-pre-wrap break-words"
                  >
                    {String(this.state.error?.stack || this.state.error?.message || this.state.error)}
                    {this.state.errorInfo?.componentStack ? `\n\nComponent stack:${this.state.errorInfo.componentStack}` : ''}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
