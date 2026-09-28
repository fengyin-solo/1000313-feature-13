<template>
  <section class="page" data-module="meter_record">
    <header class="page-head">
      <div>
        <h2>水表管理管理</h2>
        <p class="page-desc">维护贸易结算表，围绕表具编号、表具类型、口径规格、安装位置做登记、筛选与状态流转；换表后的表号与示数以生效的换表记录为准，可在「换表记录」中核对。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn primary" to="/meter_replace">登记换表记录</RouterLink>
        <button class="btn" type="button" @click="exportRows">导出水表管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无水表管理数据，可先登记贸易结算表</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条水表管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const router = useRouter()

const ENDPOINT = '/api/meter_record'
const columns = ["表具编号", "表具类型", "口径规格", "安装位置", "上次示数", "当前示数", "生效换表单", "抄表员", "表具状态"]
const actions = ["现场抄表", "换表登记", "恢复供电"]
const statuses = ["正常", "待换表", "停走", "倒转", "缺电"]
const stats = [{"label": "正常表具", "value": 0}, {"label": "异常表具", "value": 0}, {"label": "待换表具", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (action === '换表登记') {
    // 换表以换表单为准，引导到换表记录页登记并带上表号
    void router.push({ path: '/meter_replace', query: { keyword: String(row['表具编号'] ?? '') } })
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('水表管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '水表管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('贸易结算表列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '水表管理列表读取失败'
  }
}

onMounted(reload)
</script>
