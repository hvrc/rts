import Chat from './components/Chat'

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      width: '100vw',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#fff',
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