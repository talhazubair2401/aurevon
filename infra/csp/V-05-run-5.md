# V-05 run 5: M5 product pages, search and images

Date: 4 November 2026 · Production builds behind the routing proxy · Policy unchanged (decision 0005)

| Check                                                                                     | Result                                                                    |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Run 4 pages plus `/en/products/relaxed-chino` and `/ur/search?q=kurta`, desktop and phone | Enforcing policy, zero violations                                         |
| Product structured data (`application/ld+json`)                                           | Carries the nonce; no violations                                          |
| Product photos from `/media/` (same origin)                                               | Allowed by `img-src 'self'`; served `public, max-age=31536000, immutable` |
| Staff product editor with image upload (staff journey)                                    | No policy errors                                                          |

Next runs: M6 (with 3D), M14, and staging/production through the CDN.
