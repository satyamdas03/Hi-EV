import { useEffect, useState } from 'react'
import { EV_API_URL } from '../config'
import { useStore } from '../store'

export type SetupDefaults = {
  notes_path: string
  llm_provider: string
  llm_model: string
  blocked_handles: string[]
  blocked_domains: string[]
  quiet_start: string
  quiet_end: string
  robocad_path?: string
  learningrobotics_path?: string
  hiev_path?: string
}

export function SetupWizard() {
  const setSetupNeeded = useStore((s) => s.setSetupNeeded)
  const setError = useStore((s) => s.setError)

  const [, setDefaults] = useState<SetupDefaults | null>(null)
  const [notesPath, setNotesPath] = useState('')
  const [provider, setProvider] = useState('nvidia')
  const [model, setModel] = useState('')
  const [nvidiaKey, setNvidiaKey] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [blockedHandles, setBlockedHandles] = useState('')
  const [blockedDomains, setBlockedDomains] = useState('')
  const [quietStart, setQuietStart] = useState('22:00')
  const [quietEnd, setQuietEnd] = useState('08:00')
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    fetch(`${EV_API_URL}/setup`)
      .then((res) => res.json())
      .then((data) => {
        if (!data.needs_setup) {
          setSetupNeeded(false)
          return
        }
        const defs = data.defaults as SetupDefaults
        setDefaults(defs)
        setNotesPath(defs.notes_path)
        setProvider(defs.llm_provider)
        setModel(defs.llm_model)
        setQuietStart(defs.quiet_start)
        setQuietEnd(defs.quiet_end)
      })
      .catch((err) => {
        setError(`Could not load setup status: ${err}`)
      })
  }, [setSetupNeeded, setError])

  const hasAnyKey = Boolean(nvidiaKey || anthropicKey || openaiKey)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setStatus('')

    const payload = {
      notes_path: notesPath,
      llm_provider: provider,
      llm_model: model || undefined,
      nvidia_api_key: nvidiaKey || undefined,
      anthropic_api_key: anthropicKey || undefined,
      openai_api_key: openaiKey || undefined,
      github_token: githubToken || undefined,
      blocked_handles: blockedHandles
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      blocked_domains: blockedDomains
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      quiet_start: quietStart,
      quiet_end: quietEnd,
    }

    try {
      const res = await fetch(`${EV_API_URL}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Setup failed')
      }
      setStatus('Saved. Restarting EV…')
      setTimeout(() => {
        window.location.reload()
      }, 2500)
    } catch (err) {
      setStatus(`Error: ${err}`)
      setSaving(false)
    }
  }

  return (
    <div className="setup-overlay">
      <div className="setup-modal">
        <h2>Welcome to Hi-EV</h2>
        <p className="setup-subtitle">
          Complete this one-time setup so EV can run on your machine.
          Everything stays local.
        </p>

        <form onSubmit={handleSubmit}>
          <section className="setup-section">
            <h3>1. Notes vault</h3>
            <label>
              Path to your notes folder
              <input
                type="text"
                value={notesPath}
                onChange={(e) => setNotesPath(e.target.value)}
                placeholder="C:\\Users\\you\\notes"
                required
              />
            </label>
          </section>

          <section className="setup-section">
            <h3>2. LLM provider</h3>
            <p className="setup-hint">
              EV needs a language-model API key for chat. Your key stays in your
              local .env file; it is never sent anywhere else.
            </p>
            <label>
              Provider
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="nvidia">NVIDIA NIM</option>
                <option value="anthropic">Anthropic Claude</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
            <label>
              Model (optional)
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={
                  provider === 'nvidia'
                    ? 'meta/llama-3.2-11b-vision-instruct'
                    : provider === 'anthropic'
                      ? 'claude-3-5-sonnet-20241022'
                      : 'gpt-4o-mini'
                }
              />
            </label>
            {provider === 'nvidia' && (
              <label>
                NVIDIA API key
                <input
                  type="password"
                  value={nvidiaKey}
                  onChange={(e) => setNvidiaKey(e.target.value)}
                  placeholder="nvapi-..."
                />
              </label>
            )}
            {provider === 'anthropic' && (
              <label>
                Anthropic API key
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder="sk-ant-..."
                />
              </label>
            )}
            {provider === 'openai' && (
              <label>
                OpenAI API key
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="sk-..."
                />
              </label>
            )}
            {!hasAnyKey && (
              <p className="setup-warning">
                Without an API key EV can only answer from local memory; chat
                responses will be unavailable.
              </p>
            )}
          </section>

          <section className="setup-section">
            <h3>3. Optional integrations</h3>
            <label>
              GitHub personal token
              <input
                type="password"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                placeholder="ghp_..."
              />
            </label>
          </section>

          <section className="setup-section">
            <h3>4. Personal-only boundary</h3>
            <p className="setup-hint">
              Comma-separated handles or domains EV must never ingest or act
              on.
            </p>
            <label>
              Blocked handles
              <input
                type="text"
                value={blockedHandles}
                onChange={(e) => setBlockedHandles(e.target.value)}
                placeholder="employerhandle, work-account"
              />
            </label>
            <label>
              Blocked domains
              <input
                type="text"
                value={blockedDomains}
                onChange={(e) => setBlockedDomains(e.target.value)}
                placeholder="employer.com, work.example"
              />
            </label>
          </section>

          <section className="setup-section">
            <h3>5. Quiet hours</h3>
            <div className="setup-row">
              <label>
                Start
                <input
                  type="time"
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                />
              </label>
              <label>
                End
                <input
                  type="time"
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                />
              </label>
            </div>
          </section>

          <div className="setup-actions">
            <button type="submit" className="setup-submit" disabled={saving || !notesPath}>
              {saving ? 'Saving…' : 'Finish setup'}
            </button>
          </div>

          {status && <p className="setup-status">{status}</p>}
        </form>
      </div>
    </div>
  )
}
