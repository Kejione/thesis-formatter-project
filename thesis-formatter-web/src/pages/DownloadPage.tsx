import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Row, Col, Typography, Button, Space, List, Tag, Spin, message, Empty } from 'antd'
import { DownloadOutlined, FileWordOutlined, FileMarkdownOutlined, FilePdfOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { getChangelog, downloadFixedDoc } from '@/services/taskApi'
import type { ChangeLog } from '@/types'

const { Title, Text, Paragraph } = Typography

const riskColors: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
}

const riskLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

function formatChangeLocation(loc: ChangeLog['changes'][number]['location']): string {
  const parts: string[] = []
  if (loc.section) parts.push(`第${loc.section}节`)
  if (loc.page) parts.push(`第${loc.page}页`)
  if (loc.paragraph) parts.push(`第${loc.paragraph}段`)
  return parts.length > 0 ? parts.join('，') : '-'
}

function DownloadPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [changelog, setChangelog] = useState<ChangeLog | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloadLoading, setDownloadLoading] = useState(false)

  useEffect(() => {
    if (!taskId) return

    async function fetchData() {
      setLoading(true)
      try {
        const data = await getChangelog(taskId!)
        setChangelog(data)
      } catch {
        message.error('获取修改记录失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [taskId])

  const handleDownload = async () => {
    if (!taskId) return
    setDownloadLoading(true)
    try {
      const url = await downloadFixedDoc(taskId)
      window.open(url, '_blank')
    } catch {
      message.error('获取下载链接失败，请稍后重试')
    } finally {
      setDownloadLoading(false)
    }
  }

  return (
    <div className="download-page">
      <Title level={2}>下载中心</Title>
      <Text type="secondary">任务 ID: {taskId}</Text>

      {/* Download Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card hoverable style={{ textAlign: 'center' }}>
            <FileWordOutlined style={{ fontSize: 48, color: '#2b579a', marginBottom: 16 }} />
            <Title level={4}>修复版文档</Title>
            <Paragraph type="secondary">
              已修复格式问题的 Word 文档
            </Paragraph>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              block
              loading={downloadLoading}
              onClick={handleDownload}
            >
              下载 .docx
            </Button>
          </Card>
        </Col>
        <Col span={8}>
          <Card hoverable style={{ textAlign: 'center' }}>
            <FileMarkdownOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
            <Title level={4}>修改记录</Title>
            <Paragraph type="secondary">
              所有格式修改的详细记录
            </Paragraph>
            <Button icon={<DownloadOutlined />} block disabled>
              下载 .md
            </Button>
          </Card>
        </Col>
        <Col span={8}>
          <Card hoverable style={{ textAlign: 'center' }}>
            <FilePdfOutlined style={{ fontSize: 48, color: '#ff4d4f', marginBottom: 16 }} />
            <Title level={4}>检查报告</Title>
            <Paragraph type="secondary">
              完整的格式检查报告
            </Paragraph>
            <Button icon={<DownloadOutlined />} block disabled>
              下载 .pdf
            </Button>
          </Card>
        </Col>
      </Row>

      {/* Change Log */}
      <Card
        title="修改记录"
        extra={
          loading ? null : (
            <Tag color="green">共 {changelog?.total_changes ?? 0} 处修改</Tag>
          )
        }
      >
        <Spin spinning={loading}>
          {!loading && (!changelog || changelog.changes.length === 0) ? (
            <Empty description="暂无修改记录" />
          ) : (
            <List
              itemLayout="horizontal"
              dataSource={changelog?.changes ?? []}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />}
                    title={
                      <Space>
                        <Text strong>{item.category}</Text>
                        <Tag color={riskColors[item.risk_level]}>
                          {riskLabels[item.risk_level] ?? item.risk_level}
                        </Tag>
                      </Space>
                    }
                    description={
                      <div>
                        <Text type="secondary">位置：{formatChangeLocation(item.location)}</Text>
                        <br />
                        <Text delete type="danger">{item.before_value}</Text>
                        <Text> → </Text>
                        <Text type="success">{item.after_value}</Text>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </Card>
    </div>
  )
}

export default DownloadPage
