import { spawn, spawnSync } from 'node:child_process'

const candidates = process.platform === 'win32'
  ? [
      ['python', []],
      ['py', ['-3.14']],
      ['py', ['-3.13']],
      ['py', ['-3']],
    ]
  : [
      ['python3', []],
      ['python', []],
    ]

const selected = candidates.find(([command, args]) => {
  const probe = spawnSync(command, [...args, '-c', 'from ortools.sat.python import cp_model'], {
    stdio: 'ignore',
    windowsHide: true,
  })
  return probe.status === 0
})

if (!selected) {
  console.error('No Python interpreter with Google OR-Tools was found.')
  console.error('Install it in the active environment with:')
  console.error('  python -m pip install -r requirements.txt')
  process.exit(1)
}

const [command, args] = selected
const version = spawnSync(command, [...args, '-c', 'import sys; print(sys.executable)'], {
  encoding: 'utf8',
  windowsHide: true,
})
console.log(`Using Python: ${version.stdout.trim()}`)

const server = spawn(command, [...args, 'server.py'], {
  stdio: 'inherit',
  windowsHide: true,
})

server.on('error', (error) => {
  console.error(`Could not start the V5 server: ${error.message}`)
  process.exit(1)
})

server.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal)
  process.exit(code ?? 1)
})
