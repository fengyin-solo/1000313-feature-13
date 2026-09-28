<template>
  <section class="page" data-module="meter_replace">
    <header class="page-head">
      <div>
        <h2>换表记录</h2>
        <p class="page-desc">围绕表具编号、表具类型、口径规格、安装位置登记旧表止度、新表起度与换表原因；止度回退、表号冲突或施工晚于复核时先暂存核对，生效后同步水表档案与结算明细。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记换表记录</button>
        <button class="btn" type="button" @click="exportRows">导出换表清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>表号 / 安装位置</span>
        <input v-model="keyword" placeholder="按旧表、新表编号或安装位置检索" />
      </label>
      <label class="filter-item">
        <span>记录状态</span>
        <select v-model="status">
          <option value="">全部</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>状态</th>
          <th>核对提示</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-draft': row.status === '暂存' }">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span class="badge" :class="row.status === '生效' ? 'badge-ok' : 'badge-draft'">{{ row.status }}</span>
          </td>
          <td class="warn-cell">
            <ul v-if="warnings(row).length" class="warn-list">
              <li v-for="text in warnings(row)" :key="text">{{ text }}</li>
            </ul>
            <span v-else>—</span>
          </td>
          <td class="row-actions">
            <button v-if="row.status === '暂存'" class="link" type="button" @click="reviewRow(row)">复核生效</button>
            <button v-if="row.status === '暂存'" class="link" type="button" @click="openEdit(row)">编辑核对</button>
            <button v-if="row.status === '暂存'" class="link danger" type="button" @click="discardRow(row)">作废</button>
            <span v-else class="muted-text">档案与结算已采用</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 3" class="empty-state">暂无换表记录，可先登记一条换表单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条换表记录</span>
      <span v-if="message" :class="messageTone">{{ message }}</span>
    </footer>

    <div v-if="formOpen" class="modal-mask" @click.self="closeForm">
      <form class="modal-panel" @submit.prevent="submitForm">
        <h3 class="modal-title">{{ editingId === null ? '登记换表记录' : `编辑暂存记录 #${editingId}` }}</h3>
        <div class="form-grid">
          <label v-for="field in formFields" :key="field.key" class="form-item" :class="{ required: field.required }">
            <span>{{ field.label }}</span>
            <input
              v-model="formValues[field.key]"
              :type="field.type || 'text'"
              :placeholder="field.placeholder"
              :readonly="field.readonly"
            />
          </label>
        </div>
        <p class="form-tip">提示：表具类型、口径规格、安装位置可留空，登记时自动按旧表档案带出。</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeForm">取消</button>
          <button class="btn primary" type="submit">{{ editingId === null ? '提交登记' : '保存修改' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | string[] | null>

const route = useRoute()
const ENDPOINT = '/api/meter_replace'
const columns = ["旧表编号", "新表编号", "表具类型", "口径规格", "安装位置", "旧表止度", "新表起度", "上期止度", "换表原因", "施工时间", "复核时间"]
const statuses = ["暂存", "生效"]

const rows = ref<Row[]>([])
const total = ref(0)
const message = ref('')
const messageTone = ref('muted-text')
const keyword = ref(typeof route.query.keyword === 'string' ? route.query.keyword : '')
const status = ref('')

const stats = computed(() => {
  const drafts = rows.value.filter((row) => row.status === '暂存').length
  const effective = rows.value.filter((row) => row.status === '生效').length
  const abnormal = rows.value.reduce(
    (sum, row) => sum + ((row['警告'] as string[] | undefined)?.length ?? 0),
    0,
  )
  return [
    { label: '生效记录', value: effective },
    { label: '暂存待核对', value: drafts },
    { label: '待核对问题', value: abnormal },
  ]
})

function warnings(row: Row): string[] {
  return (row['警告'] as string[] | undefined) ?? []
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

// ---- 登记表单 ----------------------------------------------------------

type FormField = {
  key: string
  label: string
  required?: boolean
  type?: string
  placeholder?: string
  readonly?: boolean
}

const formFields: FormField[] = [
  { key: '旧表编号', label: '旧表编号', required: true, placeholder: '如 METE-0002' },
  { key: '新表编号', label: '新表编号', required: true, placeholder: '换装后在装表号' },
  { key: '表具类型', label: '表具类型', placeholder: '留空则按旧表档案带出' },
  { key: '口径规格', label: '口径规格', placeholder: '留空则按旧表档案带出' },
  { key: '安装位置', label: '安装位置', placeholder: '留空则按旧表档案带出' },
  { key: '旧表止度', label: '旧表止度', required: true, type: 'number', placeholder: '拆表时累计止度' },
  { key: '新表起度', label: '新表起度', required: true, type: 'number', placeholder: '新表安装时起度' },
  { key: '换表原因', label: '换表原因', required: true, placeholder: '如 周期到期轮换' },
  { key: '施工时间', label: '施工时间', required: true, type: 'datetime-local' },
  { key: '复核时间', label: '复核时间', required: true, type: 'datetime-local' },
]

const formOpen = ref(false)
const editingId = ref<number | null>(null)
const formValues = ref<Record<string, string>>({})

function openCreate() {
  editingId.value = null
  formValues.value = { 旧表止度: '', 新表起度: '0' }
  formOpen.value = true
}

function openEdit(row: Row) {
  editingId.value = Number(row.id)
  formValues.value = {}
  for (const field of formFields) {
    const raw = row[field.key]
    formValues.value[field.key] = typeof raw === 'string' ? raw : raw == null ? '' : String(raw)
  }
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
}

async function submitForm() {
  const target = editingId.value === null ? ENDPOINT : `${ENDPOINT}/${editingId.value}`
  const method = editingId.value === null ? 'POST' : 'PUT'
  try {
    const response = await request(target, {
      method,
      body: JSON.stringify({ values: formValues.value }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      messageTone.value = 'error-text'
      message.value = payload.message || '换表记录提交失败'
      return
    }
    messageTone.value = payload.entry?.status === '暂存' ? 'warn-text' : 'ok-text'
    message.value = payload.message
    formOpen.value = false
    await reload()
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '换表记录提交失败'
  }
}

async function reviewRow(row: Row) {
  await act(`/api/meter_replace/${row.id}/review`, { method: 'POST', body: JSON.stringify({}) })
}

async function discardRow(row: Row) {
  if (!window.confirm(`确认作废暂存记录 #${row.id}？作废后不可恢复。`)) {
    return
  }
  await act(`/api/meter_replace/${row.id}`, { method: 'DELETE' })
}

async function act(path: string, init: RequestInit) {
  try {
    const response = await request(path, init)
    const payload = await response.json()
    messageTone.value = payload.ok ? 'ok-text' : 'warn-text'
    message.value = payload.message
    await reload()
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '换表记录操作失败'
  }
}

async function reload() {
  message.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (status.value) query.set('status', status.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('换表记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '换表记录列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.badge-ok { background: #e7f6ec; color: #1a7f37; }
.badge-draft { background: #fdf1e3; color: #b54708; }
.row-draft { background: #fffaf2; }
.warn-cell { max-width: 260px; }
.warn-list { margin: 0; padding-left: 16px; color: #b54708; }
.warn-list li { font-size: 12px; line-height: 1.5; }
.muted-text { color: var(--muted); font-size: 12px; }
.warn-text { color: #b54708; }
.ok-text { color: #1a7f37; }
.link.danger { color: #b42318; }
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-panel {
  width: 720px;
  max-width: calc(100vw - 40px);
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
}
.modal-title { margin: 0 0 14px; font-size: 16px; }
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.form-item.required span::after { content: ' *'; color: #b42318; }
.form-item input[readonly] { background: #f1f5f9; color: var(--muted); }
.form-tip { font-size: 12px; color: var(--muted); margin: 10px 0; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
