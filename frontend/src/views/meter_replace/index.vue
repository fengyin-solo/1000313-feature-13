<template>
  <section class="page" data-module="meter_replace">
    <header class="page-head">
      <div>
        <h2>换表记录</h2>
        <p class="page-desc">围绕表具编号、表具类型、口径规格、安装位置登记旧表止度、新表起度与换表原因；止度回退、表号冲突或施工晚于复核时仅暂存并提示核对。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记换表</button>
        <button class="btn" type="button" @click="exportRows">导出换表清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <template v-if="activeTab === 'records'">
      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>表号检索</span>
          <input v-model="keyword" placeholder="按换表编号/旧表号/新表号检索" />
        </label>
        <label class="filter-item">
          <span>状态</span>
          <select v-model="statusFilter">
            <option value="">全部</option>
            <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td>{{ row['换表编号'] ?? '—' }}</td>
            <td>{{ row['旧表编号'] ?? '—' }}</td>
            <td>{{ row['新表编号'] ?? '—' }}</td>
            <td>{{ row['表具类型'] ?? '—' }}</td>
            <td>{{ row['口径规格'] ?? '—' }}</td>
            <td>{{ row['安装位置'] ?? '—' }}</td>
            <td>{{ formatValue(row['旧表止度']) }}</td>
            <td>{{ formatValue(row['新表起度']) }}</td>
            <td>{{ row['换表原因'] ?? '—' }}</td>
            <td>{{ row['施工时间'] ?? '—' }}</td>
            <td>{{ row['复核时间'] ?? '—' }}</td>
            <td>{{ row['施工人员'] ?? '—' }}</td>
            <td>
              <span class="badge" :class="row.status === '生效' ? 'ok' : 'warn'">{{ row.status }}</span>
            </td>
            <td>
              <ul v-if="warningsOf(row).length" class="warn-list" :title="warningsOf(row).join('；')">
                <li v-for="(w, i) in warningsOf(row)" :key="i">{{ w }}</li>
              </ul>
              <span v-else class="muted-text">核对通过</span>
            </td>
            <td class="row-actions">
              <button v-if="row.status === '暂存'" class="link" type="button" @click="openEdit(row)">核对修改</button>
              <button v-if="row.status === '暂存'" class="link" type="button" @click="promote(row)">核对生效</button>
              <span v-else class="muted-text">已联动档案</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无换表记录，可先登记一条换表</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条换表记录</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
        <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      </footer>
    </template>

    <template v-else>
      <p class="page-desc" style="margin: 8px 0">
        结算明细只读取生效换表记录，与换表页、水表档案共用同一条生效记录；暂存记录核对通过前不参与结算。
      </p>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in settlementColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in settlements" :key="String(row['换表编号']) + idx">
            <td v-for="column in settlementColumns" :key="column">{{ formatValue(row[column]) }}</td>
          </tr>
          <tr v-if="!settlements.length">
            <td :colspan="settlementColumns.length" class="empty-state">暂无生效换表记录，结算明细为空</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ settlements.length }} 条结算明细（仅生效记录）</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <div v-if="formOpen" class="modal-mask" @click.self="closeForm">
      <form class="modal-card" @submit.prevent="submitForm">
        <div class="modal-head">
          <h3>{{ editingId ? '核对修改暂存记录' : '登记换表' }}</h3>
          <button class="btn ghost" type="button" @click="closeForm">关闭</button>
        </div>
        <div v-if="formWarnings.length" class="warn-box">
          <p class="warn-title">以下核对项未通过，记录将仅暂存，请核对后再生效：</p>
          <ul>
            <li v-for="(w, i) in formWarnings" :key="i">{{ w }}</li>
          </ul>
        </div>
        <div class="form-grid">
          <label class="form-item">
            <span>旧表编号 *</span>
            <input v-model="form.旧表编号" list="meter-options" placeholder="选择在装表具" required @change="prefillFromMeter" />
          </label>
          <label class="form-item">
            <span>新表编号 *</span>
            <input v-model="form.新表编号" required placeholder="新表具出厂编号" />
          </label>
          <label class="form-item">
            <span>表具类型</span>
            <input v-model="form.表具类型" placeholder="默认取档案旧表" />
          </label>
          <label class="form-item">
            <span>口径规格</span>
            <input v-model="form.口径规格" placeholder="默认取档案旧表" />
          </label>
          <label class="form-item span-2">
            <span>安装位置</span>
            <input v-model="form.安装位置" placeholder="默认取档案旧表" />
          </label>
          <label class="form-item">
            <span>旧表止度 *</span>
            <input v-model="form.旧表止度" type="number" min="0" step="0.01" required placeholder="旧表拆除时读数" />
          </label>
          <label class="form-item">
            <span>新表起度 *</span>
            <input v-model="form.新表起度" type="number" min="0" step="0.01" required placeholder="新表安装时读数" />
          </label>
          <label class="form-item span-2">
            <span>换表原因 *</span>
            <input v-model="form.换表原因" required placeholder="如：到期轮换、计量异常、表体损坏" />
          </label>
          <label class="form-item">
            <span>施工时间 *</span>
            <input v-model="form.施工时间" type="datetime-local" required />
          </label>
          <label class="form-item">
            <span>复核时间 *</span>
            <input v-model="form.复核时间" type="datetime-local" required />
          </label>
          <label class="form-item span-2">
            <span>施工人员 *</span>
            <input v-model="form.施工人员" required placeholder="现场换表/复核人员" />
          </label>
        </div>
        <datalist id="meter-options">
          <option v-for="m in meters" :key="String(m.id)" :value="String(m['表具编号'] ?? '')" />
        </datalist>
        <p v-if="formError" class="error-text form-foot-msg">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeForm">取消</button>
          <button class="btn primary" type="submit">{{ editingId ? '保存并重新核对' : '提交登记' }}</button>
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
type FormState = Record<string, string>

const ENDPOINT = '/api/meter_replace'
const METER_ENDPOINT = '/api/meter_record'

const columns = ['换表编号', '旧表编号', '新表编号', '表具类型', '口径规格', '安装位置', '旧表止度', '新表起度', '换表原因', '施工时间', '复核时间', '施工人员', '状态', '核对提示']
const settlementColumns = ['换表编号', '表具编号', '表具类型', '口径规格', '安装位置', '旧表编号', '旧表止度', '新表起度', '换表期用量', '换表原因', '施工时间', '复核时间']
const statuses = ['暂存', '生效']
const tabs = [
  { key: 'records', label: '换表记录' },
  { key: 'settlements', label: '结算明细' },
] as const

const route = useRoute()
const activeTab = ref<'records' | 'settlements'>('records')
const rows = ref<Row[]>([])
const settlements = ref<Row[]>([])
const meters = ref<Row[]>([])
const total = ref(0)
const draftCount = ref(0)
const effectiveCount = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const formOpen = ref(false)
const editingId = ref<number | null>(null)
const formWarnings = ref<string[]>([])
const formError = ref('')
const emptyForm: FormState = {
  旧表编号: '',
  新表编号: '',
  表具类型: '',
  口径规格: '',
  安装位置: '',
  旧表止度: '',
  新表起度: '',
  换表原因: '',
  施工时间: '',
  复核时间: '',
  施工人员: '',
}
const form = ref<FormState>({ ...emptyForm })

const stats = computed(() => [
  { label: '换表记录总数', value: total.value },
  { label: '待核对暂存', value: draftCount.value },
  { label: '已生效', value: effectiveCount.value },
  { label: '结算明细', value: settlements.value.length },
])

function warningsOf(row: Row): string[] {
  const value = row['核对提示']
  return Array.isArray(value) ? value : []
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function switchTab(key: 'records' | 'settlements') {
  activeTab.value = key
  errorMessage.value = ''
  if (key === 'settlements') {
    void reloadSettlements()
  } else {
    void reload()
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function prefillFromMeter() {
  const meter = meters.value.find((m) => String(m['表具编号'] ?? '') === form.value.旧表编号)
  if (!meter) return
  for (const field of ['表具类型', '口径规格', '安装位置']) {
    if (!form.value[field]) form.value[field] = String(meter[field] ?? '')
  }
}

function openCreate() {
  editingId.value = null
  form.value = { ...emptyForm }
  const presetOld = typeof route.query.oldMeter === 'string' ? route.query.oldMeter : ''
  if (presetOld) {
    form.value.旧表编号 = presetOld
    prefillFromMeter()
  }
  formWarnings.value = []
  formError.value = ''
  formOpen.value = true
}

function openEdit(row: Row) {
  editingId.value = Number(row.id)
  form.value = {
    ...emptyForm,
    ...Object.fromEntries(
      ['旧表编号', '新表编号', '表具类型', '口径规格', '安装位置', '旧表止度', '新表起度', '换表原因', '施工时间', '复核时间', '施工人员'].map((f) => [
        f,
        row[f] === null || row[f] === undefined ? '' : String(row[f]).replace(' ', 'T'),
      ]),
    ),
  }
  formWarnings.value = warningsOf(row)
  formError.value = ''
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
}

async function submitForm() {
  formError.value = ''
  const payload: FormState = { ...form.value }
  try {
    const url = editingId.value ? `${ENDPOINT}/${editingId.value}` : ENDPOINT
    const response = await request(url, {
      method: editingId.value ? 'PUT' : 'POST',
      body: JSON.stringify({ values: payload }),
    })
    const result = await response.json()
    if (!result.ok) {
      formError.value = result.message ?? '提交失败'
      return
    }
    formWarnings.value = result.entry?.['核对提示'] ?? []
    noticeMessage.value = result.message ?? '已提交'
    formOpen.value = false
    await Promise.all([reload(), reloadMeters()])
    if (activeTab.value === 'settlements') await reloadSettlements()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '换表记录提交失败'
  }
}

async function promote(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '核对生效' } }),
    })
    const result = await response.json()
    if (!result.ok) {
      noticeMessage.value = ''
      errorMessage.value = result.message ?? '核对未通过'
    } else {
      noticeMessage.value = result.message ?? '已生效'
    }
    await Promise.all([reload(), reloadMeters(), reloadSettlements()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '核对生效失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('换表记录列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const [draftPage, effectivePage] = await Promise.all([
      request(`${ENDPOINT}?status=暂存&size=1`).then((r) => r.json()),
      request(`${ENDPOINT}?status=生效&size=1`).then((r) => r.json()),
    ])
    draftCount.value = draftPage.total ?? 0
    effectiveCount.value = effectivePage.total ?? 0
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '换表记录列表读取失败'
  }
}

async function reloadSettlements() {
  try {
    const response = await request(`${ENDPOINT}/settlements`)
    if (!response.ok) throw new Error('结算明细读取失败')
    const payload = await response.json()
    settlements.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '结算明细读取失败'
  }
}

async function reloadMeters() {
  try {
    const response = await request(`${METER_ENDPOINT}?page=1&size=200`)
    if (!response.ok) return
    const payload = await response.json()
    meters.value = payload.items ?? []
  } catch {
    // 档案只用于选表辅助，读取失败不阻塞换表录入
  }
}

onMounted(() => {
  const focusNo = typeof route.query.focus === 'string' ? route.query.focus : ''
  if (focusNo) {
    keyword.value = focusNo
    activeTab.value = 'records'
  }
  void reload()
  void reloadSettlements()
  void reloadMeters()
  if (route.query.oldMeter) openCreate()
})
</script>
