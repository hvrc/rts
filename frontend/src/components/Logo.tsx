const Logo = () => {
  const bubbleStyle = {
    width: '30px',
    height: '30px',
    borderRadius: '50%',
    backgroundColor: '#FFAC1C',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    margin: '0 2px'
  };

  const textStyle = {
    marginTop: '-2px'
  };

  const containerStyle = {
    display: 'flex',
    justifyContent: 'center',
    width: '100%',
    padding: '8px 0 16px 0',
    marginLeft: '30px'
  };

  return (
    <div style={containerStyle}>
      <div style={bubbleStyle}><span style={textStyle}>r</span></div>
      <div style={bubbleStyle}><span style={textStyle}>t</span></div>
      <div style={bubbleStyle}><span style={textStyle}>s</span></div>
    </div>
  );
};

export default Logo;