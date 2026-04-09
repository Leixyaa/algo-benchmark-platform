import { createRouter, createWebHistory } from "vue-router";

import Layout from "../views/LayoutBrand2.vue";
import Community from "../views/Community.vue";
import Datasets from "../views/Datasets.vue";
import Algorithms from "../views/Algorithms.vue";
import NewRun from "../views/NewRun.vue";
import Compare from "../views/Compare.vue";
import Runs from "../views/Runs.vue";
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
      { path: "new-run", component: NewRun },
      { path: "compare", component: Compare },
      { path: "runs", name: "Runs", component: Runs },
      { path: "admin", component: Admin },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
