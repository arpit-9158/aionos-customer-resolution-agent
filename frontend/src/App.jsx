import { startTransition, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const quickActions = {
  'priya-nair': [
    'I want a full refund for the cancelled flight.',
    'Can you rebook me on the next available flight within 24 hours?',
    'I want a free business class upgrade on my return flight.',
    'Escalate this unsupported request to a human agent.',
  ],
  'arvind-kulkarni': [
    'My flight is delayed by four hours. I need a hotel.',
    'Can I receive the meal voucher and lounge access?',
    'I need an exception because I missed a connecting meeting.',
    'Escalate this request if it is outside policy.',
  ],
  'meher-kaur': [
    'I want a full night hotel stay and I need a different flight.',
    'The fare difference is ₹2,000. Please waive it.',
    'I need the hotel and meal voucher covered by policy.',
    'Escalate the fare-difference exception to a supervisor.',
  ],
}

const defaultMessages = {
  'priya-nair': 'I understand this is frustrating. I can explain the cancellation support options available under the policy.',
  'arvind-kulkarni': 'I can review the delay policy and the specific support available for your travel disruption.',
  'meher-kaur': 'I can review the delay and fare-difference rules for your itinerary and clarify what requires supervisor approval.',
}

const demoScenarios = [
  { customerId: 'priya-nair', name: 'Priya', detail: 'Cancellation + upgrade request', flight: 'SK-204', tier: 'Gold', message: 'My flight was cancelled. I want a full refund and a free business class upgrade.' },
  { customerId: 'arvind-kulkarni', name: 'Arvind', detail: '4h delay + hotel request', flight: 'SK-118', tier: 'Silver', message: 'My flight is delayed by four hours. I need a hotel.' },
  { customerId: 'meher-kaur', name: 'Meher', detail: '6h delay + ₹2,000 waiver', flight: 'SK-305', tier: 'Platinum', message: "I want a full night's hotel and I want to switch to another flight. The fare difference is ₹2,000. Waive it." },
]

const quickActionMeta = [
  { match: 'refund', label: 'Refund', icon: '↩' },
  { match: 'rebook', label: 'Rebook', icon: '↗' },
  { match: 'meal', label: 'Meal voucher', icon: '＋' },
  { match: 'lounge', label: 'Lounge', icon: '◇' },
  { match: 'hotel', label: 'Hotel', icon: '⌂' },
  { match: 'escalate', label: 'Escalate', icon: '!' },
]

const getQuickAction = (text) => quickActionMeta.find((action) => text.toLowerCase().includes(action.match)) || { label: 'Policy review', icon: 'i' }

function App() {
  const [customers, setCustomers] = useState([])
  const [selectedCustomerId, setSelectedCustomerId] = useState('priya-nair')
  const [customerProfile, setCustomerProfile] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [failedMessage, setFailedMessage] = useState('')
  const [lastResponse, setLastResponse] = useState(null)
  const [auditLog, setAuditLog] = useState([])
  const [actionState, setActionState] = useState({})
  const threadRef = useRef(null)

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.customer_id === selectedCustomerId) || null,
    [customers, selectedCustomerId],
  )

  useEffect(() => {
    const loadCustomers = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/customers`)
        if (!response.ok) throw new Error('Unable to fetch customer list')
        const data = await response.json()
        setCustomers(data)
        if (data.length > 0) setSelectedCustomerId(data[0].customer_id)
      } catch {
        setError('Unable to connect to the AIONOS backend. Please ensure the API is running on port 8000.')
      }
    }

    loadCustomers()
  }, [])

  useEffect(() => {
    if (!selectedCustomer) return

    const greeting = defaultMessages[selectedCustomer.customer_id] || 'I can help review the available policy options for this trip.'
    startTransition(() => {
      setMessages([{ type: 'agent', text: greeting }])
      setLastResponse(null)
      setError('')
      setFailedMessage('')
      setAuditLog([])
      setActionState({})
      setInput('')
    })
  }, [selectedCustomer])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    if (!selectedCustomerId) return
    fetch(`${API_BASE_URL}/api/customers/${selectedCustomerId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => setCustomerProfile(data))
      .catch(() => setCustomerProfile(null))
  }, [selectedCustomerId])

  const appendAudit = (response) => {
    const title = response?.escalation?.required ? 'ESCALATION REQUIRED' : response?.allowed_actions?.length ? 'ALLOWED' : 'NOT ELIGIBLE'
    const content = response?.escalation?.required
      ? response?.escalation?.reason || 'Escalation required'
      : response?.allowed_actions?.[0]?.reason || 'No policy-backed action available'

    setAuditLog((current) => [{
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      action: 'Policy evaluated',
      status: title,
      reason: content,
    }, ...current])
  }

  const appendEvent = (action, status, reason) => {
    setAuditLog((current) => [{
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      action,
      status,
      reason,
    }, ...current])
  }

  const sendMessage = async (messageTextOverride, customerIdOverride) => {
    const messageToSend = (messageTextOverride ?? input).trim()
    const customerId = customerIdOverride || selectedCustomerId
    if (!messageToSend || !customerId || isLoading) return

    setMessages((current) => [...current, { type: 'user', text: messageToSend }])
    setInput('')
    setIsLoading(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: customerId, message: messageToSend }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Unable to process response')
      }

      const payload = await response.json()
      setFailedMessage('')
      setLastResponse(payload)
      setMessages((current) => [...current, { type: 'agent', text: payload.message }])
      appendAudit(payload)
    } catch (chatError) {
      setFailedMessage(messageToSend)
      setError(chatError.message || 'Something went wrong while contacting the backend.')
      setMessages((current) => [...current, { type: 'agent', text: 'I could not process this response because the policy service is unavailable.' }])
    } finally {
      setIsLoading(false)
    }
  }

  const submitAction = async (action, isEscalation = false) => {
    const actionKey = `${isEscalation ? 'escalation' : 'action'}-${action.type}`
    setActionState((current) => ({ ...current, [actionKey]: 'PROCESSING' }))
    try {
      const response = await fetch(`${API_BASE_URL}/api/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: selectedCustomerId, action_type: action.type, request: action.label }),
      })
      if (!response.ok) throw new Error('The action service could not accept this request.')
      const payload = await response.json()
      const status = payload.status === 'created' ? 'CREATED' : 'REQUESTED'
      setActionState((current) => ({ ...current, [actionKey]: status }))
      appendEvent(isEscalation ? 'Escalation created' : `${action.label} requested`, status, payload.message)
    } catch (actionError) {
      setActionState((current) => ({ ...current, [actionKey]: 'FAILED' }))
      setError(actionError.message)
      appendEvent(isEscalation ? 'Escalation request' : `${action.label} request`, 'FAILED', actionError.message)
    }
  }

  const runDemo = (scenario) => {
    setSelectedCustomerId(scenario.customerId)
    setTimeout(() => sendMessage(scenario.message, scenario.customerId), 0)
  }

  const flight = customerProfile?.bookings?.[0] || selectedCustomer?.bookings?.[0] || null

  const decisionFacts = useMemo(() => {
    if (!lastResponse || !flight) return []
    const facts = []
    if (flight.status === 'cancelled') {
      facts.push('Airline-caused cancellation')
      if (lastResponse.allowed_actions?.some((action) => action.type === 'refund')) facts.push('Full refund eligible')
      facts.push('Refund → original payment method')
      facts.push('Processing → within 7 business days')
    }
    if (flight.status === 'delayed') {
      facts.push(`Delay = ${flight.delay_hours} hours`)
      if (lastResponse.allowed_actions?.some((action) => action.type === 'meal_voucher')) facts.push('Meal voucher eligible')
      if (lastResponse.allowed_actions?.some((action) => action.type === 'lounge_access')) facts.push('Lounge access eligible')
      if (lastResponse.allowed_actions?.some((action) => action.type === 'hotel')) facts.push('Hotel eligible for delayed hours only')
    }
    if (lastResponse.escalation?.required) facts.push(lastResponse.escalation.reason)
    return facts
  }, [flight, lastResponse])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">A</div>
          <div>
            <p className="eyebrow">AIONOS</p>
            <h1>Resolution Agent</h1>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-heading">
            <p className="section-label">Customers</p>
            <span className="customer-count">{customers.length}</span>
          </div>
          <div className="customer-list">
            {customers.map((customer) => (
              <button
                key={customer.customer_id}
                type="button"
                className={`customer-pill ${customer.customer_id === selectedCustomerId ? 'selected' : ''}`}
                onClick={() => setSelectedCustomerId(customer.customer_id)}
              >
                <span className="customer-avatar">{customer.name.split(' ').map((part) => part[0]).join('')}</span>
                <span className="customer-copy"><strong>{customer.name}</strong><small>{customer.bookings?.[0]?.pnr || 'PNR unavailable'}</small></span>
                <span className="loyalty-badge">{customer.loyalty_tier}</span>
              </button>
            ))}
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Customer support <span className="live-dot" /> Live workspace</p>
            <h2>{selectedCustomer?.name || 'Select a customer'}</h2>
          </div>
          <div className="header-meta">
            {selectedCustomer && (
              <>
                <span className="badge tone-gold">{selectedCustomer.loyalty_tier}</span>
                <span className="meta-chip">PNR <strong>{flight?.pnr || 'N/A'}</strong></span>
                <span className="meta-chip">{selectedCustomer.email}</span>
              </>
            )}
          </div>
        </header>

        <section className="flight-card">
          <div className="flight-header">
            <div>
              <p className="section-label">Flight status</p>
              <div className="flight-title-row"><h3>{flight?.flight_number || '—'}</h3><span className="flight-route">{flight?.route || 'Route unavailable'}</span></div>
            </div>
            <span className={`status-badge ${flight?.status === 'cancelled' ? 'cancelled' : 'active'}`}>
              <span className="status-dot" />{flight?.status || 'Unknown'}{flight?.status === 'delayed' && flight?.delay_hours ? ` ${flight.delay_hours}h` : ''}
            </span>
          </div>

          <div className="flight-grid">
            <div>
              <span>Date</span>
              <strong>{flight?.date || 'Not available'}</strong>
            </div>
            <div>
              <span>Scheduled</span>
              <strong>{flight?.scheduled_departure || 'Not available'}</strong>
            </div>
            <div>
              <span>Schedule</span>
              <strong>{flight?.new_departure ? `${flight?.scheduled_departure || '—'} → ${flight.new_departure}` : flight?.scheduled_departure || 'Not available'}</strong>
            </div>
            <div>
              <span>Reason</span>
              <strong>{flight?.reason || 'Not specified'}</strong>
            </div>
          </div>
        </section>

        <div className="content-grid">
          <section className="chat-card">
            <div className="panel-header">
              <div><p className="panel-kicker">AI resolution agent</p><h3>Conversation</h3></div>
              <span className="panel-count">{messages.length} events</span>
            </div>

            <div className="chat-thread" ref={threadRef}>
              {messages.map((message, index) => (
                <div key={`${message.type}-${index}`} className={`chat-row ${message.type}`}>
                  <div className="bubble">
                    {message.text}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="chat-row agent">
                  <div className="typing-indicator">
                    <span className="typing-label">AI agent is reviewing the disruption</span>
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
            </div>

            <div className="quick-actions">
              {(quickActions[selectedCustomerId] || []).map((text) => (
                <button key={text} type="button" className="action-chip" onClick={() => sendMessage(text)} disabled={isLoading}>
                  <span>{getQuickAction(text).icon}</span>{getQuickAction(text).label}
                </button>
              ))}
            </div>

            <div className="demo-strip">
              <div className="demo-heading"><span className="panel-kicker">Try a scenario</span><small>Run a complete assignment flow</small></div>
              <div className="demo-list">
              {demoScenarios.map((scenario) => (
                <button key={scenario.customerId} type="button" className="demo-card" onClick={() => runDemo(scenario)}>
                  <strong>{scenario.name}</strong><span>{scenario.detail}</span><small>{scenario.flight} <i>•</i> {scenario.tier}</small>
                </button>
              ))}
              </div>
            </div>

            <div className="composer">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') sendMessage()
                }}
                placeholder="Ask about the disruption, refund, rebooking, or compensation..."
                aria-label="Customer message"
              />
              <button type="button" onClick={() => sendMessage()} disabled={isLoading || !input.trim()}>
                Send
              </button>
            </div>
          </section>

          <aside className="side-stack">
            <section className="panel-card">
              <div className="panel-header">
                <div><p className="panel-kicker">Decision workspace</p><h3>Resolution</h3></div>
                {lastResponse && <span className="panel-count">Policy grounded</span>}
              </div>
              {lastResponse ? (
                <div className="resolution-box">
                  <div className={`resolution-summary ${lastResponse.escalation?.required ? 'summary-warning' : ''}`}>
                    {lastResponse.escalation?.required ? 'ESCALATION REQUIRED' : lastResponse.allowed_actions?.length ? 'POLICY DECISION: ACTIONS AVAILABLE' : 'NOT ELIGIBLE'}
                  </div>
                  <div className="resolution-list">
                    {(lastResponse.allowed_actions || []).map((action) => (
                      <div key={action.type} className="resolution-item allowed-card">
                        <div className="item-heading"><strong>{action.label}</strong><span className="state-pill allowed">ALLOWED</span></div>
                        <small>Requested action</small>
                        <p>{action.reason}</p>
                        <small>Next step</small>
                        <p>Request recorded for processing; no external airline action is claimed.</p>
                        <button className="secondary-button" type="button" disabled={actionState[`action-${action.type}`] === 'PROCESSING' || actionState[`action-${action.type}`] === 'REQUESTED'} onClick={() => submitAction(action)}>
                          {actionState[`action-${action.type}`] || 'Request action'}
                        </button>
                      </div>
                    ))}
                    {(lastResponse.recommended_actions || []).filter((action) => !lastResponse.allowed_actions?.some((a) => a.type === action.type)).map((action) => (
                      <div key={`${action.type}-rec`} className={`resolution-item ${lastResponse.escalation?.required ? 'escalation-card' : 'warning'}`}>
                        <div className="item-heading"><strong>{action.label}</strong><span className={`state-pill ${lastResponse.escalation?.required ? 'escalated' : 'not-eligible'}`}>{lastResponse.escalation?.required ? 'ESCALATION REQUIRED' : 'NOT ELIGIBLE'}</span></div>
                        <small>Requested action</small>
                        <p>{action.reason}</p>
                        <small>Next step</small>
                        <p>{lastResponse.escalation?.required ? 'Supervisor review is required before any exception can be considered.' : 'Choose an action covered by the supplied policy.'}</p>
                        {lastResponse.escalation?.required && <button className="escalation-button" type="button" disabled={actionState[`escalation-${action.type}`] === 'PROCESSING' || actionState[`escalation-${action.type}`] === 'CREATED'} onClick={() => submitAction(action, true)}>{actionState[`escalation-${action.type}`] || 'Escalate to Human'}</button>}
                      </div>
                    ))}
                  </div>
                  {decisionFacts.length > 0 && <div className="decision-trace"><div className="trace-title">Policy decision</div>{decisionFacts.map((fact) => <div key={fact} className={lastResponse.escalation?.required && fact === lastResponse.escalation.reason ? 'trace-warning' : 'trace-fact'}>{lastResponse.escalation?.required && fact === lastResponse.escalation.reason ? '!' : '✓'} {fact}</div>)}</div>}
                </div>
              ) : (
                <div className="empty-state"><span className="empty-icon">✦</span><strong>Ready to resolve</strong><p>Ask about the disruption or choose a suggested action below.</p></div>
              )}
            </section>

            <section className="panel-card">
              <div className="panel-header">
                <div><p className="panel-kicker">Session activity</p><h3>Audit trail</h3></div>
                {auditLog.length > 0 && <span className="panel-count">{auditLog.length} events</span>}
              </div>
              <div className="audit-list">
                {auditLog.length === 0 ? (
                  <div className="empty-state">Actions will appear here once the policy is applied.</div>
                ) : (
                  auditLog.map((item, index) => (
                    <div key={`${item.time}-${index}`} className="audit-item">
                      <span className="audit-line" />
                      <span className="audit-marker" />
                      <div className="audit-topline">
                        <span>{item.time}</span>
                        <span className={`tone ${item.status.toLowerCase().replace(/\s+/g, '_')}`}>
                          {item.status}
                        </span>
                      </div>
                      <strong>{item.action}</strong>
                      <p>{item.reason}</p>
                    </div>
                  ))
                )}
              </div>
            </section>
          </aside>
        </div>

        {error && <div className="error-banner"><span>{error}</span>{failedMessage && <button type="button" onClick={() => sendMessage(failedMessage)}>Retry</button>}</div>}
      </main>
    </div>
  )
}

export default App
