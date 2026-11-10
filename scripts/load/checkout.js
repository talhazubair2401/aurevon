// k6 load test for the busiest paths (MTS §15; M14). Run against staging only, never production:
//   k6 run -e BASE=https://staging.example -e VUS=50 -e DURATION=5m scripts/load/checkout.js
// Pass/fail thresholds below are PROVISIONAL: P-18 sets the real performance budgets after V-01 device data.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:8080";
export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || "2m",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{kind:browse}": ["p(95)<800"],
    "http_req_duration{kind:checkout}": ["p(95)<1500"],
  },
};

const json = { headers: { "Content-Type": "application/json", Accept: "application/json" } };

export default function () {
  const list = http.get(`${BASE}/api/v1/catalog/products?limit=24`, {
    tags: { kind: "browse" },
  });
  check(list, { "catalogue 200": (r) => r.status === 200 });
  const products = list.json("results") || [];
  if (!products.length) return;
  const slug = products[Math.floor(Math.random() * products.length)].slug;
  const detail = http.get(`${BASE}/api/v1/catalog/products/${slug}`, { tags: { kind: "browse" } });
  check(detail, { "product 200": (r) => r.status === 200 });
  http.get(`${BASE}/en/products/${slug}`, { tags: { kind: "browse" } });

  const avail = http.get(`${BASE}/api/v1/catalog/products/${slug}/availability`, {
    tags: { kind: "browse" },
  });
  const variant = (avail.json("variants") || []).find((v) => v.available);
  if (!variant || !variant.sku) return;
  const add = http.post(
    `${BASE}/api/v1/cart/items`,
    JSON.stringify({ sku: variant.sku, quantity: 1 }),
    {
      ...json,
      tags: { kind: "checkout" },
    },
  );
  check(add, { "added to bag": (r) => r.status === 200 || r.status === 201 });
  const csrf = http.get(`${BASE}/api/v1/cart`, { tags: { kind: "checkout" } }).json("csrf_token");
  const quote = http.post(
    `${BASE}/api/v1/checkout/quote`,
    JSON.stringify({
      address: {
        full_name: "Load Test",
        phone: "03001234567",
        line1: "1 Test St",
        area: "Test",
        city: "Karachi",
        province: "sindh",
        postal_code: "75500",
      },
    }),
    { headers: { ...json.headers, "X-CSRF-Token": csrf }, tags: { kind: "checkout" } },
  );
  check(quote, { "quote 200": (r) => r.status === 200 });
  // Orders are not placed: that would consume staging stock. Placement is covered by the e2e suite.
  sleep(1);
}
