<template>
  <section class="page" data-module="meter_record">
    <header class="page-head">
      <div>
        <h2>水表档案</h2>
        <p class="page-desc">维护贸易结算表档案，围绕表具编号、表具类型、口径规格、安装位置做登记、筛选与状态流转；换表生效后档案与换表记录、结算明细同步更新。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn primary" type="button" to="/meter_replace">换表记录</RouterLink>
        <button class="btn" type="button" @click="exportRows">导出水表档案清单</button>
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
      <label class="filter-item">
        <span>表具状态</span>
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
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '最近换表'">
              <RouterLink v-if="row['最近换表']" class="link" :to="`/meter_replace?focus=${row['最近换表']}`">
                {{ row['最近换表'] }}
              </RouterLink>
              <span v-else class="muted-text">—</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
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
            <RouterLink class="link" :to="`/meter_replace?oldMeter=${encodeURIComponent(String(row['表具编号'] ?? ''))}`">发起换表</RouterLink>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无水表档案数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条水表档案记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/meter_record'
const columns = ["表具编号", "表具类型", "口径规格", "安装位置", "上次示数", "当前示数", "抄表员", "表具状态", "最近换表"]
const actions = ["现场抄表", "恢复供电"]
const statuses = ["正常", "待换表", "停走", "倒转", "缺电"]
const stats = [{"label": "正常表具", "value": 0}, {"label": "异常表具", "value": 0}, {"label": "待换表具", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('水表档案动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '水表档案操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('水表档案列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '水表档案列表读取失败'
  }
}

onMounted(reload)
</script>
