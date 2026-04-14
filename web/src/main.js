import { createApp } from "vue";
import App from "./App.vue";

import router from "./router";

import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./style.css";

import { createPinia } from "pinia";

const isDesktop = import.meta.env.VITE_DESKTOP === "1";
document.title = isDesktop ? "算法评测平台 Desktop" : "算法评测平台 Web";

createApp(App)
  .use(router)
  .use(createPinia())
  .use(ElementPlus)
  .mount("#app");
