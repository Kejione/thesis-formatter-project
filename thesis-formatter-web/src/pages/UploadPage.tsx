import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Upload, Button, Select, Form, message, Space, Typography, Divider, Alert, Spin } from 'antd'
import { InboxOutlined, FileTextOutlined, ThunderboltOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { createTask } from '@/services/taskApi'
import { listTemplates } from '@/services/ruleApi'
import { listModels } from '@/services/modelApi'
import type { Template, ModelConfig } from '@/types'

const { Dragger } = Upload
const { Title, Text, Paragraph } = Typography

function UploadPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [thesisFile, setThesisFile] = useState<File | null>(null)
  const [specFile, setSpecFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [initLoading, setInitLoading] = useState(false)
  const [templates, setTemplates] = useState<Template[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])

  // 页面挂载时获取模板和模型列表
  useEffect(() => {
    async function fetchOptions() {
      setInitLoading(true)
      try {
        const [templateList, modelList] = await Promise.all([
          listTemplates(),
          listModels(),
        ])
        setTemplates(templateList)
        setModels(modelList)
      } catch {
        message.warning('获取模板或模型列表失败，您仍可手动上传文件')
      } finally {
        setInitLoading(false)
      }
    }
    fetchOptions()
  }, [])

  const thesisUploadProps = {
    accept: '.docx',
    maxCount: 1,
    beforeUpload: (file: File) => {
      setThesisFile(file)
      return false
    },
    onRemove: () => setThesisFile(null),
  }

  const specUploadProps = {
    accept: '.pdf,.docx,.doc,.txt',
    maxCount: 1,
    beforeUpload: (file: File) => {
      setSpecFile(file)
      return false
    },
    onRemove: () => setSpecFile(null),
  }

  const handleSubmit = async () => {
    if (!thesisFile) {
      message.error('请上传毕业论文文件')
      return
    }

    const values = form.getFieldsValue()
    setLoading(true)

    try {
      const task = await createTask(
        thesisFile,
        specFile ?? undefined,
        values.template_id,
        values.model_id,
      )
      message.success('任务创建成功，正在检查格式...')
      navigate(`/result/${task.id}`)
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ?? error?.message ?? '创建任务失败，请重试'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const thesisTypeLabels: Record<string, string> = {
    bachelor: '本科',
    master: '硕士',
    doctor: '博士',
  }

  return (
    <div className="upload-page">
      <Title level={2}>上传论文</Title>
      <Paragraph type="secondary">
        上传您的毕业论文和学校格式规范文件，系统将自动检查格式问题
      </Paragraph>

      {initLoading && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin tip="正在加载配置..." />
        </div>
      )}

      <Form form={form} layout="vertical">
        <Card title="📄 毕业论文" style={{ marginBottom: 24 }}>
          <Dragger {...thesisUploadProps} fileList={thesisFile ? [thesisFile as unknown as UploadFile] : []}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              仅支持 .docx 格式，文件大小不超过 50MB
            </p>
          </Dragger>
        </Card>

        <Card title="📋 格式规范文件（可选）" style={{ marginBottom: 24 }}>
          <Alert
            message="提示"
            description="您可以上传学校提供的格式规范文件（PDF/DOCX/TXT），系统将自动解析。如不上传，可选择预置模板或手动配置规则。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Dragger {...specUploadProps} fileList={specFile ? [specFile as unknown as UploadFile] : []}>
            <p className="ant-upload-drag-icon">
              <FileTextOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持 PDF、DOCX、DOC、TXT 格式
            </p>
          </Dragger>
        </Card>

        <Card title="⚙️ 检查配置" style={{ marginBottom: 24 }}>
          <Form.Item label="学校模板" name="template_id">
            <Select
              placeholder="选择预置的学校模板（可选）"
              allowClear
              loading={initLoading}
              options={templates.map((t) => ({
                value: t.id,
                label: `${t.school_name}（${thesisTypeLabels[t.thesis_type] ?? t.thesis_type}）`,
              }))}
            />
          </Form.Item>

          <Form.Item label="AI 模型" name="model_id">
            <Select
              placeholder="选择 AI 模型（默认使用系统配置）"
              allowClear
              loading={initLoading}
              options={models.map((m) => ({
                value: m.id,
                label: m.is_default ? `${m.name}（推荐）` : m.name,
              }))}
            />
          </Form.Item>
        </Card>

        <div style={{ textAlign: 'center' }}>
          <Space size="large">
            <Button size="large" onClick={() => navigate('/')}>
              返回
            </Button>
            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              loading={loading}
              onClick={handleSubmit}
            >
              开始检查
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  )
}

export default UploadPage
