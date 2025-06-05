import ChatBox from './components/ChatBox'

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      width: '100vw',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#fff',
      padding: window.innerWidth <= 400 ? '10px' : '0'
    }}>
      <ChatBox />
    </div>
  )
}

export default App
