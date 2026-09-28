<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "管段档案", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡查记录", "created": 0, "pending": 0, "abnormal": 0}, {"name": "病害管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "CCTV检测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "阀门管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护计划", "created": 0, "pending": 0, "abnormal": 0}, {"name": "应急抢修", "created": 0, "pending": 0, "abnormal": 0}, {"name": "开挖审批", "created": 0, "pending": 0, "abnormal": 0}, {"name": "井盖管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "排水清疏", "created": 0, "pending": 0, "abnormal": 0}, {"name": "气体监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "漏水检测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "水表管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "换表记录", "created": 0, "pending": 0, "abnormal": 0}, {"name": "贸易结算", "created": 0, "pending": 0, "abnormal": 0}, {"name": "消防栓管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "管沟巡检", "created": 0, "pending": 0, "abnormal": 0}, {"name": "占道施工", "created": 0, "pending": 0, "abnormal": 0}, {"name": "回填修复", "created": 0, "pending": 0, "abnormal": 0}, {"name": "防腐检测", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
