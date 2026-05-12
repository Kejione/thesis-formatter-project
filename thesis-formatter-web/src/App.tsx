import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import HomePage from './pages/HomePage'
import UploadPage from './pages/UploadPage'
import ResultPage from './pages/ResultPage'
import PreviewPage from './pages/PreviewPage'
import DownloadPage from './pages/DownloadPage'
import AppHeader from './components/AppHeader'
import './App.css'

const { Content, Footer } = Layout

function App() {
  return (
    <BrowserRouter>
      <Layout className="app-layout">
        <AppHeader />
        <Content className="app-content">
          <div className="content-wrapper">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/result/:taskId" element={<ResultPage />} />
              <Route path="/preview/:taskId" element={<PreviewPage />} />
              <Route path="/download/:taskId" element={<DownloadPage />} />
            </Routes>
          </div>
        </Content>
        <Footer className="app-footer">
          毕业论文排版 Agent ©{new Date().getFullYear()} - 让论文格式不再是烦恼
        </Footer>
      </Layout>
    </BrowserRouter>
  )
}

export default App
