type LogLevel = 'info' | 'warning' | 'error'

const SECRET_FIELDS = /authorization|cookie|credential|key|password|secret|token/i

function safeFields(fields: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(fields).map(([name, value]) => [name, SECRET_FIELDS.test(name) ? '***' : value]),
  )
}

export function logUiEvent(
  event: string,
  level: LogLevel = 'error',
  fields: Record<string, unknown> = {},
) {
  if (level === 'info' && !import.meta.env.DEV) return
  const record = {
    timestamp: new Date().toISOString(),
    service: 'footballpulse-frontend',
    level: level.toUpperCase(),
    event,
    ...safeFields(fields),
  }
  const writer = level === 'error' ? console.error : level === 'warning' ? console.warn : console.info
  writer(JSON.stringify(record))
}
