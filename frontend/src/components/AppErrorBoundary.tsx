import { Component, type ErrorInfo, type ReactNode } from 'react'
import { logUiEvent } from '../observability'

type Props = { children: ReactNode }
type State = { failed: boolean }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logUiEvent('unexpected_ui_error', 'error', {
      error_type: error.name,
      component_stack_present: Boolean(info.componentStack),
    })
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="mx-auto max-w-3xl px-6 py-24">
          <h1 className="text-2xl font-semibold">Không thể hiển thị trang</h1>
          <p className="mt-3 text-slate-600">Vui lòng tải lại trang hoặc thử lại sau.</p>
        </main>
      )
    }
    return this.props.children
  }
}
