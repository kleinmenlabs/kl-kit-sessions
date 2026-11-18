import type { EngineInterface, Register } from 'claude-code'

// KL Kit Sessions status bar:
// «KL Kit Sessions: 426k tokens saved with /clear · this window: 105k · 5 windows: 380k»
// - saved: the counter the kit's hooks write (hooks/tokens_saved.py → ~/.claude/hooks/tokens_saved.json).
// - this window: the context this session weighs right now.
// - windows: every session drops its size in ~/.claude/hooks/open_sessions/<id>.json each minute;
//   the ones reported in the last 3 minutes and not closed are added up.
const ALIVE_MS = 3 * 60_000

async function hooksDir($: EngineInterface): Promise<string> {
  const config = await $.env.get('CLAUDE_CONFIG_DIR')
  if (config) return `${config.replace(/[\\/]+$/, '')}/hooks`
  const home = (await $.env.get('HOME')) || (await $.env.get('USERPROFILE')) || '~'
  return `${home.replace(/[\\/]+$/, '')}/.claude/hooks`
}

function short(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return `${n}`
}

async function saved($: EngineInterface, dir: string): Promise<number> {
  try {
    return Number(JSON.parse(await $.fs.read(`${dir}/tokens_saved.json`)).total) || 0
  } catch {
    return 0
  }
}

async function thisWindow($: EngineInterface): Promise<number> {
  try {
    return (await $.session.usage()).context.tokens ?? 0
  } catch {
    return 0
  }
}

async function openWindows($: EngineInterface, dir: string, now: number): Promise<{ count: number; sum: number }> {
  let count = 0
  let sum = 0
  let entries: { name: string; kind: string }[] = []
  try {
    entries = await $.fs.list(`${dir}/open_sessions`)
  } catch {
    return { count, sum }
  }
  for (const f of entries) {
    if (f.kind !== 'file' || !f.name.endsWith('.json')) continue
    try {
      const d = JSON.parse(await $.fs.read(`${dir}/open_sessions/${f.name}`))
      if (d.closed || now - Number(d.t) > ALIVE_MS) continue
      count += 1
      sum += Number(d.tokens) || 0
    } catch {
      // half-written file: counted on the next round
    }
  }
  return { count, sum }
}

async function paint($: EngineInterface): Promise<void> {
  const dir = await hooksDir($)
  const now = await $.clock.now()
  const mine = await thisWindow($)
  try {
    await $.fs.write(`${dir}/open_sessions/${await $.session.id()}.json`, JSON.stringify({ tokens: mine, t: now }))
  } catch {
    // if it cannot write, the bar still shows the rest
  }
  const total = await saved($, dir)
  const { count, sum } = await openWindows($, dir, now)
  $.ui.status(
    `KL Kit Sessions: ${short(total)} tokens saved with /clear · this window: ${short(mine)} · ${count} ${count === 1 ? 'window' : 'windows'}: ${short(sum)}`,
  )
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const r = await next(e)
    await paint($)
    $.clock.every(60_000, () => paint($))
    return r
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    await paint($)
    return r
  })

  // On exit or /clear the session is marked closed, so it no longer counts in "windows".
  on('session.end', async ($, e, next) => {
    try {
      const dir = await hooksDir($)
      await $.fs.write(`${dir}/open_sessions/${e.sessionId}.json`, JSON.stringify({ tokens: 0, t: await $.clock.now(), closed: true }))
    } catch {
      // nothing
    }
    return next(e)
  })
}
