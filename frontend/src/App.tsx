import Chat from './components/chat'

function App() {
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