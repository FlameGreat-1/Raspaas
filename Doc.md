Admin/
├── .gitignore
├── 4.2
├── build.sh
├── db.sqlite3
├── manage.py
├── package-copy.json
├── package-lock.json
├── package.json
├── preload.js
├── README.md
├── render.yaml
├── requirements.txt
├── webpack.config.js
├── yarn.lock
├── accounts/
│   ├── __init__.py
│   ├── admin.py
│   ├── admin_site.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── signals.py
│   ├── tests.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── migrations/
│   └── __pycache__/
├── attendance/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── services.py
│   ├── signals.py
│   ├── tasks.py
│   ├── tests.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── management/
│   ├── migrations/
│   └── __pycache__/
├── core/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   ├── views.py
│   ├── migrations/
│   ├── templatetags/
│   └── __pycache__/
├── employees/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── signal.py
│   ├── tests.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── migrations/
│   └── __pycache__/
├── payroll/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── services.py
│   ├── signals.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── migrations/
│   └── __pycache__/
├── path/
├── plugins/
├── src/
├── static/
│   └── assets/
│       ├── 29066d810a74e994be27.eot
│       ├── 39795c0b4513de014cf8.woff
│       ├── 868d1a768f4762dbcc3e.ttf
│       ├── b7bcc075b395c14ce8c2.woff2
│       ├── bb211d855a1864aa5b67.woff2
│       ├── ce82bb240fef24f93f95.woff
│       ├── df9902a6df13645438e1.svg
│       ├── chunk/
│       │   ├── app.js
│       │   ├── bootstrap.js
│       │   └── icons.js
│       ├── css/
│       │   ├── app-rtl.min.css
│       │   ├── app.min.css
│       │   ├── bootstrap-rtl.min.css
│       │   ├── bootstrap.min.css
│       │   └── icons.min.css
│       ├── images/
│       ├── js/
│       │   ├── app.js
│       │   ├── layout-setup.js
│       │   ├── plugins.js
│       │   ├── scroll-top.init.js
│       │   ├── app/
│       │   │   ├── admission-form.init.js
│       │   │   ├── apps-calendar.init.js
│       │   │   ├── apps-email.init.js
│       │   │   ├── chat.init.js
│       │   │   ├── ecommerce-cart.init.js
│       │   │   ├── ecommerce-checkout.init.js
│       │   │   ├── ecommerce-create-product.init.js
│       │   │   ├── ecommerce-order-details.init.js
│       │   │   ├── ecommerce-order.init.js
│       │   │   ├── ecommerce-product-detail.init.js
│       │   │   ├── ecommerce-product-list.init.js
│       │   │   ├── ecommerce-product.init.js
│       │   │   ├── ecommerce-wishlist.init.js
│       │   │   ├── kanban.init.js
│       │   │   ├── school-course.init.js
│       │   │   ├── school-exam.init.js
│       │   │   ├── school-parents.init.js
│       │   │   ├── students.init.js
│       │   │   ├── teachers-schedule.init.js
│       │   │   └── teachers.init.js
│       │   ├── auth/
│       │   │   ├── auth.init.js
│       │   │   ├── coming-soon.init.js
│       │   │   └── two-step-verification.init.js
│       │   ├── chart/
│       │   │   ├── apexcharts-line.init.js
│       │   │   ├── chartjs.init.js
│       │   │   └── echart.init.js
│       │   ├── dashboard/
│       │   │   ├── analytics.init.js
│       │   │   ├── e-commerce.init.js
│       │   │   ├── media.init.js
│       │   │   └── school.init.js
│       │   ├── form/
│       │   │   ├── advanced-form.init.js
│       │   │   ├── file-upload.init.js
│       │   │   ├── form-editor.init.js
│       │   │   ├── form-layout.init.js
│       │   │   ├── form-validation.init.js
│       │   │   ├── forms-select.init.js
│       │   │   └── stepper.init.js
│       │   ├── icon/
│       │   ├── map/
│       │   ├── pages/
│       │   │   ├── blog-crate.init.js
│       │   │   ├── blog-list.init.js
│       │   │   └── profile.init.js
│       │   ├── table/
│       │   │   └── datatable.init.js
│       │   └── ui/
│       │       ├── air-datepicker.init.js
│       │       ├── block-ui.init.js
│       │       ├── card.init.js
│       │       ├── countup.init.js
│       │       ├── gridjs.init.js
│       │       ├── input-masks.init.js
│       │       ├── jstree.init.js
│       │       ├── listjs.init.js
│       │       ├── modal.init.js
│       │       ├── nouislider.init.js
│       │       ├── placeholder.init.js
│       │       ├── player.init.js
│       │       ├── rating.init.js
│       │       ├── sortablejs.init.js
│       │       ├── sweetalert.init.js
│       │       ├── swiper.init.js
│       │       ├── toast.init.js
│       │       └── tour.init.js
│       └── libs/
├── templates/
│   ├── apps-calendar.html
│   ├── apps-chat.html
│   ├── apps-ecommerce-cart.html
│   ├── apps-ecommerce-checkout.html
│   ├── apps-ecommerce-create-products.html
│   ├── apps-ecommerce-customer-details.html
│   ├── apps-ecommerce-customer.html
│   ├── apps-ecommerce-order-details.html
│   ├── apps-ecommerce-order.html
│   ├── apps-ecommerce-products-details.html
│   ├── apps-ecommerce-products-list.html
│   ├── apps-ecommerce-products.html
│   ├── apps-ecommerce-wishlist.html
│   ├── apps-email.html
│   ├── apps-kanban.html
│   ├── apps-school-admission-form.html
│   ├── apps-school-courses.html
│   ├── apps-school-exam.html
│   ├── apps-school-parents.html
│   ├── apps-school-students.html
│   ├── apps-teacher-schedule.html
│   ├── apps-teacher.html
│   ├── auth-email-verify.html
│   ├── auth-forgot-password.html
│   ├── auth-reset-password.html
│   ├── auth-signin.html
│   ├── auth-signout.html
│   ├── auth-signup.html
│   ├── auth-two-step-verify.html
│   ├── chart-apex-line.html
│   ├── chart-js-chart.html
│   ├── coming-soon.html
│   ├── dashboard-analytics.html
│   ├── dashboard-media.html
│   ├── dashboard-school.html
│   ├── echart-chart.html
│   ├── error.html
│   ├── google-maps.html
│   ├── icons-bootstrap.html
│   ├── icons-remix.html
│   ├── index.html
│   ├── maps-leaflet.html
│   ├── maps-vector.html
│   ├── not-authorize.html
│   ├── pages-billing-subscription.html
│   ├── pages-blog-create.html
│   ├── pages-blog-details.html
│   ├── pages-blog-list.html
│   ├── pages-faqs.html
│   ├── pages-pricing.html
│   ├── pages-privacy-policy.html
│   ├── pages-profile.html
│   ├── pages-starter.html
│   ├── pages-terms-conditions.html
│   ├── pages-timeline.html
│   ├── ui-accordions.html
│   ├── ui-advance-swiper.html
│   ├── ui-alerts.html
│   ├── ui-avatars.html
│   ├── ui-badges.html
│   ├── ui-block.html
│   ├── ui-breadcrumbs.html
│   ├── ui-button-group.html
│   ├── ui-buttons.html
│   ├── ui-card.html
│   ├── ui-carousel.html
│   ├── ui-cookie.html
│   ├── ui-countup.html
│   ├── ui-date-picker.html
│   ├── ui-draggable-cards.html
│   ├── ui-dropdowns.html
│   ├── ui-floating-labels.html
│   ├── ui-form-advanced.html
│   ├── ui-form-checkboxs-radios.html
│   ├── ui-form-editor.html
│   ├── ui-form-elements.html
│   ├── ui-form-file-uploads.html
│   ├── ui-form-input-group.html
│   ├── ui-form-input-masks.html
│   ├── ui-form-input-spin.html
│   ├── ui-form-layout.html
│   ├── ui-form-range.html
│   ├── ui-form-select.html
│   ├── ui-form-validation.html
│   ├── ui-form-wizards.html
│   ├── ui-images-figures.html
│   ├── ui-links.html
│   ├── ui-list.html
│   ├── ui-media-player.html
│   ├── ui-modal.html
│   ├── ui-offcanvas.html
│   ├── ui-pagination.html
│   ├── ui-placeholders.html
│   ├── ui-popover.html
│   ├── ui-progress.html
│   ├── ui-ratings.html
│   ├── ui-ribbons.html
│   ├── ui-scrollspy.html
│   ├── ui-separator.html
│   ├── ui-sortable-js.html
│   ├── ui-spinner.html
│   ├── ui-sweetalert2.html
│   ├── ui-tables-basic.html
│   ├── ui-tables-datatables.html
│   ├── ui-tables-gridjs.html
│   ├── ui-tables-listjs.html
│   ├── ui-tabs.html
│   ├── ui-toast.html
│   ├── ui-tooltips.html
│   ├── ui-tour.html
│   ├── ui-treeview.html
│   ├── ui-typography.html
│   ├── ui-utilities.html
│   ├── under-maintenance.html
│   └── partials/
│       ├── auth-background.html
│       ├── auth-header.html
│       ├── body.html
│       ├── footer.html
│       ├── head-css.html
│       ├── header.html
│       ├── horizontal.html
│       ├── main.html
│       ├── pagetitle.html
│       ├── scroll-to-top.html
│       ├── sidebar.html
│       ├── switcher.html
│       ├── title-meta.html
│       ├── vendor-scripts.html
│       └── layouts/
│           ├── demo_main.html
│           ├── main.html
│           ├── main2.html
│           └── master_auth.html
├── urbix/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   ├── wsgi.py
│   └── __pycache__/
├── venv/
└── virtual_env/
