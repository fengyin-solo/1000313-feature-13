<template>
  <section class="page" data-module="meter_settlement">
    <header class="page-head">
      <div>
        <h2>贸易结算明细</h2>
        <p class="page-desc">结算用量由生效的换表记录自动派生：旧表止度减去上期止度，与换表页、水表档案共用同一生效记录；暂存记录不参与结算。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出结算清单</button>
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
        <span>表号 / 位置 / 结算编号</span>
        <input v-model="keyword" placeholder="按旧表、新表编号、安装位置或结算编号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetKeyword">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-warn': row['核对说明'] }">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '结算用量'">
              <span :class="row['核对说明'] ? 'warn-text' : ''">{{ formatQuantity(row[column]) }}</span>
            </template>
            <template v-else-if="column === '生效换表单'">#{{ row[column] }}</template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无结算明细，换表记录生效后会自动出现在这里</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条结算明细（仅统计生效换表记录）</span>
      <span v-if="message" class="error-text">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/meter_settlement'
const columns = ["结算编号", "生效换表单", "表具类型", "口径规格", "安装位置", "旧表编号", "新表编号", "在装表号", "上期止度", "旧表止度", "结算用量", "换表原因", "施工时间", "复核时间", "核对说明"]

const rows = ref<Row[]>([])
const total = ref(0)
const message = ref('')
const keyword = ref('')

const stats = computed(() => {
  const totalQuantity = rows.value.reduce((sum, row) => {
    const value = Number(row['结算用量'])
    return sum + (Number.isFinite(value) && value > 0 ? value : 0)
  }, 0)
  const toCheck = rows.value.filter((row) => row['核对说明']).length
  return [
    { label: '结算单数', value: rows.value.length },
    { label: '累计结算用量', value: totalQuantity },
    { label: '待核对明细', value: toCheck },
  ]
})

function formatQuantity(value: Row[string]) {
  if (value === null || value === undefined || value === '') return '—'
  return value
}

function resetKeyword() {
  keyword.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  message.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('结算明细读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    message.value = error instanceof Error ? error.message : '结算明细读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.row-warn { background: #fffaf2; }
.warn-text { color: #b54708; font-weight: 600; }
</style>
