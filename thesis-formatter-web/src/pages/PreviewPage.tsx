import { useParams } from 'react-router-dom'
import { Card, Typography, Alert, Button, Space } from 'antd'
import { DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

function PreviewPage() {
  const { taskId } = useParams()

  return (
    <div className="preview-page">
      <Title level={2}>文档预览</Title>
      <Text type="secondary">任务 ID: {taskId}</Text>

      <Alert
        message="预览功能开发中"
        description="文档在线预览功能正在开发中，敬请期待。目前您可以在检查结果页面下载修复后的文档。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Card style={{ marginBottom: 24, textAlign: 'center', minHeight: 400 }}>
        <div style={{ padding: 100 }}>
          <Title level={3} type="secondary">
            📄 文档预览区域
          </Title>
          <Paragraph type="secondary">
            这里将显示修复后的文档预览，支持：
          </Paragraph>
          <ul style={{ textAlign: 'left', display: 'inline-block' }}>
            <li>在线预览 Word 文档内容</li>
            <li>高亮显示修改位置</li>
            <li>逐条查看格式修改</li>
            <li>对比修改前后效果</li>
          </ul>
        </div>
      </Card>

      <div style={{ textAlign: 'center' }}>
        <Space size="large">
          <Button icon={<ArrowLeftOutlined />}>返回结果</Button>
          <Button type="primary" icon={<DownloadOutlined />}>
            下载文档
          </Button>
        </Space>
      </div>
    </div>
  )
}

export default PreviewPage
