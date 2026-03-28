import { createApp } from "vue";
import App from "./App.vue";

import router from "./router";

import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./style.css";

import { createPinia } from "pinia";

createApp(App)
  .use(router)
  .use(createPinia())
  .use(ElementPlus)
  .mount("#app");
