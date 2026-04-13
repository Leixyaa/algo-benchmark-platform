import { createRouter, createWebHashHistory, createWebHistory } from "vue-router";
import { ElMessage } from "element-plus";

import Layout from "../views/LayoutBrand2.vue";
import Community from "../views/Community.vue";
import Datasets from "../views/Datasets.vue";
import Algorithms from "../views/Algorithms.vue";
import AlgorithmAccess from "../views/AlgorithmAccess.vue";
import Metrics from "../views/Metrics.vue";
import NewRun from "../views/NewRun.vue";
import Compare from "../views/Compare.vue";
import Runs from "../views/Runs.vue";
import Notices from "../views/Notices.vue";
import Login from "../views/LoginBrand.vue";
import Register from "../views/RegisterBrand.vue";
import AdminLogin from "../views/AdminLoginBrand.vue";
import Admin from "../views/Admin.vue";

const routes = [
  { path: "/login", component: Login },
  { path: "/admin-login", component: AdminLogin },
  { path: "/register", component: Register },
  {
    path: "/",
    component: Layout,
    redirect: "/community",
    children: [
      { path: "community", component: Community },
      { path: "datasets", component: Datasets },
      { path: "algorithms", component: Algorithms },
      { path: "algorithm-access", component: AlgorithmAccess },
      { path: "metrics", component: Metrics },
      { path: "new-run", component: NewRun },
      { path: "compare", component: Compare },
      { path: "runs", name: "Runs", component: Runs },
      { path: "notices", component: Notices },
      { path: "admin", component: Admin },
    ],
  },
];

const isDesktop = import.meta.env.VITE_DESKTOP === "1";

const router = createRouter({
  history: isDesktop ? createWebHashHistory() : createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  if (to.path !== "/admin") {
    next();
    return;
  }

  const role =
    sessionStorage.getItem("userRole") ||
    localStorage.getItem("userRole") ||
    "user";

  if (role === "admin") {
    next();
    return;
  }

  ElMessage.warning("权限不足，普通用户不能进入管理后台");
  next(from.path && from.path !== "/admin" ? from.fullPath : "/community");
});

export default router;
