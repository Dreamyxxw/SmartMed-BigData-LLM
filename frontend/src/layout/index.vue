<template>
  <div class="layout-container">
    <!-- 左侧导航栏 -->
    <aside class="sidebar" :class="{ 'sidebar--collapsed': globalStore.sidebarCollapsed }">
      <div class="sidebar__logo">
        <div class="logo-wrap">
          <svg class="logo-icon" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#40a9ff;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#1890ff;stop-opacity:1" />
              </linearGradient>
            </defs>
            <circle cx="50" cy="50" r="42" fill="url(#logoGrad)"/>
            <path d="M50 28 L50 72 M28 50 L72 50" stroke="white" stroke-width="7" stroke-linecap="round"/>
          </svg>
        </div>
        <transition name="slide-fade" mode="out-in">
          <span v-if="!globalStore.sidebarCollapsed" key="text" class="logo-text">智慧医疗分析平台</span>
        </transition>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="globalStore.sidebarCollapsed"
        :collapse-transition="false"
        class="sidebar__menu"
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#ffffff"
        router
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- 右侧主区域 -->
    <div class="main-wrapper">
      <!-- 顶部状态栏 -->
      <header class="header">
        <div class="header__left">
          <el-tooltip :content="globalStore.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" placement="bottom">
            <el-button text class="sidebar-toggle-btn" @click="globalStore.toggleSidebar()">
              <el-icon :size="20">
                <Expand v-if="globalStore.sidebarCollapsed" />
                <Fold v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
          <el-divider direction="vertical" class="header-divider header-divider--left" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header__right">
          <!-- 全局筛选器 -->
          <div class="global-filters">
            <span class="filter-label">
              <el-icon><Filter /></el-icon>
              全局筛选
            </span>
            <el-select
              v-model="globalStore.selectedYear"
              size="default"
              style="width: 120px"
              placeholder="选择年份"
              @change="onFilterChange"
            >
              <el-option
                v-for="opt in globalStore.yearOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-select
              v-model="globalStore.selectedRegion"
              size="default"
              style="width: 180px"
              placeholder="选择区域"
              @change="onFilterChange"
            >
              <el-option
                v-for="opt in globalStore.regionOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>

          <el-divider direction="vertical" class="header-divider" />

          <!-- 全屏按钮 -->
          <el-tooltip content="全屏" placement="bottom">
            <el-button text @click="toggleFullscreen">
              <el-icon :size="18"><FullScreen /></el-icon>
            </el-button>
          </el-tooltip>

          <!-- 通知 -->
          <el-tooltip content="通知" placement="bottom">
            <el-badge :value="3" :max="9" class="notification-badge">
              <el-button text>
                <el-icon :size="18"><Bell /></el-icon>
              </el-button>
            </el-badge>
          </el-tooltip>

          <el-divider direction="vertical" class="header-divider" />

          <!-- 用户头像 -->
          <el-dropdown>
            <div class="user-info">
              <el-avatar :size="36" class="user-avatar">
                <el-icon><UserFilled /></el-icon>
              </el-avatar>
              <span class="user-name">管理员</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalStore } from '@/stores/global'

const route = useRoute()
const globalStore = useGlobalStore()

const menuItems = computed(() => {
  return [
    { path: '/dashboard', title: '可视化大屏', icon: 'DataAnalysis' },
    { path: '/ai-chat', title: 'AI智能探索舱', icon: 'ChatDotRound' },
    { path: '/analytics', title: '多维数据穿透分析', icon: 'DataBoard' },
    { path: '/reports', title: '自动化洞察报告', icon: 'Document' }
  ]
})

const activeMenu = computed(() => route.path)
const currentPageTitle = computed(() => route.meta.title || '')

const onFilterChange = () => {
  // 全局筛选变更后刷新当前页面数据 - 通过监听store变化在各页面处理
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    ElMessage.success('已退出登录')
  }).catch(() => {})
}
</script>

<style lang="scss" scoped>
.layout-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

// ========== 侧边栏 ==========
.sidebar {
  width: $sidebar-width;
  background: $bg-dark-sidebar;
  display: flex;
  flex-direction: column;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;

  &--collapsed {
    width: $sidebar-width-collapsed;
  }

  &__logo {
    height: $header-height;
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    transition: padding 0.28s cubic-bezier(0.4, 0, 0.2, 1), gap 0.2s;
    flex-shrink: 0;

    .logo-wrap {
      width: 36px;
      height: 36px;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .logo-icon {
      width: 32px;
      height: 32px;
      display: block;
    }

    .logo-text {
      color: #fff;
      font-size: 15px;
      font-weight: 600;
      white-space: nowrap;
      letter-spacing: 0.3px;
      line-height: 1;
    }
  }

  &--collapsed &__logo {
    padding: 0;
    gap: 0;
    justify-content: center;
  }

  &__menu {
    flex: 1;
    border-right: none !important;
    padding: 10px 0;
    background: transparent !important;

    :deep(.el-menu-item) {
      margin: 3px 10px;
      border-radius: $radius-sm;
      height: 44px;
      line-height: 44px;
      transition: background-color 0.2s, color 0.2s, margin 0.2s, border-radius 0.2s;
      overflow: hidden;

      &:hover {
        background-color: $bg-dark-sidebar-hover !important;
        color: #fff !important;
      }

      &.is-active {
        color: #fff !important;
        background-color: $primary-color !important;
        box-shadow: 0 2px 8px rgba(24, 144, 255, 0.28);
        position: relative;
      }

      .el-icon {
        font-size: 18px;
      }
    }
  }

  // 收缩态：菜单项变成正方形图标按钮
  &--collapsed &__menu {
    :deep(.el-menu-item) {
      margin: 4px auto;
      width: calc(#{$sidebar-width-collapsed} - 16px);
      height: 44px;
      border-radius: $radius-sm;
      padding: 0 !important;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;

      .el-icon {
        margin: 0 !important;
      }
    }
  }
}

// Logo文字过渡
.slide-fade-enter-active {
  transition: all 0.25s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(-6px);
  opacity: 0;
}

// ========== 主区域 ==========
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

// ========== 顶部 Header ==========
.header {
  height: $header-height;
  background: $bg-header;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  z-index: 10;

  &__left {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.sidebar-toggle-btn {
  width: 40px;
  height: 40px;
  border-radius: $radius-md;
  color: $text-regular;
  transition: all 0.2s;

  &:hover {
    background: $bg-page;
    color: $primary-color;
  }

  .el-icon {
    transition: transform 0.25s ease;
  }
}

.header-divider {
  margin: 0 4px;
  height: 22px;

  &--left {
    margin: 0 8px;
  }
}

// ========== 全局筛选器 ==========
.global-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 12px;
  background: $primary-bg;
  border-radius: $radius-md;
  margin: 0 4px;
  transition: all 0.2s;

  &:hover {
    background: rgba(24, 144, 255, 0.12);
  }

  .filter-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: $primary-dark;
    font-weight: 500;
    white-space: nowrap;
  }
}

.notification-badge {
  :deep(.el-badge__content) {
    top: 4px;
    right: 4px;
    font-size: 10px;
    min-width: 16px;
    height: 16px;
    line-height: 16px;
    padding: 0 4px;
  }
}

// ========== 用户信息 ==========
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 10px 4px 4px;
  border-radius: $radius-md;
  cursor: pointer;
  transition: background 0.2s;
  margin-left: 4px;

  &:hover {
    background: $bg-page;
  }

  .user-avatar {
    background: $gradient-primary;
    font-size: 16px;
  }

  .user-name {
    font-size: 14px;
    color: $text-regular;
    font-weight: 500;
  }
}

// ========== 主内容区 ==========
.main-content {
  flex: 1;
  overflow: auto;
  padding: $spacing-lg;
  background: $bg-page;
}

// ========== 路由过渡动画 ==========
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
