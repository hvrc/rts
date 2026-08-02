import Chat from './components/chat'
import RawDatabase from './components/RawDatabase'
import { current } from './lib/route'

/* The backend base URL, injected at build time so the backend can move hosts without
   a code change. Same default the chat uses. */
const API_URL = import.meta.env.VITE_API_URL
  ?? (import.meta.env.PROD
    ? 'https://backend-dot-rts0-462101.ue.r.appspot.com'
    : 'http://localhost:5001')

function App() {
  /* /database is a file, not a screen, so it replaces the app rather than opening
     inside it - no window, no wallpaper, nothing to scroll it off.

     Read once at load rather than followed reactively: nothing in the app links here,
     you arrive by typing the URL, and you leave the same way. */
  if (current().at === 'database') {
    return <RawDatabase api={API_URL} />
  }

  return (
    <div style={{
      minHeight: '100vh',
      width: '100vw',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      // Transparent, not `var(--bg)`. This div covers the whole viewport, so an
      // opaque fill here sits on top of the wallpaper on body::before and hides
      // it completely. The window paints its own surface; the shell only centers.
      backgroundColor: 'transparent',
      padding: window.innerWidth <= 400 ? '10px' : '0',
      overflow: 'hidden',
      position: 'fixed',
      top: 0,
      left: 0
    }}>
      <Chat />
    </div>
  )
}

export default App
