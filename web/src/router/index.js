import { createRouter, createWebHistory } from "vue-router";

import Layout from "../views/Layout.vue";
import Datasets from "../views/Datasets.vue";
import Algorithms from "../views/Algorithms.vue";
import NewRun from "../views/NewRun.vue";
import Compare from "../views/Compare.vue";
import Runs from "../views/Runs.vue";
import Login from "../views/Login.vue";
import Register from "../views/Register.vue";

const routes = [
  { path: "/login", component: Login },
  { path: "/register", component: Register },
  {
    path: "/",
    component: Layout,
    redirect: "/datasets",
    children: [
      { path: "datasets", component: Datasets },
      { path: "algorithms", component: Algorithms },
      { path: "new-run", component: NewRun },
      { path: "compare", component: Compare },
      { path: "/runs", name: "Runs", component: Runs },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
