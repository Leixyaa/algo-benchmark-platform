import { createRouter, createWebHistory } from "vue-router";

import Layout from "../views/Layout.vue";
import Datasets from "../views/Datasets.vue";
import Algorithms from "../views/Algorithms.vue";
import NewRun from "../views/NewRun.vue";
import Tasks from "../views/Tasks.vue";
import Compare from "../views/Compare.vue";
import Runs from "../views/Runs.vue";

const routes = [
  {
    path: "/",
    component: Layout,
    redirect: "/datasets",
    children: [
      { path: "datasets", component: Datasets },
      { path: "algorithms", component: Algorithms },
      { path: "new-run", component: NewRun },
      { path: "tasks", component: Runs },
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
