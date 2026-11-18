import { expect, test } from 'claude-code/testing'

const NOW = 1_000_000_000

test('shows tokens saved, this window and the open windows, under the user folder', async ($, on) => {
  const seen: unknown[] = []
  const paths: string[] = []
  const written: Record<string, string> = {}
  const files: Record<string, string> = {
    'tokens_saved.json': JSON.stringify({ total: 1234567 }),
    'other.json': JSON.stringify({ tokens: 200_000, t: NOW - 60_000 }),
    'old.json': JSON.stringify({ tokens: 900_000, t: NOW - 10 * 60_000 }),
    'closed.json': JSON.stringify({ tokens: 0, t: NOW, closed: true }),
  }
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/home/someone' : undefined }))
  on('clock.now', () => ({ value: NOW }))
  on('session.id', () => ({ value: 'mine' }))
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 105_000, window: 200_000 }, rateLimits: [] } }))
  on('fs.write', (_, e) => {
    paths.push(e.path)
    written[e.path.split(/[\\/]/).pop()!] = e.text
    return { value: undefined }
  })
  on('fs.list', () => ({
    value: ['other.json', 'old.json', 'closed.json', ...Object.keys(written)].map(name => ({ name, kind: 'file', size: 1, mtimeMs: 0, isLink: false })),
  }))
  on('fs.read', (_, e) => {
    paths.push(e.path)
    const name = e.path.split(/[\\/]/).pop()!
    const t = written[name] ?? files[name]
    if (t === undefined) throw new Error('missing: ' + e.path)
    return { value: t }
  })
  on('ui.status', (_, e) => { seen.push(e); return { value: undefined } })
  on('clock.every', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'vscode', isInteractive: true })
  expect(JSON.stringify(seen)).toContain('KL Kit Sessions: 1.2M tokens saved with /clear · this window: 105k · 2 windows: 305k')
  // the engine may normalize the path for the OS (C:\home\someone\... on Windows)
  expect(paths.map(p => p.replace(/\\/g, '/').replace(/^[A-Za-z]:/, ''))).toContain('/home/someone/.claude/hooks/tokens_saved.json')
})

test('with nothing yet it says 0', async ($, on) => {
  const seen: unknown[] = []
  on('env.get', () => ({ value: undefined }))
  on('clock.now', () => ({ value: NOW }))
  on('session.id', () => ({ value: 'mine' }))
  on('session.usage', () => ({ value: { startedAt: 0, context: { window: 200_000 }, rateLimits: [] } }))
  on('fs.write', () => { throw new Error('no permission') })
  on('fs.list', () => { throw new Error('missing') })
  on('fs.read', () => { throw new Error('missing') })
  on('ui.status', (_, e) => { seen.push(e); return { value: undefined } })
  on('clock.every', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(JSON.stringify(seen)).toContain('KL Kit Sessions: 0 tokens saved with /clear · this window: 0 · 0 windows: 0')
})
