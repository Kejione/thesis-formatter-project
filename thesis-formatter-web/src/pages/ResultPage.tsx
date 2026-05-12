import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Row, Col, Progress, Typography, Table, Tag, Button, Space, Statistic, Spin, Alert, Result } from 'antd'
import { CheckCircleOutlined, WarningOutlined, InfoCircleOutlined, DownloadOutlined, EyeOutlined, LoadingOutlined } from '@ant-design/icons'
import { useTaskPolling } from '@/hooks/useTaskPolling'
import { getTaskReport, fixTask } from '@/services/taskApi'
import type { TaskReport, Issue } from '@/types'

const { Title, Text } = Typography

const severityColors: Record<string, string> = {
  error: 'red',
  warning: 'orange',
  info: 'blue',
}

const severityIcons: Record<string, React.ReactNode> = {
  error: <WarningOutlined style={{ color: '#ff4d4f' }} />,
  warning: <WarningOutlined style={{ color: '#faad14' }} />,
  info: <InfoCircleOutlined style={{ color: '#1890ff' }} />,
}

const severityLabels: Record<string, string> = {
  error: '错误',
  warning: '警告',
  info: '提示',
}

const categoryLabels: Record<string, string> = {
  margin: '页边距',
  font: '字体',
  font_size: '字号',
  spacing: '间距',
  line_spacing: '行距',
  paragraph_spacing: '段间距',
  heading: '标题',
  heading_style: '标题样式',
  page_num: '页码',
  page_number: '页码',
  ref: '参考文献',
  references: '参考文献',
  toc: '目录',
  table: '表格',
  figure: '图片',
}

function formatLocation(issue: Issue): string {
  const loc = issue.location
  const parts: string[] = []
  if (loc.section) parts.push(`第${loc.section}节`)
  if (loc.page) parts.push(`第${loc.page}页`)
  if (loc.paragraph) parts.push(`第${loc.paragraph}段`)
  return parts.length > 0 ? parts.join('，') : '-'
}

function ResultPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<TaskReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [fixLoading, setFixLoading] = useState(false)

  const { taskStatus, isPolling, error: pollingError } = useTaskPolling(taskId ?? null)

  // 当任务完成时获取完整报告
  useEffect(() => {
    if (taskStatus?.status === 'completed' && !report) {
      async function fetchReport() {
        setReportLoading(true)
        try {
          const data = await getTaskReport(taskId!)
          setReport(data)
        } catch {
          // 报告获取失败，不影响页面展示
        } finally {
          setReportLoading(false)
        }
      }
      fetchReport()
    }
  }, [taskStatus?.status, report, taskId])

  const handleFix = async () => {
    if (!taskId) return
    setFixLoading(true)
    try {
      await fixTask(taskId)
      navigate(`/download/${taskId}`)
    } catch {
      // fixTask 失败时仍尝试跳转
      navigate(`/download/${taskId}`)
    } finally {
      setFixLoading(false)
    }
  }

  const handlePreview = () => {
    if (taskId) {
      navigate(`/preview/${taskId}`)
    }
  }

  const columns = [
    {
      title: '严重程度',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (severity: string) => (
        <Tag color={severityColors[severity]} icon={severityIcons[severity]}>
          {severityLabels[severity] ?? severity}
        </Tag>
      ),
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (category: string) => categoryLabels[category] ?? category,
    },
    {
      title: '位置',
      key: 'location',
      width: 120,
      render: (_: unknown, record: Issue) => formatLocation(record),
    },
    {
      title: '当前值',
      dataIndex: 'current_value',
      key: 'current_value',
      ellipsis: true,
    },
    {
      title: '期望值',
      dataIndex: 'expected_value',
      key: 'expected_value',
      ellipsis: true,
    },
    {
      title: '修复建议',
      dataIndex: 'suggestion',
      key: 'suggestion',
      ellipsis: true,
    },
  ]

  // 轮询中 / 处理中状态
  if (isPolling || taskStatus?.status === 'pending' || taskStatus?.status === 'processing') {
    return (
      <div className="result-page" style={{ textAlign: 'center', padding: '80px 0' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
        <Title level={3} style={{ marginTop: 24 }}>
          正在检查论文格式...
        </Title>
        <Text type="secondary">请稍候，AI 正在分析您的论文并对照格式规范进行检查</Text>
        {taskStatus && (
          <div style={{ maxWidth: 400, margin: '24px auto 0' }}>
            <Progress
              percent={taskStatus.status === 'processing' ? 60 : 20}
              status="active"
              strokeColor={{ from: '#667eea', to: '#764ba2' }}
            />
          </div>
        )}
      </div>
    )
  }

  // 修复中状态
  if (taskStatus?.status === 'fixing') {
    return (
      <div className="result-page" style={{ textAlign: 'center', padding: '80px 0' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
        <Title level={3} style={{ marginTop: 24 }}>
          正在修复格式问题...
        </Title>
        <Text type="secondary">请稍候，系统正在自动修复已检测到的格式问题</Text>
        <div style={{ maxWidth: 400, margin: '24px auto 0' }}>
          <Progress percent={80} status="active" strokeColor="#52c41a" />
        </div>
      </div>
    )
  }

  // 任务失败
  if (taskStatus?.status === 'failed' || pollingError) {
    return (
      <div className="result-page">
        <Result
          status="error"
          title="任务执行失败"
          subTitle={pollingError ?? taskStatus?.error_message ?? '任务执行过程中出现错误，请重试'}
          extra={[
            <Button key="retry" type="primary" onClick={() => navigate('/upload')}>
              重新上传
            </Button>,
            <Button key="home" onClick={() => navigate('/')}>
              返回首页
            </Button>,
          ]}
        />
      </div>
    )
  }

  // 已修复状态
  if (taskStatus?.status === 'fixed') {
    return (
      <div className="result-page">
        <Result
          status="success"
          title="格式修复完成"
          subTitle="论文格式问题已全部修复，请下载修复后的文档"
          extra={[
            <Button
              key="download"
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => navigate(`/download/${taskId}`)}
            >
              前往下载
            </Button>,
            <Button key="preview" icon={<EyeOutlined />} onClick={handlePreview}>
              预览文档
            </Button>,
          ]}
        />
      </div>
    )
  }

  // 已完成但报告未加载
  if (!report) {
    return (
      <div className="result-page" style={{ textAlign: 'center', padding: '80px 0' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
        <Title level={3} style={{ marginTop: 24 }}>
          正在加载检查报告...
        </Title>
      </div>
    )
  }

  const { summary, issues } = report

  return (
    <div className="result-page">
      <Title level={2}>检查结果</Title>
      <Text type="secondary">任务 ID: {taskId}</Text>

      {/* Summary */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="总体评分"
              value={summary.score ?? 0}
              suffix="分"
              valueStyle={{ color: (summary.score ?? 0) >= 80 ? '#52c41a' : (summary.score ?? 0) >= 60 ? '#faad14' : '#ff4d4f' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="错误"
              value={summary.error_count}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<WarningOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="警告"
              value={summary.warning_count}
              valueStyle={{ color: '#faad14' }}
              prefix={<WarningOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="提示"
              value={summary.info_count}
              valueStyle={{ color: '#1890ff' }}
              prefix={<InfoCircleOutlined />}
            />
          </Col>
        </Row>
      </Card>

      {/* Progress */}
      <Card title="检查进度" style={{ marginBottom: 24 }}>
        <Progress percent={100} status="success" />
        <Text type="secondary">已完成所有格式检查，共发现 {summary.total_issues} 个问题</Text>
      </Card>

      {/* Issues Table */}
      <Card
        title="格式问题列表"
        extra={
          <Space>
            <Button icon={<EyeOutlined />} onClick={handlePreview}>
              预览文档
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={fixLoading}
              onClick={handleFix}
            >
              一键修复
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={issues}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          loading={reportLoading}
        />
      </Card>
    </div>
  )
}

export default ResultPage
