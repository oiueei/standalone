// Instance legal text — generic version shipped with the standalone repo.
// Every OIUEEI deployment has its own operator, and that operator is the data
// controller: if you self-host OIUEEI, edit the "Who operates this instance"
// section with your identity and contact details.
// (The official deployment at www.oiueei.com replaces this file on its deploy
// branch with the full version carrying its owner's real details.)
export default `
# Our commitment

OIUEEI runs without ads and without third-party analytics: nobody tracks you while you use it. Your data is not the product — it is never sold or shared with anyone. There are no tracking pixels in the emails and no links wrapped in trackers. This commitment is written into the project's design rules; it's the starting point, not the fine print.

# Who operates this instance

OIUEEI is source-available software (BUSL 1.1 licence; MIT from 2030). This page describes **one instance** of OIUEEI: whoever operates it is responsible for the service and for how your data is handled.

*The operator of this instance has not yet completed this section with their identity and contact details. If you run this deployment, edit \`frontend/src/legal/\` with your details.*

# Privacy

**What the app stores, by design:** your email (to sign in with magic links — no passwords), your name and optional profile (bio, photo, language), the content you publish (collections, things and their photos, questions and answers, requests), your email preferences, and **optional** demographics (birth-year generation and postal code) visible only to the people who run your communities, in aggregate — never public.

**Where it goes:** email leaves through whatever SMTP provider the operator configured, and images are hosted on Cloudinary. Nothing else leaves the instance: no third-party SDKs, no events sent anywhere. Usage metrics are first-party, pseudonymised and never shared.

**Cookies:** technical only (session and security). There are no third-party or advertising cookies, which is why there is no banner.

**Deleting your account:** from your profile (Edit profile → Delete account), with email confirmation. It is immediate and irreversible: your account, your collections, your things and their photos, and your requests are erased. Questions you asked on other people's things and the transfer history stay **without your name** ("Former member").

# Basic terms

OIUEEI is in alpha and offered "as is", without warranties, to the extent the law allows. The content you publish is yours and you are responsible for it; don't publish anything illegal or harmful. Exchanges (gifts, sales, loans, swaps) are agreements between people: the platform is not a party to them and processes no payments. There is a report button, and the operator may remove content that breaks these rules.

# For operators (self-hosting)

If you deploy OIUEEI, you are the data controller: complete this page with your identity, your purposes and your processors (email provider, Cloudinary, hosting), and honour your users' rights. The BUSL 1.1 licence allows production use; the one thing it does not allow is offering OIUEEI to third parties as a hosted service that competes with the licensor's paid offering.
`;
