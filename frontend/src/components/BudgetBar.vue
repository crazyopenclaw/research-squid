<template>
  <div class="budget-bar">
    <div class="budget-item">
      <span class="label">Budget</span>
      <div class="bar">
        <div class="fill" :style="{ width: pct + '%', background: color }"></div>
      </div>
      <span class="value">${{ totalSpent.toFixed(2) }} / ${{ totalBudget.toFixed(2) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ budget: { type: Object, default: () => ({}) } })
const totalSpent = computed(() =>
  Number(props.budget.spent ?? 0)
  || (Number(props.budget.llm_spent ?? 0) + Number(props.budget.compute_spent ?? 0))
)
const totalBudget = computed(() =>
  Number(props.budget.total ?? 0)
  || Number(props.budget.budget ?? 0)
  || Number(props.budget.llm_budget ?? 0) + Number(props.budget.compute_budget ?? 0)
)
const pct = computed(() => totalBudget.value ? (totalSpent.value / totalBudget.value) * 100 : 0)
const color = computed(() => pct.value > 90 ? '#d32f2f' : pct.value > 70 ? '#f57c00' : '#111')
</script>

<style scoped>
.budget-bar { display: flex; gap: 16px; }
.budget-item { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.label { text-transform: uppercase; color: #666; width: 55px; }
.bar { width: 80px; height: 6px; background: #eee; }
.fill { height: 100%; transition: width 0.5s; }
.value { font-size: 10px; color: #666; white-space: nowrap; }
</style>
