import { useNavigate } from 'react-router-dom'
import { Card, Row, Col, Typography, Button, Steps, Space, Statistic } from 'antd'
import { UploadOutlined, RocketOutlined, DownloadOutlined, FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="home-page">
      {/* Hero Section */}
      <Card
        className="hero-card"
        style={{
          marginBottom: 24,
          textAlign: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          border: 'none',
          borderRadius: 12,
        }}
      >
        <Title level={1} style={{ color: 'white', marginBottom: 16 }}>
          毕业论文排版 Agent
        </Title>
        <Paragraph style={{ color: 'rgba(255,255,255,0.9)', fontSize: 18, marginBottom: 24 }}>
          上传论文，自动检查格式问题，一键修复，让格式不再是烦恼
        </Paragraph>
        <Button
          type="primary"
          size="large"
          icon={<UploadOutlined />}
          onClick={() => navigate('/upload')}
          style={{ borderRadius: 8 }}
        >
          开始检查
        </Button>
      </Card>

      {/* How it works */}
      <Card title="使用流程" style={{ marginBottom: 24, borderRadius: 8 }}>
        <Steps
          current={-1}
          items={[
            {
              title: '上传论文',
              description: '上传毕业论文 .docx 文件和学校格式规范',
              icon: <UploadOutlined />,
            },
            {
              title: 'AI 检查',
              description: '自动解析规范，检查论文格式问题',
              icon: <RocketOutlined />,
            },
            {
              title: '下载结果',
              description: '获取检查报告和修复后的文档',
              icon: <DownloadOutlined />,
            },
          ]}
        />
      </Card>

      {/* Features */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card hoverable style={{ borderRadius: 8, textAlign: 'center' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              <Title level={4}>智能解析</Title>
              <Text type="secondary">
                AI 自动解析学校格式规范，支持 PDF、DOCX、TXT 多种格式
              </Text>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card hoverable style={{ borderRadius: 8, textAlign: 'center' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
              <Title level={4}>全面检查</Title>
              <Text type="secondary">
                页边距、字体、字号、行距、标题层级、目录、页码、参考文献
              </Text>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card hoverable style={{ borderRadius: 8, textAlign: 'center' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <DownloadOutlined style={{ fontSize: 48, color: '#722ed1' }} />
              <Title level={4}>一键修复</Title>
              <Text type="secondary">
                自动修复格式问题，保持原文内容不变，生成修改记录
              </Text>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Stats */}
      <Card style={{ borderRadius: 8 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="支持格式维度" value={8} suffix="项" />
          </Col>
          <Col span={6}>
            <Statistic title="检查准确率" value={95} suffix="%" />
          </Col>
          <Col span={6}>
            <Statistic title="平均处理时间" value={30} suffix="秒" />
          </Col>
          <Col span={6}>
            <Statistic title="内容保护" value={100} suffix="%" />
          </Col>
        </Row>
      </Card>
    </div>
  )
}

export default HomePage
