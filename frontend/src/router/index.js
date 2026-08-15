import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/layout/index.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '可视化大屏', icon: 'DataAnalysis' }
      },
      {
        path: 'ai-chat',
        name: 'AIChat',
        component: () => import('@/views/ai-chat/index.vue'),
        meta: { title: 'AI智能探索舱', icon: 'ChatDotRound' }
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('@/views/analytics/index.vue'),
        meta: { title: '多维数据穿透分析', icon: 'DataBoard' }
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('@/views/reports/index.vue'),
        meta: { title: '自动化洞察报告', icon: 'Document' }
      },
      {
        path: 'reports/:id',
        name: 'ReportPreview',
        component: () => import('@/views/reports/preview.vue'),
        meta: { title: '报告预览', hidden: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智慧医疗分析平台`
  }
  next()
})

export default router
