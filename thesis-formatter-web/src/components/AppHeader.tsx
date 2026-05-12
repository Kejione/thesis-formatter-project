import { Layout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { FileTextOutlined, UploadOutlined, SettingOutlined } from '@ant-design/icons'

const { Header } = Layout

function AppHeader() {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: '/',
      icon: <FileTextOutlined />,
      label: '工作台',
    },
    {
      key: '/upload',
      icon: <UploadOutlined />,
      label: '上传论文',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ]

  return (
    <Header className="app-header" style={{ display: 'flex', alignItems: 'center' }}>
      <div className="logo" style={{ color: 'white', fontSize: '18px', fontWeight: 'bold', marginRight: '40px' }}>
        📄 论文排版 Agent
      </div>
      <Menu
        theme="dark"
        mode="horizontal"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  )
}

export default AppHeader
