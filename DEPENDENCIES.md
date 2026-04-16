# OIUEEI Feature Dependency Map

This document maps every feature to its full dependency chain across the codebase. Its purpose is to make **pruning safe**: when user testing reveals which features matter, this map tells you exactly what to remove (and what to keep) for each one.

**Last updated:** 2026-04-16

---

## How to Read This Document

Each feature section lists every file and component that would need to be removed (or modified) if that feature were deleted. Dependencies marked with **(shared)** are used by multiple features — removing the feature does not mean removing that dependency.

---

## Core Platform (cannot be removed)

These are foundational — every feature depends on them.

| Layer | Files |
|-------|-------|
| **Models** | `core/models/user.py`, `core/models/theeeme.py` |
| **Views** | `core/views/auth.py` (RequestLink, VerifyLink, PopIn, Me, Logout, TokenRefresh), `core/views/users.py`, `core/views/theeemes.py`, `core/views/upload.py` |
| **Serializers** | `core/serializers/auth.py`, `core/serializers/user.py`, `core/serializers/theeeme.py` |
| **Services** | `core/services/email_service.py` — `send_magic_link_email()` |
| **Utilities** | `core/utils.py`, `core/validators.py`, `core/permissions.py`, `core/pagination.py` |
| **URLs** | `config/urls.py`, `core/urls.py` (auth, user, theeeme, upload, health routes) |
| **Management** | `core/management/commands/cleanup_rsvps.py` |
| **Migrations** | `0001`–`0005`, `0006`, `0010`, `0013`, `0020`, `0024`–`0032`, `0034`–`0036`, `0042`–`0046` |
| **Tests** | `core/tests/conftest.py` **(shared)**, `core/tests/unit/test_models.py` (User, Theeeme sections), `core/tests/unit/test_security.py`, `core/tests/unit/test_validators.py` |
| **Frontend pages** | `LoginPage`, `VerifyPage`, `LogoutPage`, `HomePage`, `UserPage`, `EditProfilePage`, `WelcomePage`, `PopInPage`, `NotFoundPage` |
| **Frontend components** | `BackLink`, `Toast`, `LoadingSpinner`, `TheeemeSelector`, `KoroSelector`, `ImageUpload` |
| **Frontend services** | `src/services/api.js`, `src/services/analytics.js` |
| **Frontend config** | `App.jsx`, `src/i18n/`, `src/constants/things.js` **(shared)**, `vite.config.js` |

---

## Feature: Collections

Allows users to create lists of things and share them with others via email invites.

| Layer | Files | Detail |
|-------|-------|--------|
| **Model** | `core/models/collection.py` | Collection model with owner FK, things M2M, invites M2M, is_onboarding flag |
| **Views** | `core/views/collections.py` | CollectionViewSet (CRUD), CollectionInviteView (POST/DELETE), InvitedCollectionsView, MyPendingInvitationsView |
| **Serializers** | `core/serializers/collection.py` | CollectionSerializer, CollectionCreateSerializer, CollectionUpdateSerializer, CollectionInviteSerializer, CollectionAddThingSerializer, CollectionRemoveThingSerializer, CollectionRemoveInviteSerializer, CollectionInviteSummarySerializer, CollectionThingSummarySerializer |
| **Services** | `core/services/email_service.py` | `send_collection_invite_email()`, `send_invite_rejected_email()`, `send_collection_revoke_email()` |
| **Permissions** | `core/permissions.py` | `IsCollectionOwner` |
| **RSVP actions** | `core/views/auth.py` | `_handle_collection_invite()`, `_handle_collection_reject()` in VerifyLinkView |
| **RSVP model** | `core/models/rsvp.py` | Actions: `COLLECTION_INVITE`, `COLLECTION_REJECT` |
| **URLs** | `core/urls.py` | `collections/` (router), `invited-collections/`, `my-invitations/`, `collections/<code>/invite/` |
| **Migrations** | `0001` (initial), `0006`, `0010`, `0011`, `0014`, `0017`–`0019`, `0038`, `0040`, `0048`–`0050` |
| **Tests** | `core/tests/unit/test_models.py` (Collection), `core/tests/unit/test_serializers.py` (Collection), `core/tests/integration/test_views.py` (collection endpoints), `core/tests/scenarios/test_user_flows.py` |
| **Frontend pages** | `CollectionPage`, `CreateCollectionPage`, `EditCollectionPage`, `ManageInvitesPage`, `RemoveGuestPage` |
| **Frontend (HomePage)** | `HomePage` — fetches and displays `my-invitations/` pending invites |
| **Frontend (UserPage)** | `UserPage` — "My collections", "Shared with me" sections |
| **Depends on** | Core Platform, Things (M2M) |
| **Depended on by** | Things (visibility via `can_view`), Bookings (inactive collection check), FAQs (visibility) |

### Pruning difficulty: **IMPOSSIBLE** — Collections are the backbone of sharing. Removing them breaks thing visibility, invites, and the entire sharing model.

---

## Feature: Things

Items that can be gifted, sold, lent, rented, shared, or ordered.

| Layer | Files | Detail |
|-------|-------|--------|
| **Model** | `core/models/thing.py` | Thing model with owner FK, type, status, fee, availability, location, condition, deal M2M |
| **Views** | `core/views/things.py` | ThingViewSet (CRUD + activate/hide), InvitedThingsView |
| **Serializers** | `core/serializers/thing.py` | ThingSerializer, ThingCreateSerializer, ThingUpdateSerializer |
| **Permissions** | `core/permissions.py` | `IsThingOwner` |
| **URLs** | `core/urls.py` | `things/` (router), `invited-things/` |
| **Migrations** | `0001`, `0007`–`0008`, `0011`–`0012`, `0017`–`0018`, `0023`, `0033`, `0039`, `0042`–`0043`, `0051` |
| **Tests** | `core/tests/unit/test_models.py` (Thing), `core/tests/unit/test_serializers.py` (Thing), `core/tests/integration/test_views.py` (thing endpoints) |
| **Frontend pages** | `ThingPage`, `AddThingPage`, `EditThingPage`, `DeleteThingPage` |
| **Frontend components** | `ThingLinkbox`, `ThingTags` |
| **Frontend constants** | `src/constants/things.js` — TYPE_VALUES, DATE_TYPES, ORDER_TYPE, FEE_TYPES, DETAIL_TYPES, AVAILABILITY_VALUES, CONDITION_VALUES, TAG_THEMES |
| **Depends on** | Core Platform, Collections (M2M, visibility) |
| **Depended on by** | Bookings, FAQs |

### Thing Types (sub-features)

Each thing type can potentially be pruned independently:

| Type | Booking behaviour | Extra fields | Removable independently? |
|------|------------------|--------------|--------------------------|
| `GIFT_THING` | Single-use, no dates | availability, location, condition | Yes — remove from choices, constants, serializer logic |
| `SELL_THING` | Single-use, no dates | fee, availability, location, condition | Yes |
| `LEND_THING` | Date-based, stays ACTIVE | availability, location, condition | Yes |
| `RENT_THING` | Date-based, stays ACTIVE | fee, availability, location, condition | Yes |
| `SHARE_THING` | Date-based, stays ACTIVE | availability, location, condition | Yes |
| `ORDER_THING` | Repeatable, delivery_date + quantity | fee, delivery_date, quantity | Yes |

**To remove a type:** update `Thing.THING_TYPES` choices, `BookingPeriod` category lists (`DATE_BASED_TYPES`, `SINGLE_USE_TYPES`, `REPEATABLE_TYPES`), frontend `constants/things.js`, i18n keys, and serializer conditional logic.

### Pruning difficulty: **IMPOSSIBLE** — Things are the core entity. But individual *types* can be pruned (MEDIUM difficulty).

---

## Feature: Bookings (Reservations)

Allows invited users to request, and owners to accept/reject, holds on things.

| Layer | Files | Detail |
|-------|-------|--------|
| **Model** | `core/models/booking.py` | BookingPeriod with thing FK, requester FK, owner FK, status, dates, quantity |
| **Views** | `core/views/reservations.py` | ThingRequestView (creates bookings) |
| **Views** | `core/views/booking.py` | ThingCalendarView, MyBookingsView, OwnerBookingsView, BookingCancelView, BookingActionView |
| **Serializers** | `core/serializers/booking.py` | BookingPeriodSerializer, BookingPeriodCalendarSerializer, BookingPeriodOwnerCalendarSerializer, ThingRequestWithDatesSerializer, ThingOrderSerializer, MyBookingSerializer |
| **Services** | `core/services/booking_service.py` | `accept_booking()`, `reject_booking()`, `cancel_booking()` |
| **Services** | `core/services/email_service.py` | `send_booking_request_email()`, `send_booking_confirmation_email()`, `send_booking_decision_email()` |
| **RSVP actions** | `core/views/auth.py` | `_handle_booking_accept()`, `_handle_booking_reject()` in VerifyLinkView |
| **RSVP model** | `core/models/rsvp.py` | Actions: `BOOKING_ACCEPT`, `BOOKING_REJECT`. Method: `create_for_booking()` |
| **Thing model** | `core/models/thing.py` | `status` (TAKEN state), `deal` M2M, `reserve()`, `release()` methods |
| **Management** | `core/management/commands/expire_bookings.py` | Batch expire stale PENDING bookings |
| **URLs** | `core/urls.py` | `things/<code>/request/`, `things/<code>/calendar/`, `my-bookings/`, `owner-bookings/`, `bookings/<code>/accept/`, `bookings/<code>/reject/`, `bookings/<code>/cancel/` |
| **Migrations** | `0007`, `0009`, `0015`–`0016`, `0017`, `0021`–`0022` |
| **Tests** | `core/tests/integration/test_booking.py`, `core/tests/unit/test_models.py` (BookingPeriod), `core/tests/unit/test_commands.py` |
| **Frontend pages** | `RequestThingPage`, `MyBookingsPage` |
| **Frontend (ThingLinkbox)** | Owner button matrix (Confirm/Cancel hold), guest reservation button, calendar fetch |
| **Frontend (ThingPage)** | Owner bookings display, reservation flow |
| **Frontend (HomePage)** | "My requests" button linking to `/my-bookings` |
| **Frontend (ThingSerializer)** | `pending_booking`, `my_pending_booking` fields |
| **Depends on** | Core Platform, Things, Collections (inactive check) |
| **Depended on by** | Nothing (leaf feature) |

### Pruning difficulty: **MEDIUM** — Bookings are a leaf feature. Removing them simplifies Thing (remove TAKEN status, deal M2M, reserve/release methods), cleans up ThingLinkbox and ThingPage button logic significantly, removes 3 email functions, and drops the expire_bookings command. The RSVP model keeps its other actions.

---

## Feature: FAQs

Allows invited users to ask questions about things, and owners to answer or hide them.

| Layer | Files | Detail |
|-------|-------|--------|
| **Model** | `core/models/faq.py` | FAQ with thing FK, questioner FK, question, answer, is_visible |
| **Views** | `core/views/faq.py` | ThingFAQListView (GET/POST), FAQDetailView, FAQAnswerView, FAQVisibilityView |
| **Serializers** | `core/serializers/faq.py` | FAQSerializer, FAQCreateSerializer, FAQAnswerSerializer |
| **Services** | `core/services/email_service.py` | `send_faq_question_email()`, `send_faq_answer_email()`, `send_faq_hide_email()` |
| **URLs** | `core/urls.py` | `things/<code>/faq/`, `faq/<code>/`, `faq/<code>/answer/`, `faq/<code>/hide/`, `faq/<code>/show/` |
| **Migrations** | `0001` (initial), `0041` (demo FAQs) |
| **Tests** | `core/tests/unit/test_models.py` (FAQ), `core/tests/integration/test_views.py` (FAQ endpoints) |
| **Frontend (ThingPage)** | FAQs section — list, ask, answer, hide/show |
| **Frontend (ThingLinkbox)** | `pending_questions` tag (owner only) |
| **Frontend (ThingSerializer)** | `faqs`, `pending_questions` fields |
| **Depends on** | Core Platform, Things |
| **Depended on by** | Nothing (leaf feature) |

### Pruning difficulty: **EASY** — FAQs are fully independent. Remove the model, views, serializers, 3 email functions, URL routes, and the FAQ section from ThingPage/ThingLinkbox. Remove `pending_questions` from ThingSerializer and CollectionThingSummarySerializer.

---

## ~~Feature: Philips Hue Easter Egg~~ (REMOVED)

Removed on 2026-04-16. Was a standalone easter egg with no dependencies. Deleted `core/views/hue.py` and 4 URL routes from `core/urls.py`.

---

## Feature: Mixpanel Analytics

Client-side event tracking via Mixpanel.

| Layer | Files | Detail |
|-------|-------|--------|
| **Frontend** | `src/services/analytics.js` | `initAnalytics()`, `identifyUser()`, `track()`, `resetAnalytics()` |
| **Frontend (App.jsx)** | `PageViewTracker` component, `initAnalytics()` call |
| **Frontend (HomePage)** | `identifyUser()` call |
| **Frontend (LogoutPage)** | `resetAnalytics()` call |
| **Env vars** | — | `VITE_MIXPANEL_TOKEN` |
| **npm deps** | `package.json` | `mixpanel-browser` |
| **Depends on** | Nothing (fully standalone) |
| **Depended on by** | Nothing |

### Pruning difficulty: **TRIVIAL** — Delete `analytics.js`, remove imports and calls from `App.jsx`, `HomePage`, `LogoutPage`. Remove `mixpanel-browser` from `package.json`.

---

## Feature: Cloudinary Image Upload

Direct browser-to-Cloudinary uploads with signed URLs.

| Layer | Files | Detail |
|-------|-------|--------|
| **Views** | `core/views/upload.py` | CloudinarySignatureView |
| **URLs** | `core/urls.py` | `upload/signature/` |
| **Utilities** | `core/utils.py` | `cloudinary_url()` function |
| **Frontend** | `src/components/ImageUpload.jsx` | FileInput + Cloudinary upload + preview |
| **Frontend pages** | `AddThingPage`, `EditThingPage` | `ImageUpload` usage for thing thumbnails |
| **Model fields** | `Thing.thumbnail` | CharField(255) storing Cloudinary public_id |
| **Serializers** | `core/serializers/thing.py` | `ImageIdField` for thumbnail, `thumbnail_url` SerializerMethodField |
| **Validators** | `core/validators.py` | `ImageIdField`, `validate_image_id()` |
| **Env vars** | — | `CLOUDINARY_CLOUD_NAME` |
| **pip deps** | `requirements/` | `cloudinary` |
| **Depends on** | Core Platform |
| **Depended on by** | Thing thumbnails display (ThingLinkbox, ThingPage, CollectionPage) |

### Pruning difficulty: **EASY** — Remove upload view, `ImageUpload` component, `ImageIdField`, `cloudinary_url()`. Remove `thumbnail` field from Thing model (migration needed). Remove `thumbnail_url` from serializers. Images in ThingLinkbox/ThingPage fall back to placeholder.

---

## Feature: Internationalisation (i18n)

Multi-language support via react-i18next.

| Layer | Files | Detail |
|-------|-------|--------|
| **Frontend** | `src/i18n/index.js` | i18next setup with browser language detection |
| **Frontend** | `src/i18n/locales/*.json` | 7 language files (en, es, ca, pt-BR, pt-PT, eu, gl) |
| **Frontend (App.jsx)** | `import './i18n'`, `html[lang]` update |
| **Frontend (all pages)** | Every page uses `useTranslation()` and `t()` calls |
| **Frontend tests** | `src/test/i18n-mock.js`, `src/test/setup.js` |
| **npm deps** | `package.json` | `i18next`, `react-i18next`, `i18next-browser-languagedetector` |
| **Depends on** | Nothing |
| **Depended on by** | Every frontend page and component |

### Pruning difficulty: **HARD** — i18n is woven into every component. Removing it means replacing every `t('key')` call with hardcoded strings across all pages. Not recommended unless going single-language.

---

## Feature: Theeeme Personalisation

Per-user colour palette and koro wave customisation.

| Layer | Files | Detail |
|-------|-------|--------|
| **Model** | `core/models/theeeme.py` | Theeeme with 6 colour fields |
| **Model** | `core/models/user.py` | `theeeme` FK, `koro` field |
| **Views** | `core/views/theeemes.py` | TheeemeListView |
| **Serializers** | `core/serializers/theeeme.py` | TheeemeSerializer |
| **Serializers** | `core/serializers/user.py` | `theeeme_colors` in UserSerializer, `theeeme` in UserUpdateSerializer |
| **URLs** | `core/urls.py` | `theeemes/` |
| **Migrations** | `0002`–`0005`, `0013`, `0020`, `0024`–`0032`, `0034`–`0036` |
| **Frontend** | `src/components/TheeemeSelector.jsx`, `src/components/KoroSelector.jsx` |
| **Frontend (EditProfilePage)** | TheeemeSelector and KoroSelector usage |
| **Frontend (all pages)** | `theeemeColors` from localStorage, `btnStyle`/`btnSecondaryStyle`, hero backgrounds, Koros component |
| **Frontend CSS** | `src/styles/oiueei-theme.css` |
| **Depends on** | Core Platform |
| **Depended on by** | Every page's visual styling (colours, koros) |

### Pruning difficulty: **HARD** — Theeeme colours are used for button styling, hero backgrounds, and koros on every page. Removing would require a single static colour scheme replacement across all pages.

---

## Cross-Cutting: RSVP System

The RSVP model serves multiple features. Here is which actions belong to which feature:

| Action | Feature | Created by | Consumed by |
|--------|---------|------------|-------------|
| `MAGIC_LINK` | Core Platform | `RequestLinkView`, `PopInView` | `VerifyLinkView._handle_magic_link` |
| `COLLECTION_INVITE` | Collections | `CollectionInviteView` | `VerifyLinkView._handle_collection_invite` |
| `COLLECTION_REJECT` | Collections | `CollectionInviteView` | `VerifyLinkView._handle_collection_reject` |
| `BOOKING_ACCEPT` | Bookings | `ThingRequestView` | `VerifyLinkView._handle_booking_accept` |
| `BOOKING_REJECT` | Bookings | `ThingRequestView` | `VerifyLinkView._handle_booking_reject` |

**To prune a feature's RSVP actions:** remove the action constant, the handler method in `VerifyLinkView`, and the creation logic in the originating view.

---

## Cross-Cutting: Email Service

All 10 email functions mapped to their feature:

| Function | Feature |
|----------|---------|
| `send_magic_link_email` | Core Platform |
| `send_collection_invite_email` | Collections |
| `send_invite_rejected_email` | Collections |
| `send_collection_revoke_email` | Collections |
| `send_booking_request_email` | Bookings |
| `send_booking_confirmation_email` | Bookings |
| `send_booking_decision_email` | Bookings |
| `send_faq_question_email` | FAQs |
| `send_faq_answer_email` | FAQs |
| `send_faq_hide_email` | FAQs |

---

## Cross-Cutting: Demo Data (Migrations)

Seed migrations that would need updating if features are removed:

| Migration | Content | Feature |
|-----------|---------|---------|
| `0003` | Default theeeme | Core Platform |
| `0036` | All theeemes | Core Platform |
| `0037` | Demo users (Lala, Lele) | Core Platform |
| `0047` | Demo users (Lili, Lolo, Lulu) | Core Platform |
| `0038` | Demo collections (Lala, Lele) | Collections |
| `0048` | Demo collections (Lili, Lolo, Lulu) | Collections |
| `0039` | Demo things (Lala, Lele) | Things |
| `0051` | Demo things (Lili, Lolo, Lulu) | Things |
| `0040` | Demo collection-thing links | Collections + Things |
| `0041` | Demo FAQs | FAQs |
| `0049`–`0050` | Onboarding collection flags | Collections |

---

## Pruning Priority Guide

After user testing, use this priority to decide what to cut:

| Priority | Action | Difficulty |
|----------|--------|------------|
| ~~1~~ | ~~Remove Hue easter egg~~ | ~~DONE~~ |
| 2 | Remove Mixpanel if not needed | TRIVIAL |
| 3 | Remove FAQs if users don't ask questions | EASY |
| 4 | Remove unused Thing types (e.g. ORDER, SHARE) | MEDIUM |
| 5 | Remove Bookings if simple "mark as taken" suffices | MEDIUM |
| 6 | Remove image uploads if text-only is enough | EASY |
| 7 | Reduce i18n to single language | HARD |
| 8 | Replace theeemes with single colour scheme | HARD |
