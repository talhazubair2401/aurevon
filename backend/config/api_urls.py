"""Routes under /api/v1/. Each module adds its own include here as it is built."""

from django.conf import settings
from django.urls import URLPattern, URLResolver, include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts.api.urls import customer_urlpatterns, staff_urlpatterns
from apps.cart.api import views as cart
from apps.catalog.api import views as catalog
from apps.cms.api import public as cms
from apps.customers.api import views as me
from apps.notifications.api import views as newsletter
from apps.orders.api import views as orders
from apps.payments.api import views as payments
from apps.returns.api import views as returns
from apps.sandbox.api.views import sandbox_pay
from apps.support.api import views as support
from common.csp_reports import csp_report
from common.views import ApiIndexView, api_not_found

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ApiIndexView.as_view(), name="api-index"),
    # Browser CSP violation reports (decision 0005). Plain Django view: not part of the OpenAPI contract.
    path("csp-reports", csp_report, name="csp-reports"),
    # Staff API: only the staff session cookie is honoured here (MTS v2.1 A-22, §9).
    path("staff/", include(staff_urlpatterns)),
    *customer_urlpatterns,
    # Public storefront reads (MTS §8): catalogue and published content.
    path("catalog/products", catalog.ProductListView.as_view(), name="catalog-products"),
    path("catalog/products/<slug:slug>", catalog.ProductDetailView.as_view(), name="catalog-product"),
    path("catalog/products/<slug:slug>/availability", catalog.AvailabilityView.as_view(), name="catalog-availability"),
    path("catalog/facets", catalog.FacetsView.as_view(), name="catalog-facets"),
    path("catalog/categories", catalog.CategoryListView.as_view(), name="catalog-categories"),
    path("catalog/collections", catalog.CollectionListView.as_view(), name="catalog-collections"),
    path("catalog/collections/<slug:slug>", catalog.CollectionDetailView.as_view(), name="catalog-collection"),
    path("cms/home", cms.HomeView.as_view(), name="cms-home"),
    path("cms/banners/<slug:key>", cms.BannerView.as_view(), name="cms-banner"),
    path("cms/pages", cms.PageListView.as_view(), name="cms-pages"),
    path("cms/pages/<slug:slug>", cms.PageView.as_view(), name="cms-page"),
    path("cms/navigation", cms.NavigationView.as_view(), name="cms-navigation"),
    path("cms/seo/<str:key>", cms.SeoView.as_view(), name="cms-seo"),
    path("cms/redirects/resolve", cms.RedirectResolveView.as_view(), name="cms-redirect-resolve"),
    path("newsletter/subscribe", newsletter.NewsletterSubscribeView.as_view(), name="newsletter-subscribe"),
    path("newsletter/confirm", newsletter.NewsletterConfirmView.as_view(), name="newsletter-confirm"),
    path("unsubscribe", newsletter.UnsubscribeView.as_view(), name="unsubscribe"),
    # Customer account (M7)
    path("me", me.MeView.as_view()),
    path("me/password", me.PasswordView.as_view()),
    path("me/preferences", me.PreferencesView.as_view()),
    path("me/addresses", me.AddressesView.as_view()),
    path("me/addresses/<uuid:address_id>", me.AddressView.as_view()),
    path("me/wishlist", me.WishlistView.as_view()),
    path("me/wishlist/<slug:slug>", me.WishlistItemView.as_view()),
    path("me/orders", orders.MyOrdersView.as_view()),
    # Cart, checkout, orders, payments (M7, M8)
    path("cart", cart.CartView.as_view()),
    path("cart/items", cart.CartItemsView.as_view()),
    path("cart/items/<uuid:item_id>", cart.CartItemView.as_view()),
    path("cart/coupon", cart.CartCouponView.as_view()),
    path("shipping/options", orders.ShippingOptionsView.as_view()),
    path("checkout/quote", orders.QuoteView.as_view()),
    path("checkout/orders", orders.PlaceOrderView.as_view()),
    path("orders/<str:number>", orders.OrderView.as_view()),
    path("orders/<str:number>/payment-attempts", payments.PaymentAttemptView.as_view()),
    path("orders/<str:number>/payment-status", payments.PaymentStatusView.as_view()),
    # Returns, exchanges and support (M12)
    path("orders/<str:number>/returns", returns.OrderReturnsView.as_view()),
    path("orders/<str:number>/returns/<str:return_number>/cancel", returns.OrderReturnCancelView.as_view()),
    path("contact", support.ContactView.as_view()),
    path("support/ticket", support.TicketByTokenView.as_view()),
    path("support/ticket/reply", support.TicketReplyView.as_view()),
    path("me/tickets", support.MyTicketsView.as_view()),
    path("webhooks/payments/<slug:provider>", payments.payment_webhook),
    # Simulated provider (sandbox only; 404 elsewhere). Not part of the API contract.
    path("sandbox/pay/<str:ref>", sandbox_pay),
]

if settings.API_SCHEMA_PUBLIC:
    urlpatterns.append(path("schema/", SpectacularAPIView.as_view(), name="api-schema"))

# Must stay last: unknown API paths always get a problem-details 404, even when DEBUG is on.
urlpatterns.append(re_path(r"^.*$", api_not_found, name="api-not-found"))
